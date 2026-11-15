"""Exercise path-alias lifetime and crash collection with real child processes."""

import contextlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from akynoleyend.crash_report import collect_run, image_base, map_offsets, path_findings, preserve_previous_crash
from akynoleyend.errors import ProjectError
from akynoleyend.files import sha256, write_json
from akynoleyend.windows_paths import nt_target, short_romfs
import akynoleyend.launch as launcher


class FakeDrives:
    def __init__(self, marker=None):
        self.removed = []
        self.created = []
        self.marker = marker

    def available(self, letter):
        return letter != "Z"

    def create(self, letter, target):
        self.created.append((letter, target))
        if self.marker:
            self.marker.write_text("mapped")
        return True

    def remove(self, letter, target):
        self.removed.append((letter, target))
        if self.marker:
            self.marker.unlink()
        return True


def synthetic_pe(path):
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<H", data, 152, 0x20B)
    struct.pack_into("<Q", data, 176, 0x140000000)
    path.write_bytes(data)


class ShortPathsTests(unittest.TestCase):
    def test_skips_occupied_drive_and_removes_only_own_exact_target_after_exception(self):
        api = FakeDrives()
        with self.assertRaisesRegex(ValueError, "child failed"):
            with short_romfs(r"C:\pasta com espaço\romfs", api=api) as alias:
                self.assertEqual(alias, "Y:\\")
                self.assertEqual(api.removed, [])
                raise ValueError("child failed")
        self.assertEqual(api.created, [("Y", "\\??\\C:\\pasta com espaço\\romfs")])
        self.assertEqual(api.removed, api.created)

    def test_no_free_letter_does_not_remove_existing_mapping(self):
        api = FakeDrives()
        api.available = lambda letter: False
        with self.assertRaises(ProjectError):
            with short_romfs(r"C:\romfs", api=api):
                self.fail("No alias was available")
        self.assertEqual(api.created, [])
        self.assertEqual(api.removed, [])

    def test_raced_creation_tries_another_free_letter(self):
        api = FakeDrives()
        original = api.create
        api.create = lambda letter, target: letter != "Y" and original(letter, target)
        with short_romfs(r"C:\romfs", api=api) as alias:
            self.assertEqual(alias, "X:\\")
        self.assertEqual(api.removed, [("X", "\\??\\C:\\romfs")])

    def test_normalizes_unc_and_extended_paths_without_accepting_relative_input(self):
        self.assertEqual(nt_target(r"\\server\share\romfs"), "\\??\\UNC\\server\\share\\romfs")
        self.assertEqual(nt_target(r"\\?\C:\data\romfs"), "\\??\\C:\\data\\romfs")
        self.assertEqual(nt_target(r"\\?\UNC\server\share"), "\\??\\UNC\\server\\share")
        for invalid in ("romfs", r"C:romfs", ""):
            with self.subTest(path=invalid), self.assertRaises(ProjectError):
                nt_target(invalid)


