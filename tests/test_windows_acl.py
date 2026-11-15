"""Regression for publishing from a Python 0o700 folder created under UAC."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from akynoleyend.files import workspace_stage
from akynoleyend.windows_acl import Security, private_sddl
from akynoleyend.config import ROOT


class StagingAclTests(unittest.TestCase):
    def test_descriptor_grants_the_actual_user_instead_of_the_default_owner(self):
        sid = "S-1-5-21-100-200-300-1001"
        sddl = private_sddl(sid)
        self.assertEqual(sddl, "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;" + sid + ")")
        self.assertNotIn(";;;OW)", sddl)
        self.assertNotIn(";;;WD)", sddl)
        for invalid in ("", "user", sid + ")(A;;FA;;;WD)", "S-1-5-21\n"):
            with self.assertRaises(ValueError): private_sddl(invalid)

    def test_acl_is_applied_before_writing_and_moving_the_published_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); events = []
            def secure(folder):
                self.assertEqual(list(folder.iterdir()), [])
                events.append(folder)
            with workspace_stage(prefix="publish-", dir=root, _acl=secure) as stage:
                self.assertEqual(events, [stage])
                (stage / "test.bin").write_bytes(b"unchanged payload")
                (stage / "test.bin").replace(root / "published.bin")
            self.assertFalse(stage.exists())
            self.assertEqual((root / "published.bin").read_bytes(), b"unchanged payload")

    def test_acl_failure_does_not_publish_from_a_restricted_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(PermissionError):
                with workspace_stage(prefix="publish-", dir=root,
                                     _acl=lambda _: (_ for _ in ()).throw(PermissionError("DACL failed"))):
                    self.fail("must not write/publish before successful ACL setup")
            self.assertEqual(list(root.iterdir()), [])

    def test_all_publishing_contexts_use_user_named_staging(self):
        # Enforce the integration contract: the known private-folder publication sites are covered.
        import ast
        for name, expected in (("build.py", 3), ("shader_prepare.py", 2)):
            tree = ast.parse((ROOT / "akynoleyend" / name).read_text())
            stages = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Name) and node.func.id == "workspace_stage"]
            self.assertEqual(len(stages), expected, name)

    @unittest.skipUnless(os.name == "nt", "Windows token/DACL APIs unavailable on this host")
    def test_real_windows_descriptor_contains_token_user_after_creation(self):
        sid = Security().user_sid()
        with tempfile.TemporaryDirectory() as directory:
            with workspace_stage(prefix="acl-check-", dir=Path(directory)) as stage:
                child = stage / "child.bin"; child.write_bytes(b"test")
                for path in (stage, child):
                    command = str(Path(os.environ["SystemRoot"]) / "System32/icacls.exe")
                    result = subprocess.run([command, str(path), "/findsid", "*" + sid],
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn(str(path).casefold(), result.stdout.casefold())

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell parser unavailable on this host")
    def test_repair_script_parses_without_executing_it(self):
        powershell = str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
        literal = str(ROOT / "reparar-acesso.ps1").replace("'", "''")
        command = "$e=$null; $t=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('" + literal + "',[ref]$t,[ref]$e); if($e.Count){$e | Out-String | Write-Output; exit 1}"
        result = subprocess.run([powershell, "-NoProfile", "-Command", command],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__": unittest.main()
