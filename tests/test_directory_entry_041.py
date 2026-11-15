"""Regression for a host nn::fs DirectoryEntry ABI mismatch that hid foliage files.

Runs a native C exercise of the actual helper shared by both ReadDirectory
paths; on Linux it does not require the game's EXE or Windows toolchain.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DirectoryEntry041Tests(unittest.TestCase):
    def test_regular_and_mod_entries_use_the_same_wire_serializer(self):
        source = (ROOT / "host" / "nn_fs.c").read_text(encoding="utf-8")
        fn = "hos_fs_directory_entry_set_type("
        # Both the filesystem and mod-overlay directory listing must use
        # the correct ABI; do not regress one of the two paths.
        self.assertEqual(source.count(fn), 2)
        self.assertIn(fn + "GP(e), isdir);", source)
        self.assertIn(fn + "GP(e), x->is_dir);", source)
        self.assertNotIn("GP(e + 0x302)", source)

    def test_guest_layout_is_verified_by_compiled_c_helper(self):
        compiler = (os.environ.get("OCARINA_TEST_CC") or shutil.which("cc") or
                    shutil.which("clang"))
        if not compiler and os.name == "nt":
            bundled = ROOT / "ferramentas" / "llvm" / "bin" / "clang.exe"
            if bundled.exists():
                compiler = str(bundled)
        if not compiler:
            self.skipTest("C compiler not available")
        with tempfile.TemporaryDirectory(prefix="akyno-fs-wire-") as tmp:
            output = Path(tmp) / ("wire.exe" if os.name == "nt" else "wire")
            cmd = [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                   "-I" + str(ROOT / "host"),
                   str(ROOT / "tests" / "native" / "directory_entry_041.c"),
                   "-o", str(output)]
            built = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run([str(output)], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("ABI checks passed", run.stdout)

if __name__ == "__main__":
    unittest.main()