class CrashReportTests(unittest.TestCase):
    def test_graphics_options_are_snapshotted_without_editing_or_unbounded_reads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            logs = root / "logs"
            logs.mkdir()
            options = root / "AkynoLeyend_opts.ini"
            self.assertEqual(launcher.snapshot_options(root, logs, "inicio"), {"status": "absent"})
            data = b"frame_generation=0\nresolution=1\nunknown_future_option=7\n"
            options.write_bytes(data)
            self.assertEqual(launcher.snapshot_options(root, logs, "inicio")["status"], "saved")
            self.assertEqual((logs / "opcoes-inicio.ini").read_bytes(), data)
            self.assertEqual(options.read_bytes(), data)
            options.write_bytes(b"x" * ((64 << 10) + 1))
            self.assertEqual(launcher.snapshot_options(root, logs, "fim"), {"status": "too_large"})
            self.assertFalse((logs / "opcoes-fim.ini").exists())

    def test_pe_base_and_both_map_formats_resolve_the_same_symbols(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            exe, mapped = root / "host.exe", root / "host.map"
            synthetic_pe(exe)
            self.assertEqual(image_base(exe), 0x140000000)
            for text in (" 0001:00000000 f_80cdf000 0000000140001000 f code.obj\n",
                         "  0x0000000140001000 f_80cdf000\n",
                         "Address Size Align Out In Symbol\n00001000 00000000 0 f_80cdf000\n"):
                mapped.write_text(text)
                result = map_offsets(mapped, image_base(exe), [0x1014, 0x500])
                self.assertIn("f_80cdf000+0x14", result[0])
                self.assertIn("sem simbolo", result[1])

    def test_path_audit_reports_overflow_and_ignores_traversal(self):
        root = "C:\\" + "a" * 155
        metadata = {"build": {"romfs": root}, "runtime_romfs": "Y:\\"}
        guest = "System/" + "b" * 130 + ".byml"
        errors = f"fs: OpenFile(content:/{guest}): not found\nfs: OpenFile(content:/../../outside): not found\n"
        result = "\n".join(path_findings(metadata, errors))
        self.assertIn(guest, result)
        self.assertIn("Y:\\", result)
        self.assertNotIn("outside", result)

    def test_bundle_contains_only_logs_and_matching_map_never_game_or_saves(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            logs = root / "game/diagnosticos/20261107-001"
            built = root / "work/sa/build"
            logs.mkdir(parents=True)
            built.mkdir(parents=True)
            synthetic_pe(built / "AkynoLeyend.exe")
            (built / "AkynoLeyend.map").write_text(" 0001:00000000 f_80cdf000 0000000140001000 f code.obj\n")
            metadata = {"exit_code": -1073741819, "build": {"romfs": r"C:\romfs", "files": {
                "AkynoLeyend.exe": sha256(built / "AkynoLeyend.exe")}}}
            write_json(logs / "execucao.json", metadata)
            (logs / "erros.log").write_text("CRASH: exception 0xc0000005 at AkynoLeyend.exe+0x1014\n")
            (logs / "save.dat").write_text("never include")
            preserve_previous_crash(root / "game", root / "work", lambda line: None)
            archive = logs.with_suffix(".zip")
            original_report = archive.read_bytes()
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(set(bundle.namelist()), {"execucao.json", "erros.log", "diagnostico-crash.txt", "AkynoLeyend.map"})
                self.assertIn("f_80cdf000+0x14", bundle.read("diagnostico-crash.txt").decode())
            (built / "AkynoLeyend.exe").write_bytes(b"different build")
            preserve_previous_crash(root / "game", root / "work", lambda line: None)
            self.assertEqual(archive.read_bytes(), original_report)
            archive = collect_run(root / "game", root / "work")
            with zipfile.ZipFile(archive) as bundle:
                self.assertNotIn("AkynoLeyend.map", bundle.namelist())
                self.assertIn("False", bundle.read("diagnostico-crash.txt").decode())
            self.assertEqual((logs / "save.dat").read_text(), "never include")


@unittest.skipIf(os.name == "nt", "POSIX recording-child fixture")
class RecoveryLaunchTests(unittest.TestCase):
    def test_real_child_runs_with_alias_and_trace_and_parent_collects_after_cleanup(self):
        with tempfile.TemporaryDirectory(prefix="recovery launch ") as temporary:
            root = Path(temporary)
            romfs = root / "romfs"
            romfs.mkdir()
            (romfs / "System").mkdir()
            (romfs / "Pack").mkdir()
            marker = root / "alias-active"
            exe = root / "AkynoLeyend.exe"
            exe.write_text("#!" + sys.executable + "\nimport json,os,sys\nfrom pathlib import Path\n"
                           "assert Path(os.environ['RECOVERY_MARKER']).is_file()\n"
                           "print(json.dumps({'args':sys.argv[1:],'trace':os.environ.get('HOS_FS_TRACE'),"
                           "'validation':os.environ.get('RX_VK_VALIDATION'),"
                           "'audio':os.environ.get('HOS_AUDIO_STATS'),'slow':os.environ.get('RX_VK_SLOW_LOG'),"
                           "'backend':os.environ.get('HOS_AUDIO_BACKEND'),"
                           "'cache':os.environ.get('RX_VK_CACHE_READ_MB'),"
                           "'lighting':os.environ.get('RX_VK_FRAMELOG_DROP'),"
                           "'rgba8':os.environ.get('RX_VK_ASTC_RGBA8')}))\n"
                           "Path('AkynoLeyend_opts.ini').write_text('resolution=1\\n')\n")
            exe.chmod(0o755)
            for name in ("AkynoLeyend.dll", "image.bin"):
                (root / name).write_bytes(b"synthetic")
            (root / "AkynoLeyend_opts.ini").write_text("resolution=0\n")
            write_json(root / "AkynoLeyend-build.json", {"schema": 1, "project": "AkynoLeyend", "romfs": str(romfs),
                       "files": {name: sha256(root / name) for name in ("AkynoLeyend.exe", "AkynoLeyend.dll", "image.bin")}})
            api = FakeDrives(marker)
            fake_os = SimpleNamespace(name="nt", environ={**os.environ, "RECOVERY_MARKER": str(marker)}, getpid=os.getpid)
            with patch.object(launcher, "os", fake_os), patch.object(launcher, "short_romfs",
                    side_effect=lambda path: short_romfs(r"C:\synthetic\romfs", api=api)), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.launch(root, short_paths=True, trace_files=True,
                                                trace_runtime=True, trace_lighting=True, texture_mode="rgba8", audio_backend="wasapi", cache_mode="streaming", collect_crash=True, auto_prepare=False), 0)
            self.assertFalse(marker.exists())
            self.assertEqual(api.removed, api.created)
            logs = next(path for path in (root / "diagnosticos").iterdir() if path.is_dir())
            child = json.loads((logs / "saida.log").read_text())
            self.assertEqual(child["args"][2], "Y:\\")
            self.assertEqual(child["trace"], "1")
            self.assertIsNone(child["validation"])
            self.assertEqual(child["audio"], "1")
            self.assertEqual(child["slow"], "25")
            self.assertEqual(child["backend"], "wasapi")
            self.assertEqual(child["cache"], "16")
            self.assertEqual(child["lighting"], "1")
            self.assertEqual(child["rgba8"], "1")
            self.assertTrue((logs / "luzes-frames.bin.go").is_file())
            self.assertFalse((logs / "luzes-frames.bin").exists())
            self.assertEqual(json.loads((logs / "execucao.json").read_text())["cache_mode"], "streaming")
            self.assertEqual(json.loads((logs / "execucao.json").read_text())["exit_code"], 0)
            self.assertTrue(logs.with_suffix(".zip").is_file())
            with zipfile.ZipFile(logs.with_suffix(".zip")) as bundle:
                self.assertEqual(bundle.read("opcoes-inicio.ini"), b"resolution=0\n")
                self.assertEqual(bundle.read("opcoes-fim.ini"), b"resolution=1\n")
            with patch.object(launcher, "os", fake_os), patch.object(launcher, "short_romfs",
                    side_effect=lambda path: short_romfs(r"C:\synthetic\romfs", api=api)), \
                    patch.object(launcher.subprocess, "Popen", side_effect=PermissionError("denied")), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ProjectError, "denied"):
                    launcher.launch(root, short_paths=True, auto_prepare=False)
            self.assertFalse(marker.exists())
            self.assertEqual(api.removed, api.created)


if __name__ == "__main__":
    unittest.main()
