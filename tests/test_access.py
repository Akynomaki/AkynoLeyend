"""Regressions for the user's pre-launch PermissionError; never bypass a hash."""
import contextlib
import errno
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from akynoleyend import launch as launcher
from akynoleyend import __version__
from akynoleyend.coherence import HOST_REVISION
from akynoleyend.build import source_identity
from akynoleyend.access import FileAccessError, access_hint, inspect_file, save_access_report
from akynoleyend.cli import main
from akynoleyend.environment import runtime_environment
from akynoleyend.errors import ProjectError
from akynoleyend.files import sha256, write_json


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="access with spaces ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.game = self.root / "jogo"
        self.game.mkdir()
        self.romfs = self.root / "romfs"
        for name in ("System", "Pack"):
            (self.romfs / name).mkdir(parents=True)
        names = ("AkynoLeyend.exe", "AkynoLeyend.dll", "image.bin")
        for name in names:
            (self.game / name).write_bytes(b"synthetic, never execute")
        write_json(self.game / "AkynoLeyend-build.json", {
            "schema": 1, "project": "AkynoLeyend", "romfs": str(self.romfs), "version": __version__, "host_revision": HOST_REVISION, "source_sha256": source_identity(),
            "files": {name: sha256(self.game / name) for name in names}})

    def test_denied_hash_becomes_actionable_error_and_never_starts_the_game(self):
        failure = PermissionError(errno.EACCES, "Permission denied", str(self.game / "AkynoLeyend.exe"))
        save = launcher.save_access_report
        def report(folder, **kwargs):
            return save(folder, destination=self.root / "reports", **kwargs)
        stdout = io.StringIO()
        with patch.object(launcher, "sha256", side_effect=failure), \
                patch.object(launcher, "save_access_report", side_effect=report), \
                patch.object(launcher.subprocess, "Popen") as child, contextlib.redirect_stdout(stdout):
            with self.assertRaisesRegex(FileAccessError, "errno 13"):
                launcher.launch(self.game)
            child.assert_not_called()
        self.assertIn("Diagnostico de acesso para compartilhar", stdout.getvalue())
        archive = next((self.root / "reports").glob("*.zip"))
        with zipfile.ZipFile(archive) as bundle:
            self.assertEqual(set(bundle.namelist()), {"acesso.json", "acesso.txt"})
            data = json.loads(bundle.read("acesso.json"))
        self.assertFalse(data["game_started"])
        self.assertEqual(data["failure"]["errno"], errno.EACCES)
        self.assertFalse((self.game / "diagnosticos").exists())

    def test_file_open_and_stat_errors_are_distinct_from_a_missing_file(self):
        original = Path.open
        target = self.game / "AkynoLeyend.exe"
        def denied(path, *args, **kwargs):
            if path == target:
                raise PermissionError(errno.EACCES, "denied", str(path))
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", denied):
            self.assertEqual(inspect_file(target)["status"], "blocked")
            with self.assertRaises(FileAccessError):
                launcher.verify_build(self.game)
        original_stat = Path.stat
        def denied_stat(path, *args, **kwargs):
            if path == target:
                raise PermissionError(errno.EACCES, "denied stat", str(path))
            return original_stat(path, *args, **kwargs)
        with patch.object(Path, "stat", denied_stat):
            with self.assertRaises(FileAccessError) as caught:
                launcher.verify_build(self.game)
        self.assertIn("consultar", str(caught.exception))
        target.unlink()
        self.assertEqual(inspect_file(target)["status"], "missing")
        with self.assertRaises(FileAccessError) as caught:
            launcher.verify_build(self.game)
        self.assertIsInstance(caught.exception.original, FileNotFoundError)

    def test_directory_misnamed_exe_is_not_treated_as_a_security_block(self):
        target = self.game / "AkynoLeyend.exe"
        target.unlink(); target.mkdir()
        self.assertEqual(inspect_file(target)["status"], "not_a_file")
        with self.assertRaises(FileAccessError) as caught:
            launcher.verify_build(self.game)
        self.assertIsInstance(caught.exception.original, IsADirectoryError)

    def test_real_hash_verification_still_accepts_matches_and_rejects_changes(self):
        self.assertEqual(launcher.verify_build(self.game)["schema"], 1)
        (self.game / "AkynoLeyend.exe").write_bytes(b"changed")
        with self.assertRaisesRegex(ProjectError, "arquivo alterado"):
            launcher.verify_build(self.game)

    def test_winerror_sharing_is_reported_without_claiming_an_antivirus_detection(self):
        error = PermissionError(errno.EACCES, "denied")
        error.winerror = 32
        self.assertIn("Outro processo", access_hint(error))
        error.winerror = 5
        self.assertIn("precisa ser identificada", access_hint(error))

    def test_audit_is_independent_of_manifest_parsing_and_hash_success(self):
        (self.game / "AkynoLeyend-build.json").write_bytes(b"bad manifest")
        output = io.StringIO()
        def report(folder, **kwargs):
            return save_access_report(folder, destination=self.root / "reports", **kwargs)
        with patch("akynoleyend.cli.save_access_report", side_effect=report), \
                patch.object(launcher, "verify_build", side_effect=AssertionError("must not verify")), \
                contextlib.redirect_stdout(output):
            self.assertEqual(main(["audit-access", "--out", str(self.game)]), 0)
        # A read probe is not advertised as build integrity validation.
        self.assertIn("use Jogar para validar os hashes", output.getvalue())

    def test_texture_modes_are_explicit_clean_and_recorded(self):
        parent = {"RX_VK_ASTC_CPU": "1", "RX_VK_ASTC_RGBA8": "1", "PATH": "keep"}
        self.assertNotIn("RX_VK_ASTC_RGBA8", runtime_environment(parent, "original"))
        gpu = runtime_environment(parent, "original", texture_mode="rgba8")
        self.assertEqual(gpu["RX_VK_ASTC_RGBA8"], "1")
        self.assertNotIn("RX_VK_ASTC_CPU", gpu)
        cpu = runtime_environment(parent, "original", texture_mode="cpu-rgba8")
        self.assertEqual(cpu["RX_VK_ASTC_CPU"], "1")
        with self.assertRaises(ProjectError):
            runtime_environment(parent, "original", texture_mode="bad")
        prepared = runtime_environment(parent, "original", cache_mode="preparacao")
        self.assertEqual(prepared["RX_VK_SEED_PREPARE"], "1")
        self.assertEqual(prepared["RX_VK_CACHE_READ_MB"], "16")
        self.assertEqual(prepared["RX_VK_PIPE_CACHE_IO_MB"], "128")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(["run", "--out", str(self.game), "--texture-mode", "rgba8", "--dry-run"]), 0)
        self.assertIn("Modo de texturas: rgba8", stdout.getvalue())
        self.assertIn("RX_VK_ASTC_RGBA8=1", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
