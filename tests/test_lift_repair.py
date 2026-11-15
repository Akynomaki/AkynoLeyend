"""Repair a real old lifter in a temporary installation, then re-import it in Python -I."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("akyno_lift_repair_test", ROOT / "tools/reparar_lift.py")
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class LiftRepairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lift-repair-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "Instalacao com espacos e acentuação"
        self.root.mkdir()
        self.payload = ROOT / repair.RELATIVE
        paths = ["manage.py", "akynoleyend/__init__.py", "nx2/kit.py", "nx2/oot_occlusion.py", "nx2/insn.py", "nx2/lift_fixes.py",
                 "third_party/a64-kit/lift/a64emit.py", "third_party/a64-kit/lift/build_emit.py",
                 "third_party/a64-kit/tools/toolchain.py"]
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        # This fixture represents the original release targeted by the repair,
        # even when the tests run from a later development version.
        (self.root / "akynoleyend/__init__.py").write_text('__version__ = "0.4.2-rc.1"\n')
        (self.root / "AkynoLeyendBuilder.exe").write_bytes(b"MZ synthetic launcher, never executed")
        self.target = self.root / repair.RELATIVE
        text = self.payload.read_text(encoding="utf-8")
        text = text.replace("        self.after = {}       # pc -> inline C after that ordinary instruction; included in register/flag analysis\n", "")
        start = text.index("    def op_text(")
        end = text.index("    def dead_flags(", start)
        text = text[:start] + text[end:]
        text = text.replace("text, fl = self.op_text(pc, w, texts)",
                            "text, fl = texts[(w, pc) if pc_relative(w) else w]")
        text = text.replace("text, flags = self.op_text(pc, w, texts)",
                            "text, flags = texts[(w, pc) if pc_relative(w) else w]")
        self.original = text.encode("utf-8")
        self.assertEqual(repair.fingerprint(self.original), repair.ORIGINAL)
        self.target.write_bytes(self.original)
        (self.root / "work/inputs/keep").mkdir(parents=True)
        (self.root / "work/inputs/keep/extracted").write_bytes(b"preserve extraction")
        (self.root / "jogo/user").mkdir(parents=True)
        (self.root / "jogo/user/save").write_bytes(b"preserve save")

    def apply(self):
        return repair.repair(self.root, self.payload, lambda message: None)

    def test_repairs_exact_old_source_preserves_inputs_and_verifies_real_import(self):
        self.assertFalse(repair.probe(self.root)["has_after"])
        result = self.apply()
        self.assertTrue(result["changed"])
        self.assertEqual(Path(result["backup"]).read_bytes(), self.original)
        self.assertEqual(repair.fingerprint(self.target.read_bytes()), repair.CORRECTED)
        self.assertEqual(result["verified_sites"], 6)
        self.assertEqual(Path(result["module"]), self.target)
        self.assertEqual((self.root / "work/inputs/keep/extracted").read_bytes(), b"preserve extraction")
        self.assertEqual((self.root / "jogo/user/save").read_bytes(), b"preserve save")
        log = json.loads((self.root / "work/logs/reparo-lift.json").read_text(encoding="utf-8"))
        self.assertEqual(log, result)

    def test_running_again_only_verifies_and_preserves_backup(self):
        result = self.apply()
        backups = list((self.root / "work/repairs").rglob("*.bak"))
        again = self.apply()
        self.assertFalse(again["changed"])
        self.assertEqual(again["verified_sites"], 6)
        self.assertEqual(list((self.root / "work/repairs").rglob("*.bak")), backups)
        self.assertEqual(Path(result["backup"]).read_bytes(), self.original)

    def test_failed_post_import_restores_exact_previous_bytes(self):
        before = repair.probe(self.root)
        with patch.object(repair, "probe", side_effect=[before, repair.RepairError("synthetic failure")]):
            with self.assertRaisesRegex(repair.RepairError, "synthetic failure"):
                self.apply()
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_invalid_payload_and_modified_installation_are_rejected(self):
        wrong = Path(self.temporary.name) / "incorrect.py"
        wrong.write_text("# incomplete correction\n")
        with self.assertRaisesRegex(repair.RepairError, "correcao esta incompleto"):
            repair.repair(self.root, wrong, lambda message: None)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.target.write_bytes(self.original + b"\n# unrelated modification\n")
        with self.assertRaisesRegex(repair.RepairError, "alteracoes diferentes"):
            self.apply()
        self.assertTrue(self.target.read_bytes().endswith(b"# unrelated modification\n"))

    def test_wrong_folder_is_rejected_without_creating_work(self):
        folder = Path(self.temporary.name) / "outer"
        folder.mkdir()
        with self.assertRaisesRegex(repair.RepairError, "contem AkynoLeyendBuilder.exe"):
            repair.repair(folder, self.payload, lambda message: None)
        self.assertEqual(list(folder.iterdir()), [])

    @unittest.skipIf(sys.platform == "win32", "POSIX lock contention test")
    def test_running_build_prevents_repair(self):
        with repair.build_lock(self.root):
            with self.assertRaisesRegex(repair.RepairError, "compilacao em andamento"):
                self.apply()
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_cli_uses_isolated_child_and_handles_unicode_paths(self):
        child = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", str(ROOT / "tools/reparar_lift.py"),
             "--root", str(self.root), "--payload", str(self.payload)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertIn("CORRECAO CONFIRMADA", child.stdout)
        self.assertIn(str(self.target), child.stdout)
        self.assertEqual(repair.fingerprint(self.target.read_bytes()), repair.CORRECTED)


if __name__ == "__main__":
    unittest.main()
