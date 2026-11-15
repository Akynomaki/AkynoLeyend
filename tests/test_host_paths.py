"""Run the real C path builder; on Windows also exercise extended Win32 I/O."""

import os
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent


class HostPathTests(unittest.TestCase):
    def test_lighting_path_is_whole_and_overflow_is_rejected(self):
        compiler = os.environ.get("OCARINA_TEST_CC") or shutil.which("cc") or shutil.which("clang")
        if not compiler and os.name == "nt":
            local = ROOT / "ferramentas/llvm/bin/clang.exe"
            compiler = str(local) if local.is_file() else None
        if not compiler:
            self.skipTest("A C compiler is needed for native path checks")
        with tempfile.TemporaryDirectory(prefix="host path test ") as directory:
            exe = Path(directory) / ("paths.exe" if os.name == "nt" else "paths")
            command = [compiler, "-std=c11", "-I" + str(ROOT / "host"),
                       str(ROOT / "tests/native/test_host_paths.c")]
            if os.name == "nt":
                command.append(str(ROOT / "host/win_path.c"))
            result = subprocess.run(command + ["-o", str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("host path checks passed", result.stdout)

    def test_audio_volume_import_uses_host_implementation_instead_of_duplicate_stub(self):
        sys.path.insert(0, str(ROOT / "nx2"))
        spec = importlib.util.spec_from_file_location("audio_standalone_test", ROOT / "nx2/standalone.py")
        standalone = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(standalone)
        symbol = "_ZN2nn5audio26GetAudioDeviceOutputVolumeEPKNS0_15AudioDeviceNameE"
        self.assertIn("imp_" + symbol, standalone.implemented())
        hooks = [{"sym": symbol, "c": "imp_" + symbol},
                 {"sym": "_ZN2nn5audio7UnknownEv", "c": "imp_unknown_for_test"}]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(standalone.gen_stubs(directory, {"hooks": hooks}), 1)
            stubs = (Path(directory) / "a64_stubs.c").read_text()
            self.assertNotIn(symbol, stubs)
            self.assertIn("imp_unknown_for_test", stubs)


if __name__ == "__main__":
    unittest.main()
