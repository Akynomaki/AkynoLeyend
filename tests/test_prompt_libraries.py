"""The icon generator uses the application's private modules explicitly; the SDK's Python is not changed."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from akynoleyend import prompts
from akynoleyend.config import ROOT


class PromptLibraryTests(unittest.TestCase):
    def test_probe_and_generator_name_the_private_folder(self):
        seen = []

        def runner(args, **kwargs):
            seen.append(list(args))
            if "-c" not in args:
                out = Path(args[args.index("--out") + 1])
                for name in prompts.REQUIRED:
                    (out / name).parent.mkdir(parents=True, exist_ok=True)
                    (out / name).write_bytes(b"complete")
            return subprocess.CompletedProcess(args, 0, "", "")
        with tempfile.TemporaryDirectory() as d:
            game, romfs = Path(d) / "game", Path(d) / "romfs"
            game.mkdir()
            for rel in prompts.INPUTS + ("System/Resource/ResourceSizeTable.Product.rsizetable.zs",):
                (romfs / rel).parent.mkdir(parents=True, exist_ok=True)
                (romfs / rel).write_bytes(b"fixture")
            with patch.object(prompts, "source_stamp", return_value="fixture"):
                result = prompts.prepare_prompts(game, romfs, root=ROOT, report=lambda _: None, runner=runner)
        self.assertEqual(result["state"], "prepared")
        probe, generator = seen
        private = str(ROOT / prompts.LIBRARIES)
        self.assertEqual(probe[:3], [sys.executable, "-I", "-c"])
        self.assertEqual(probe[-1], private)
        self.assertIn("-I", generator)
        self.assertEqual(generator[generator.index("--libraries") + 1], private)

    def test_isolated_interpreter_imports_the_shipped_modules(self):
        private = ROOT / prompts.LIBRARIES
        if not private.is_dir():
            self.skipTest("Private icon modules are packaged only in the Windows release")
        probe = subprocess.run([sys.executable, "-I", "-c", prompts.PROBE, str(private)],
                               capture_output=True, text=True, timeout=60)
        self.assertEqual(probe.returncode, 0, probe.stderr)
        # Without the folder the same isolated interpreter reports the missing modules (original icons kept).
        bare = subprocess.run([sys.executable, "-I", "-c", prompts.PROBE, str(ROOT / "nao-existe")],
                              capture_output=True, text=True, timeout=60)
        if bare.returncode == 0:
            self.skipTest("This Python already has the icon modules installed globally")
        help_run = subprocess.run([sys.executable, "-I", "-X", "utf8", str(ROOT / "nx2/prompt_assets.py"),
                                   "--libraries", str(private), "--help"], capture_output=True, text=True, timeout=60)
        self.assertEqual(help_run.returncode, 0, help_run.stderr)
        self.assertIn("--romfs", help_run.stdout)


if __name__ == "__main__":
    unittest.main()
