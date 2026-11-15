"""Migration, real launch controls and native memory/diagnostic regressions."""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/native_tools.py, also under -m unittest)
from native_tools import native_cxx  # noqa: E402
from akynoleyend.environment import runtime_environment
from akynoleyend.access import access_report
from akynoleyend.errors import ProjectError
from akynoleyend.files import read_json, sha256, write_json
from akynoleyend.graphics import graphics_environment
from akynoleyend.launch import launch
from akynoleyend.legacy import brand_pe, migrate_build

ROOT = Path(__file__).resolve().parents[1]


def pe_fixture():
    data = bytearray(2048)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<HH", data, 132, 0x8664, 1)
    struct.pack_into("<H", data, 148, 240)
    struct.pack_into("<H", data, 152, 0x20B)
    section = 392
    data[section : section + 8] = b".rdata\0\0"
    struct.pack_into("<II", data, section + 16, 1024, 512)
    struct.pack_into("<I", data, section + 36, 0x40000040)
    for offset, text in [(600, b"hookshot_vk.dll\0"), (700, b"hookshot_options.ini\0")]:
        data[offset : offset + len(text)] = text
    return data


def installation(folder):
    folder.mkdir()
    romfs = folder.parent / "romfs"
    for name in ("System", "Pack"):
        (romfs / name).mkdir(parents=True, exist_ok=True)
    (folder / "hookshot.exe").write_bytes(pe_fixture())
    (folder / "hookshot_vk.dll").write_bytes(b"synthetic generic DLL")
    (folder / "image.bin").write_bytes(b"synthetic image")
    (folder / "hookshot_options.ini").write_bytes(b"keep saved options")
    (folder / "user/save").mkdir(parents=True)
    (folder / "user/save/keep").write_bytes(b"keep save")
    manifest = {
        "schema": 1,
        "project": "ocarina-hookshot",
        "version": "0.3.9-dev.1",
        "game_build_id": "e0f3ccfa",
        "romfs": str(romfs),
        "files": {n: sha256(folder / n) for n in ("hookshot.exe", "hookshot_vk.dll", "image.bin")},
    }
    write_json(folder / "ocarina-build.json", manifest)
    return manifest


