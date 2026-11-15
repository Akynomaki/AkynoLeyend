"""Regressions for the supplied device-lost logs and the pinned GPU backports."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from akynoleyend.files import sha256, write_json
from akynoleyend.launch import launch
from akynoleyend.runtime_failure import renderer_failure

ROOT = Path(__file__).resolve().parent.parent


class RuntimeFailureTests(unittest.TestCase):
    def test_bounded_scanner_finds_markers_split_across_reads(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "erros.log"
            for text in [b"vk: device lost: reading the checkpoints",
                         b"vk: GPU_FATAL device_lost result=-4 operation=present"]:
                log.write_bytes(b"x" * ((64 << 10) - 8) + b"\n" + text + b"\n")
                failure = renderer_failure(log)
                self.assertEqual(failure["kind"], "device_lost")
                self.assertLessEqual(len(failure["evidence"]), 512)
            log.write_bytes(b"a" * (3 << 20) + b"\nvk: device lost: reading the checkpoints")
            self.assertEqual(renderer_failure(log)["exit_code"], 70)

    def test_notes_and_normal_close_are_not_misclassified(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "erros.log"
            log.write_text("device lost prevention enabled\nvk: no failures\nwindow closed\n")
            self.assertIsNone(renderer_failure(log))
            log.unlink()
            self.assertEqual(renderer_failure(log)["kind"], "log_unavailable")

    @unittest.skipIf(os.name == "nt", "portable executable-script fixture")
    def test_real_child_exit_zero_cannot_hide_device_loss(self):
        for failed in (False, True):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as d:
                root = Path(d); game = root / "game"; game.mkdir()
                romfs = root / "romfs"
                for name in ("System", "Pack"):
                    (romfs / name).mkdir(parents=True)
                exe = game / "AkynoLeyend.exe"
                message = ("[hos sead::MainThread] vk: device lost: reading the checkpoints\n"
                           if failed else "[hos host] display: window closed, exiting\n")
                exe.write_text(f"#!{sys.executable}\nimport sys\nsys.stderr.write({message!r})\n")
                exe.chmod(0o755)
                for name in ("AkynoLeyend.dll", "image.bin"):
                    (game / name).write_bytes(b"synthetic")
                write_json(game / "AkynoLeyend-build.json", {
                    "schema": 1, "project": "AkynoLeyend", "version": "0.3.8-dev.2",
                    "romfs": str(romfs), "files": {n: sha256(game / n) for n in
                    ("AkynoLeyend.exe", "AkynoLeyend.dll", "image.bin")}})
                # Replace only the launcher's platform view, keeping pathlib
                # and the real POSIX child process implementation untouched.
                platform = SimpleNamespace(name="nt", environ=os.environ, getpid=os.getpid)
                with patch("akynoleyend.launch.os", platform), contextlib.redirect_stdout(io.StringIO()):
                    result = launch(game, auto_prepare=False)
                metadata = json.loads(next((game / "diagnosticos").glob("*/execucao.json")).read_text())
                self.assertEqual(metadata["process_exit_code"], 0)
                self.assertEqual(result, 70 if failed else 0)
                self.assertEqual(metadata["exit_code"], result)
                if failed:
                    self.assertEqual(metadata["runtime_failure"]["kind"], "device_lost")


class NativeBackportTests(unittest.TestCase):
    def compile_run(self, source, *, expected=0, arguments=()):
        compiler = shutil.which("c++") or shutil.which("clang++")
        if not compiler:
            self.skipTest("native C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); src = p / "test.cpp"; exe = p / "test"
            src.write_text(source)
            built = subprocess.run([compiler, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror",
                                    "-pthread", str(src), "-o", str(exe)],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(exe), *arguments], capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode, expected, run.stdout + run.stderr)
            return run

    def test_real_page_table_code_defers_last_write_wins_and_chunks_updates(self):
        memory = (ROOT / "gpu/vk/vk_memory.cpp").read_text()
        # (r4: TableRun and the flush arithmetic live in vk_table_runs.h; the real header is compiled with the real functions)
        header = (ROOT / "gpu/vk/vk_table_runs.h").read_text().replace("#pragma once", "")
        actual = header + "using namespace mkwvk;\n" + memory[memory.index("// (TableRun: vk_table_runs.h"):memory.index("uint64_t memory_guest_pages()")]
        fixture = (ROOT / "tests/native/page_table039.cpp").read_text()
        self.compile_run(fixture.replace("// ACTUAL_TABLE_FUNCTIONS", actual))
        texture = (ROOT / "gpu/vk/vk_texture.cpp").read_text()
        begin = texture[texture.index("void texture_begin_recording("):texture.index("VkCommandBuffer upload_command_buffer()")]
        end = texture[texture.index("bool texture_uploads_recorded()"):texture.index("int view_nvn_format(")]
        self.assertIn("memory_table_begin();", begin)
        self.assertLess(end.index("memory_table_flush();"), end.index("full_barrier(up_cmd)"))
        self.assertIn("VK_BUFFER_USAGE_TRANSFER_DST_BIT", memory[memory.index("uint64_t memory_guest_pages()"):memory.index("bool memory_init()")])

    def test_real_writeback_code_preserves_cpu_counter_words(self):
        memory = (ROOT / "gpu/vk/vk_memory.cpp").read_text()
        actual = memory[memory.index("std::mutex cpu_words_mu;"):memory.index("// ---- a pool remade larger")]
        fixture = (ROOT / "tests/native/cpu_words039.cpp").read_text()
        self.compile_run(fixture.replace("// ACTUAL_COUNTER_FUNCTIONS", actual))
        replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text()
        counter = replay[replay.index("case NOP_REPORT_COUNTER:"):replay.index("case NOP_RESET_COUNTER:")]
        self.assertIn("memory_cpu_owned(host->gpu_guest(c.addr), sizeof rec)", counter)

    def test_actual_narrow_emitters_match_signed_and_unsigned_memory_reads(self):
        memory = (ROOT / "gpu/vk/eden/shader_recompiler/backend/spirv/emit_spirv_memory.cpp").read_text()
        actual = memory[memory.index("// (hookshot) 8- and 16-bit loads"):memory.index("Id EmitLoadGlobal32(")]
        fixture = (ROOT / "tests/native/narrow_load039.cpp").read_text()
        self.compile_run(fixture.replace("// ACTUAL_NARROW_EMITTERS", actual))

    def test_actual_device_lost_handler_stops_with_nonzero_before_atexit(self):
        replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text()
        actual = replay[replay.index("void check_device_result("):replay.index("// ---- submissions: a timeline")]
        fixture = '''
        #include <cstdlib>
        #include <cstdio>
        #include <cstdarg>
        using VkResult = int;
        constexpr int VK_ERROR_DEVICE_LOST = -4;
        void logf(const char* f, ...) { va_list a; va_start(a,f); vfprintf(stderr,f,a); va_end(a); }
        void checkpoints_report() { fputs("CHECKPOINT_RECORDED",stderr); }
        // HANDLER
        int main(int argc,char**) {
            atexit([] { fputs("CACHE_SAVED",stderr); });
            check_device_result(argc > 1 ? -4 : 2, "fixture");
            return 0;
        }
        '''.replace("// HANDLER", actual)
        good = self.compile_run(fixture)
        self.assertIn("CACHE_SAVED", good.stderr)
        bad = self.compile_run(fixture, arguments=("fault",), expected=70)
        self.assertIn("GPU_FATAL device_lost", bad.stderr)
        self.assertIn("CHECKPOINT_RECORDED", bad.stderr)
        self.assertNotIn("CACHE_SAVED", bad.stderr)

    def test_actual_prepare_path_saves_cache_and_never_enters_gameplay(self):
        main = (ROOT / "gpu/vk/vk_main.cpp").read_text()
        actual = main[main.index("bool started_up()"):main.index("int start(void* hwnd)")]
        fixture = (ROOT / "tests/native/prepare_only039.cpp").read_text()
        source = fixture.replace("// ACTUAL_STARTUP", actual)
        normal = self.compile_run(source)
        self.assertIn("GAMEPLAY_STARTED", normal.stdout)
        prepared = self.compile_run(source, arguments=("only",))
        self.assertIn("DRIVER_CACHE_SAVED", prepared.stdout)
        self.assertIn("PREPARE_COMPLETE", prepared.stderr)
        self.assertNotIn("GAMEPLAY_STARTED", prepared.stdout)
        missing = self.compile_run(source, arguments=("only", "missing"), expected=71)
        self.assertIn("PREPARE_FAILED", missing.stderr)
        self.assertNotIn("DRIVER_CACHE_SAVED", missing.stdout)

    def test_uniform_gap_cache_avoids_scans_and_invalidates_on_changes(self):
        replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text()
        actual = replay[replay.index("/// The open gap around"):replay.index("uint64_t ub_overlay(")]
        fixture = (ROOT / "tests/native/ub_gap039.cpp").read_text()
        self.compile_run(fixture.replace("// ACTUAL_GAP_FUNCTIONS", actual))
        prune = replay[replay.index("void ub_prune("):replay.index("uint64_t ub_generation(")]
        self.assertIn("ub_list_epoch.fetch_add", prune)
        push = replay[replay.index("ub_updates.push_back(std::move(up));"):]
        self.assertIn("ub_list_epoch.fetch_add", push[:180])
