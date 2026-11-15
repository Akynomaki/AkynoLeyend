"""The extractor hotfix is reversible and never discards existing build data."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nup_repair_test", ROOT / "tools/reparar_extracao.py")
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class NupRepairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="repair-nup-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "Instalacao com espaço e acentuação"
        self.root.mkdir()
        (self.root / "nx2").mkdir()
        (self.root / "manage.py").write_text("# fixture, never executed\n")
        (self.root / "AkynoLeyendBuilder.exe").write_bytes(b"MZ fixture, never executed")
        self.target = self.root / "nx2/nup.py"
        self.original = b"# synthetic legacy reader for transaction tests\n"
        self.target.write_bytes(self.original)
        self.accepted = patch.object(repair, "ORIGINAL", repair.fingerprint(self.original))
        self.accepted.start()
        self.addCleanup(self.accepted.stop)
        # (0.4.5) the reader this hotfix ships, kept as it was: nx2/nup.py extracts on several threads since then
        self.payload = ROOT / "tests/fixtures/nup_reader_c1b9fb6f.py"
        self.keep = {}
        for name, data in {"work/inputs/keep/asset.bin": b"extracted asset",
                           "work/sa/build/old-game.o": b"compiled object",
                           "jogo/user/save": b"saved progress"}.items():
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            self.keep[p] = data

    def apply(self):
        return repair.repair(self.root, self.payload, lambda _: None)

    def test_applies_with_real_probe_and_preserves_objects_inputs_and_saves(self):
        result = self.apply()
        self.assertTrue(result["changed"])
        self.assertEqual(Path(result["backup"]).read_bytes(), self.original)
        self.assertEqual(repair.fingerprint(self.target.read_bytes()), repair.CORRECTED)
        self.assertGreater(result["verification"]["target_characters"], 350)
        self.assertEqual(result["verification"]["bytes_verified"], 26)
        for path, expected in self.keep.items():
            self.assertEqual(path.read_bytes(), expected)

    def test_second_apply_is_idempotent(self):
        first = self.apply()
        backups = list((self.root / "work/repairs").rglob("*.bak"))
        self.assertFalse(self.apply()["changed"])
        self.assertEqual(list((self.root / "work/repairs").rglob("*.bak")), backups)
        self.assertEqual(Path(first["backup"]).read_bytes(), self.original)

    def test_failed_probe_restores_previous_bytes(self):
        with patch.object(repair, "probe", side_effect=repair.RepairError("synthetic probe failure")):
            with self.assertRaisesRegex(repair.RepairError, "synthetic probe failure"):
                self.apply()
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertFalse((self.root / "work/logs/reparo-extracao.json").exists())

    def test_unknown_reader_and_changed_payload_are_rejected(self):
        self.target.write_bytes(b"# unrelated custom reader\n")
        with self.assertRaisesRegex(repair.RepairError, "Extrator diferente"):
            self.apply()
        self.assertEqual(self.target.read_bytes(), b"# unrelated custom reader\n")
        wrong = self.root / "wrong.py"
        wrong.write_text("# partial payload\n")
        with self.assertRaisesRegex(repair.RepairError, "incompleto"):
            repair.repair(self.root, wrong, lambda _: None)

    def test_existing_compiled_build_is_preserved(self):
        (self.root / "jogo/AkynoLeyend-build.json").write_text("{}")
        with self.assertRaisesRegex(repair.RepairError, "Ja existe um jogo compilado"):
            self.apply()
        self.assertEqual(self.target.read_bytes(), self.original)

    @unittest.skipIf(sys.platform == "win32", "POSIX flock fixture")
    def test_running_build_blocks_repair(self):
        with repair.build_lock(self.root):
            with self.assertRaisesRegex(repair.RepairError, "compilacao em andamento"):
                self.apply()
        self.assertEqual(self.target.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
