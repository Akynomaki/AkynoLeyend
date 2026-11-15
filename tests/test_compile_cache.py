"""A failed replacement compile must not corrupt a hard-linked cached object."""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "nx2"))


@unittest.skipIf(
    os.name == "nt",
    "This fake-compiler fixture uses a Unix shebang; cross-compile checks are separate.",
)
class CompileCacheTests(unittest.TestCase):
    def test_failed_recompile_preserves_previous_object_and_cache(self):
        specification = importlib.util.spec_from_file_location(
            "cache_native_build", ROOT / "nx2/build.py"
        )
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix="compile-test-") as directory:
            folder = Path(directory)
            compiler = folder / "compiler"
            compiler.write_text(
                "#!"
                + sys.executable
                + "\n"
                + "import pathlib,sys\n"
                + "source=pathlib.Path(sys.argv[sys.argv.index('-c')+1]).read_bytes()\n"
                + "pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_bytes(source)\n"
                + "raise SystemExit(9 if b'FAIL' in source else 0)\n"
            )
            compiler.chmod(0o755)
            source, target = folder / "source.c", folder / "target.o"
            job = (str(compiler), str(source), str(target), [], b"headers")
            with patch.object(module, "OBJ_CACHE", str(folder / "cache")):
                source.write_bytes(b"valid object")
                self.assertIsNone(module.compile_one(job)[2])
                cached = next((folder / "cache").glob("*.o"))
                self.assertIsNone(module.compile_one(job)[2])
                target.unlink()
                self.assertIsNone(module.compile_one(job)[2])
                self.assertEqual(module.COMPILE_COUNTS["compiled"], 1)
                self.assertEqual(module.COMPILE_COUNTS["local_hits"], 1)
                self.assertEqual(module.COMPILE_COUNTS["shared_hits"], 1)
                source.write_bytes(b"FAIL broken replacement")
                self.assertIsNotNone(module.compile_one(job)[2])
                self.assertEqual(target.read_bytes(), b"valid object")
                self.assertEqual(cached.read_bytes(), b"valid object")
                self.assertFalse(Path(str(target) + ".building").exists())
                self.assertEqual(module.COMPILE_COUNTS["failed"], 1)


if __name__ == "__main__":
    unittest.main()
