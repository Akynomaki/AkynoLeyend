"""A raw shader bank may be analyzed locally but must never enter a distribution."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DistributionLayoutTests(unittest.TestCase):
    def test_raw_banks_are_excluded_from_work_and_rejected_elsewhere(self):
        spec = importlib.util.spec_from_file_location("distribution_check_043", ROOT / "tools/make_distribution.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module.ROOT = root
            (root / "work").mkdir()
            (root / "work/private-bank.bin").write_bytes(b"HKSEED01synthetic")
            (root / "README.md").write_text("synthetic source tree")
            self.assertEqual([rel.as_posix() for _, rel in module.files(True)], ["README.md"])
            (root / "unexpected-bank.bin").write_bytes(b"HKSEED01synthetic")
            with self.assertRaisesRegex(SystemExit, "dados privados"):
                list(module.files(True))
