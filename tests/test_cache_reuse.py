"""Measure compiler invocations across retry and restored object-cache paths."""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "nx2"))


@unittest.skipIf(os.name == "nt", "POSIX recording compiler fixture")
class RetryCacheTests(unittest.TestCase):
    def test_retry_and_restore_do_not_launch_compiler_but_changed_flags_do(self):
        spec = importlib.util.spec_from_file_location("retry_native_build", ROOT / "nx2/build.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="retry-cache-") as directory:
            folder = Path(directory)
            compiler, count = folder / "compiler", folder / "invocations"
            compiler.write_text(
                "#!" + sys.executable + "\nimport pathlib,sys\n"
                "here=pathlib.Path(__file__).parent\n"
                "with (here/'invocations').open('a') as f: f.write('compile\\n')\n"
                "pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_bytes(b'object')\n"
            )
            compiler.chmod(0o755)
            source, obj = folder / "source.c", folder / "source.o"
            source.write_text("void example(void) {}\n")
            job = (str(compiler), str(source), str(obj), ["-O1"], b"guest headers")
            with patch.object(module, "OBJ_CACHE", str(folder / "cache")):
                self.assertIsNone(module.compile_one(job)[2])
                self.assertIsNone(module.compile_one(job)[2])
                obj.unlink()
                Path(str(obj) + ".sha256").unlink()
                self.assertIsNone(module.compile_one(job)[2])
                self.assertEqual(count.read_text().splitlines(), ["compile"])
                changed = (*job[:3], ["-O2"], job[4])
                self.assertIsNone(module.compile_one(changed)[2])
                self.assertEqual(count.read_text().splitlines(), ["compile", "compile"])


if __name__ == "__main__":
    unittest.main()
