"""Native compare-and-swap operands retain their order through Ampere lowering."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CompareExchangeTests(unittest.TestCase):
    def test_native_register_pairs_offsets_and_unsupported_width(self):
        compiler = shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "cas"
            result = subprocess.run([compiler, "-std=c++20", "-O1", "-w",
                                     "-I" + str(ROOT / "gpu/vk/eden"),
                                     "-I" + str(ROOT / "gpu/vk/compat"),
                                     str(ROOT / "tests/native/lower_cas_test.cpp"), "-o", str(binary)],
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