class MigrationTests(unittest.TestCase):
    def test_access_diagnostic_still_finds_blocked_legacy_exe_before_migration(self):
        with tempfile.TemporaryDirectory() as d:
            game = Path(d) / "jogo"
            installation(game)
            real_open = Path.open

            def denied(path, *args, **kwargs):
                if path == game / "hookshot.exe":
                    raise PermissionError(13, "denied", str(path))
                return real_open(path, *args, **kwargs)

            with patch.object(Path, "open", denied):
                report = access_report(game)
            self.assertFalse(report["game_started"])
            self.assertEqual(Path(report["files"][1]["path"]).name, "hookshot.exe")
            self.assertEqual(report["files"][1]["status"], "blocked")
            self.assertEqual(report["files"][2]["status"], "readable")

    def test_pe_replaces_only_complete_readonly_literals_without_changing_length(self):
        data = bytes(pe_fixture())
        converted, changes = brand_pe(data)
        self.assertEqual(len(converted), len(data))
        allowed = set()
        for old, change in changes.items():
            for at in change["offsets"]:
                allowed.update(range(at, at + len(old)))
        self.assertTrue(
            all(i in allowed for i, (a, b) in enumerate(zip(data, converted)) if a != b)
        )
        self.assertIn(b"AkynoLeyend.dll\0", converted)
        self.assertIn(b"AkynoLeyend_opts.ini\0", converted)

    def test_signed_writable_duplicate_truncated_and_foreign_exes_are_refused(self):
        cases = []
        data = pe_fixture()
        struct.pack_into("<II", data, 152 + 112 + 32, 1800, 8)
        cases.append(data)
        data = pe_fixture()
        struct.pack_into("<I", data, 392 + 36, 0xC0000040)
        cases.append(data)
        data = pe_fixture()
        text = b"hookshot_vk.dll\0"
        data[1600 : 1600 + len(text)] = text
        cases.append(data)
        cases.extend([pe_fixture()[:1500], b"not a PE"])
        for data in cases:
            with self.subTest(size=len(data)), self.assertRaises(ProjectError):
                brand_pe(bytes(data))

    def test_migration_is_idempotent_and_preserves_image_save_options_and_backup(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "jogo"
            old = installation(folder)
            original = (folder / "hookshot.exe").read_bytes()
            updated = migrate_build(folder, lambda _: None)
            self.assertEqual(updated["files"]["image.bin"], old["files"]["image.bin"])
            self.assertEqual((folder / "user/save/keep").read_bytes(), b"keep save")
            self.assertEqual((folder / "AkynoLeyend_opts.ini").read_bytes(), b"keep saved options")
            self.assertEqual((folder / "backup-identidade/hookshot.exe").read_bytes(), original)
            self.assertFalse(updated["identity_migration"]["translated_instructions_changed"])
            self.assertEqual(read_json(folder / "AkynoLeyend-build.json"), updated)
            self.assertIsNone(migrate_build(folder, lambda _: None))

    def test_tampering_or_failed_manifest_publication_preserves_original_build(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as d:
                folder = Path(d) / "jogo"
                manifest = installation(folder)
                if corrupt:
                    (folder / "hookshot_vk.dll").write_bytes(b"tampered")
                before = {
                    p.name: p.read_bytes()
                    for p in folder.iterdir()
                    if p.is_file() and p.name != "build.lock"
                }
                with patch("akynoleyend.legacy.write_json", side_effect=PermissionError("denied")):
                    with self.assertRaises((ProjectError, OSError)):
                        migrate_build(folder, lambda _: None)
                self.assertEqual(
                    before,
                    {
                        p.name: p.read_bytes()
                        for p in folder.iterdir()
                        if p.is_file() and p.name != "build.lock"
                    },
                )
                self.assertFalse((folder / "AkynoLeyend-build.json").exists())
                self.assertEqual(read_json(folder / "ocarina-build.json"), manifest)


class ControlsTests(unittest.TestCase):
    def test_invalid_controls_and_opengl_are_refused(self):
        for options in (
            {"backend": "opengl"},
            {"resolution": "110"},
            {"framegen": 1},
            {"sharpness": True},
            {"sharpness": 101},
            {"pacing": "yes"},
        ):
            with self.subTest(options=options), self.assertRaises(ProjectError):
                graphics_environment(**options)
        e = runtime_environment(
            {"AKYNO_RESOLUTION": "99", "RX_FAKE": "1", "KEEP": "yes"}, "compatibilidade"
        )
        self.assertNotIn("AKYNO_RESOLUTION", e)
        self.assertEqual(e["RX_VK_VRAM_MB"], "4096")
        self.assertNotIn("RX_VK_TEX_MAX_DIM", e)
        self.assertEqual(e["KEEP"], "yes")

    @unittest.skipIf(os.name == "nt", "portable executable-script fixture")
    def test_real_child_receives_graphics_controls_and_amd_diagnostics(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            game = root / "game"
            game.mkdir()
            romfs = root / "romfs"
            for name in ("System", "Pack"):
                (romfs / name).mkdir(parents=True)
            exe = game / "AkynoLeyend.exe"
            exe.write_text(
                f"#!{sys.executable}\nimport json,os\nprint(json.dumps(dict(os.environ)))\n"
            )
            exe.chmod(0o755)
            for name in ("AkynoLeyend.dll", "image.bin"):
                (game / name).write_bytes(b"synthetic")
            write_json(
                game / "AkynoLeyend-build.json",
                {
                    "schema": 1,
                    "project": "AkynoLeyend",
                    "version": "0.4.0-dev.1",
                    "romfs": str(romfs),
                    "files": {
                        n: sha256(game / n)
                        for n in ("AkynoLeyend.exe", "AkynoLeyend.dll", "image.bin")
                    },
                },
            )
            platform = SimpleNamespace(
                name="nt", environ=dict(os.environ, AKYNO_RESOLUTION="99"), getpid=os.getpid
            )
            with (
                patch("akynoleyend.launch.os", platform),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                status = launch(
                    game,
                    "compatibilidade",
                    trace_runtime=True,
                    resolution="100",
                    speed="realtime",
                    upscaling="lanczos",
                    sharpness=10,
                    framegen=0,
                    pacing=True,
                    auto_prepare=False,
                )
            self.assertEqual(status, 0)
            logs = next((game / "diagnosticos").iterdir())
            env = json.loads((logs / "saida.log").read_text())
            self.assertEqual(env["AKYNO_RESOLUTION"], "1")
            self.assertEqual(env["HOS_DYNRES"], "0")
            self.assertEqual(env["HOS_REALTIME_STEP"], "1")
            self.assertEqual(env["AKYNO_FRAMEGEN"], "0")
            self.assertEqual(env["RX_VK_FAULT_BREADCRUMBS"], "1")
            meta = read_json(logs / "execucao.json")
            self.assertEqual(meta["graphics"]["sharpness"], 10)
            self.assertEqual(meta["environment"]["RX_VK_VRAM_MB"], "4096")


class Native040Tests(unittest.TestCase):
    def test_actual_menu_initialization_applies_explicit_options_after_saved_values(self):
        text = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
        actual = text[text.index("void menu_init()") : text.index("bool menu_is_open()")]
        fixture = r"""
        #include <algorithm>
        #include <cassert>
        #include <cstdio>
        #include <cstdlib>
        #include <cstring>
        #include <string>
        #include "upscale_mode.h"
        using namespace mkwvk;
        int selected_upscaler=0;
        Upscaler started_upscaler=Upscaler::Off;
        bool temporal_menu=false;
        bool extended_outputs=false;
        int boot_output=0;
        struct Options {int resolution=0,realtime=1,framegen=0,pace=0,upscale=0,sharpness=0,output_res=0,show_fps=0,handheld=0,prompts=0;} opts;
        struct Row {const char* key;int* value;int lo,hi;};
        Row rows[]={{"resolution",&opts.resolution,0,4},{"realtime",&opts.realtime,0,1},
                    {"framegen",&opts.framegen,0,8}};
        const char* ini_key(const Row& r){return r.key;}
        std::string ini_path(){return "fixture-options.ini";}
        FILE* hos_game_file(const char*,const char* mode){return fopen(ini_path().c_str(),mode);}
        // ACTUAL_INIT
        int main(){
          FILE* f=fopen(ini_path().c_str(),"w");assert(f);
          fputs("options_version=2\nresolution=0\nrealtime=0\nframegen=8\n",f);fclose(f);
          menu_init();remove(ini_path().c_str());
          if(getenv("EXPECT_EXPLICIT")){
            assert(opts.resolution==1&&opts.realtime==1&&opts.framegen==0);
            assert(opts.sharpness==10&&opts.upscale==2&&opts.pace==1);
            assert(started_upscaler==Upscaler::Lanczos);
          }else assert(opts.resolution==0&&opts.realtime==0&&opts.framegen==8);
        }
        """.replace("// ACTUAL_INIT", actual)
        clean = {k: v for k, v in os.environ.items() if not k.startswith(("RX_", "AKYNO_", "HOS_"))}
        self.compile_run(fixture, clean)
        self.compile_run(
            fixture,
            dict(
                clean,
                EXPECT_EXPLICIT="1",
                AKYNO_RESOLUTION="1",
                HOS_DYNRES="1",
                HOS_REALTIME_STEP="1",
                AKYNO_FRAMEGEN="0",
                RX_VK_FRAMEGEN_MULT="8",
                AKYNO_SHARPNESS="10",
                RX_VK_UPSCALE="2",
                RX_VK_PACE="1",
            ),
        )

    def compile_run(self, source, environment=None):
        cxx = native_cxx()
        if not cxx:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cpp = root / "test.cpp"
            exe = root / ("test.exe" if os.name == "nt" else "test")
            cpp.write_text(source)
            built = subprocess.run(
                [
                    cxx,
                    "-std=c++20",
                    "-O1",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-pthread",
                    "-I" + str(ROOT / "gpu/vk"),
                    str(cpp),
                    "-o",
                    str(exe),
                ] + (["-static"] if os.name == "nt" else []),
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run(
                [str(exe)], cwd=root, env=environment, capture_output=True, text=True, timeout=20
            )
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_actual_captured_reads_match_reference_across_40000_changes_and_host_errors(self):
        text = (ROOT / "gpu/vk/vk_memory.cpp").read_text()
        actual = text[
            text.index("bool memory_read_as_submitted(") : text.index("bool memory_has_shadow(")
        ]
        fixture = (
            (ROOT / "tests/native/captured_read040.cpp")
            .read_text()
            .replace("// ACTUAL_READ", actual)
        )
        self.compile_run(fixture)
        self.compile_run(fixture, dict(os.environ, AKYNO_READ_CACHE="0"))

    def test_actual_readback_wait_rechecks_timeline_after_queue_catchup(self):
        text = (ROOT / "gpu/vk/vk_memory.cpp").read_text()
        actual = text[
            text.index("namespace {\nstd::mutex wb_pages_mu;") : text.index("/// A copy that fails")
        ]
        replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text()
        wait = replay[
            replay.index("    // EvilBoyce / PR296:") : replay.index(
                "    // (textures the GPU wrote there:", replay.index("void invalidate(")
            )
        ]
        fixture = (
            (ROOT / "tests/native/readback040.cpp")
            .read_text()
            .replace("// ACTUAL_TRACKER", actual)
            .replace("// ACTUAL_WAIT", wait)
        )
        self.compile_run(fixture)

    def test_cpu_breadcrumb_ring_is_bounded_ordered_and_safe_between_threads(self):
        self.compile_run("""
        #include "cpu_breadcrumbs.h"
        #include <cassert>
        #include <thread>
        int main(){mkwvk::CpuBreadcrumbs ring;
          std::thread a([&]{for(int i=0;i<1000;i++)ring.record(i,12,'g');});
          std::thread b([&]{for(int i=0;i<1000;i++)ring.record(i,13,'c');});
          a.join();b.join();auto entries=ring.snapshot();assert(entries.size()==64);
          assert(entries.front().sequence==1937&&entries.back().sequence==2000);
          for(size_t i=1;i<entries.size();i++)assert(entries[i].sequence==entries[i-1].sequence+1);
        }""")

    def test_upstream_regressions_execute_with_real_source(self):
        cxx = native_cxx()
        for number in (300, 327, 362, 416):
            with self.subTest(pr=number):
                native = number != 300
                if native and not cxx:
                    self.skipTest("C++ compiler unavailable")
                result = subprocess.run(
                    [sys.executable, str(ROOT / f"tests/test_upstream_{number}_040.py")] + (["--cxx", cxx] if native else []),
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
