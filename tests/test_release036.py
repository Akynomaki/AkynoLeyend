"""Regressions based on the incomplete collection, missing root and console reports."""
import json
import os
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from akynoleyend.crash_report import collect_run
from akynoleyend.errors import ProjectError
from akynoleyend.process import run
from akynoleyend.romfs import require_romfs, audit_romfs, PROBES


class Release036Tests(unittest.TestCase):
    def test_real_import_retry_backoff_and_bounded_metadata(self):
        root = Path(__file__).resolve().parent.parent
        compiler = shutil.which("c++") or shutil.which("clang++")
        if not compiler and os.name == "nt":
            local = root / "ferramentas/llvm/bin/clang++.exe"
            compiler = str(local) if local.is_file() else None
        if not compiler:
            self.skipTest("no C++ compiler")
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / ("import.exe" if os.name == "nt" else "import")
            args = [compiler, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I" + str(root / "gpu/vk"),
                    str(root / "tests/native/import_hold_test.cpp"), "-o", str(binary)]
            if os.name == "nt":
                args.append("-static")
            compiled = subprocess.run(args, capture_output=True, text=True, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            child = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20)
            self.assertEqual(child.returncode, 0, child.stderr)

    def test_wrong_or_nested_romfs_is_reported_without_modifying_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaisesRegex(ProjectError, "System, Pack"):
                require_romfs(root)
            nested = root / "romfs"
            for name in ("System", "Pack"):
                (nested / name).mkdir(parents=True, exist_ok=True)
            with self.assertRaisesRegex(ProjectError, "raiz parece estar"):
                require_romfs(root)
            require_romfs(nested)
            self.assertTrue((nested / "System").is_dir())

    def test_romfs_probe_distinguishes_missing_empty_and_readable(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a, b = (root / x for x in PROBES[:2])
            a.parent.mkdir(parents=True)
            a.write_bytes(b"data")
            b.touch()
            report = "\n".join(audit_romfs(root))
            self.assertIn(PROBES[0] + ": legivel", report)
            self.assertIn(PROBES[1] + ": VAZIO", report)
            self.assertIn("nao foi possivel ler", report)
            self.assertEqual(a.read_bytes(), b"data")

    def test_isolated_child_writes_unicode_and_records_utf8_mode(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            log = root / "stage.log"
            run([sys.executable, "-I", "-c", "import sys;print(sys.flags.utf8_mode);print('\\u00e7\\ufffd\\u4e2d')"],
                root, os.environ, log, lambda _: None)
            text = log.read_text(encoding="utf-8")
            self.assertIn("1\nç�中", text)

    def test_unfinished_noncrash_run_is_not_published_as_crash(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); logs = root / "game/diagnosticos/run"
            logs.mkdir(parents=True)
            (logs / "execucao.json").write_text(json.dumps({"profile": "original"}))
            (logs / "erros.log").write_text("boot still loading\n")
            with self.assertRaisesRegex(ProjectError, "encerramento registrado"):
                collect_run(root / "game", root / "work", logs)
            self.assertFalse(logs.with_suffix(".zip").exists())

    def test_crash_with_missing_exit_status_is_explicitly_partial(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); logs = root / "game/diagnosticos/run"
            logs.mkdir(parents=True)
            (logs / "execucao.json").write_text(json.dumps({"profile": "original"}))
            (logs / "erros.log").write_text("CRASH: exception 0xc0000005\n")
            path = collect_run(root / "game", root / "work", logs)
            with zipfile.ZipFile(path) as archive:
                self.assertIn("Coleta parcial", archive.read("diagnostico-crash.txt").decode())
