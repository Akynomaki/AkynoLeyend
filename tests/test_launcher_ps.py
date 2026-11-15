"""Execute the real launcher with PowerShell and a recording native-process fixture.

The fixture replaces the compiler's Python process; no game or compiler is run.
Set OCARINA_TEST_PWSH to a PowerShell executable to enable these POSIX CI checks.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PWSH = os.environ.get("OCARINA_TEST_PWSH") or shutil.which("pwsh")


@unittest.skipUnless(
    PWSH and os.name != "nt", "Requires PowerShell and the POSIX recording-process fixture"
)
class LauncherExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="akynoleyend launcher test ")
        self.base = Path(self.temporary.name)
        self.project = self.base / "project with spaces"
        self.project.mkdir()
        shutil.copy2(ROOT / "compilar.ps1", self.project / "compilar.ps1")
        runtime = self.project / "ferramentas/python"
        runtime.mkdir(parents=True)
        executable = runtime / "python.exe"
        executable.write_text(
            "#!"
            + sys.executable
            + "\nimport os,sys\nos.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n"
        )
        executable.chmod(0o755)
        (self.project / "manage.py").write_text(
            "import json,os,sys\nfrom pathlib import Path\n"
            "Path(os.environ['OCARINA_TEST_RECORD']).write_text(json.dumps(sys.argv[1:]))\n"
            "raise SystemExit(int(os.environ.get('OCARINA_TEST_EXIT', '0')))\n"
        )
        self.record = self.base / "arguments.json"
        self.environment = dict(os.environ, OCARINA_TEST_RECORD=str(self.record))

    def tearDown(self):
        self.temporary.cleanup()

    def invoke(self, *arguments):
        return subprocess.run(
            [
                PWSH,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(self.project / "compilar.ps1"),
                *arguments,
            ],
            cwd=self.base,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def recorded(self):
        return json.loads(self.record.read_text())

    def test_defaults_are_relative_to_script_from_another_working_directory(self):
        result = self.invoke("-Jogo", str(self.base / "my game.nup"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        arguments = self.recorded()
        self.assertEqual(arguments[0], "build")
        self.assertEqual(arguments[arguments.index("--out") + 1], str(self.project / "jogo"))
        self.assertEqual(arguments[arguments.index("--work") + 1], str(self.project / "work"))
        self.assertNotIn("--jobs", arguments)

    def test_explicit_paths_and_job_count_are_preserved(self):
        output, work = self.base / "custom output", self.base / "custom work"
        result = self.invoke(
            "-Jogo", "my game.nup", "-Destino", str(output), "-Trabalho", str(work), "-Jobs", "1"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        arguments = self.recorded()
        self.assertEqual(arguments[arguments.index("--out") + 1], str(output))
        self.assertEqual(arguments[arguments.index("--work") + 1], str(work))
        self.assertEqual(arguments[arguments.index("--jobs") + 1], "1")

    def test_folder_inputs_are_passed_separately(self):
        result = self.invoke("-Exefs", "my exefs", "-Romfs", "my romfs")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        arguments = self.recorded()
        self.assertEqual(arguments[arguments.index("--exefs") + 1], "my exefs")
        self.assertEqual(arguments[arguments.index("--romfs") + 1], "my romfs")
        self.assertNotIn("--nup", arguments)

    def test_mixed_input_modes_are_rejected(self):
        result = self.invoke("-Jogo", "game.nup", "-Exefs", "exefs", "-Romfs", "romfs")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.record.exists())

    def test_incomplete_folder_input_is_rejected(self):
        result = self.invoke("-Exefs", "exefs")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.record.exists())

    def test_native_build_failure_exit_code_is_propagated(self):
        self.environment["OCARINA_TEST_EXIT"] = "23"
        result = self.invoke("-Jogo", "game.nup")
        self.assertEqual(result.returncode, 23, result.stdout + result.stderr)

    def test_invalid_job_count_is_rejected_before_starting(self):
        result = self.invoke("-Jogo", "game.nup", "-Jobs", "0")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.record.exists())


if __name__ == "__main__":
    unittest.main()
