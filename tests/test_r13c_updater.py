"""r13c: a package that does not know the installed game is refused while staging (before the launcher closes and before any
file is replaced), and a rolled-back update leaves no copies behind. Packages made here, in a temporary folder."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from akynoleyend.errors import ProjectError
from akynoleyend.updater import clear_abandoned, install_files, stage_update

INSTALLED = "a" * 64


def package(path, known=()):
    coherence = "PREVIOUS_HOST_SOURCES = {\n    \"0.4.3-test.4\": {\n%s    },\n}\n" % "".join(
        '        "%s",\n' % identity for identity in known)
    files = {"AkynoLeyendBuilder.exe": b"MZ-new-ui", "manage.py": b"# new orchestrator\n", "VERSION": b"0.4.3-test.4\n",
             "ferramentas/prebuilt/AkynoLeyend.dll": b"MZ-renderer", "ferramentas/prebuilt/renderer.json": b"{}",
             "akynoleyend/coherence.py": coherence.encode()}
    index = {"schema": 1, "kind": "update", "version": "0.4.3-test.4",
             "files": {n: hashlib.sha256(v).hexdigest() for n, v in files.items()}}
    with zipfile.ZipFile(path, "w") as z:
        for n, v in files.items():
            z.writestr(n, v)
        z.writestr("update-package.json", json.dumps(index))
    return files


def installation(base):
    root = base / "project"
    (root / "jogo").mkdir(parents=True)
    (root / "jogo/AkynoLeyend-build.json").write_text(json.dumps({"version": "0.4.3-test.4", "source_sha256": INSTALLED}),
                                                      encoding="utf-8")
    (root / "manage.py").write_bytes(b"# installed\n")
    return root


class Staging(unittest.TestCase):
    def test_a_package_that_does_not_list_the_installed_game_is_refused_before_anything_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root, archive = installation(Path(d)), Path(d) / "old.zip"
            package(archive, known=["b" * 64])
            with self.assertRaisesRegex(ProjectError, r"nao reconhece o jogo instalado \(revisao aaaaaaaa\).*Nada foi alterado"):
                stage_update(archive, root, root / "jogo", report=lambda _: None)
            self.assertEqual((root / "manage.py").read_bytes(), b"# installed\n")
            self.assertEqual(list((root / "atualizacoes").glob("pendente-*")), [])

    def test_a_package_that_lists_it_is_staged(self):
        with tempfile.TemporaryDirectory() as d:
            root, archive = installation(Path(d)), Path(d) / "new.zip"
            package(archive, known=["b" * 64, INSTALLED])
            self.assertTrue(stage_update(archive, root, root / "jogo", report=lambda _: None).is_file())

    def test_the_installed_package_again_is_staged(self):
        # (nothing to replace: its maintain-build finds the game up to date)
        with tempfile.TemporaryDirectory() as d:
            root, archive = installation(Path(d)), Path(d) / "same.zip"
            for name, data in package(archive).items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes(data)
            self.assertTrue(stage_update(archive, root, root / "jogo", report=lambda _: None).is_file())

    def test_no_compiled_game_is_not_checked(self):
        with tempfile.TemporaryDirectory() as d:
            root, archive = installation(Path(d)), Path(d) / "new.zip"
            (root / "jogo/AkynoLeyend-build.json").unlink()
            package(archive)
            self.assertTrue(stage_update(archive, root, root / "jogo", report=lambda _: None).is_file())


class Rollback(unittest.TestCase):
    def test_a_rolled_back_update_leaves_no_copies_and_its_folder_is_cleared_next_time(self):
        with tempfile.TemporaryDirectory() as d:
            root, archive = installation(Path(d)), Path(d) / "new.zip"
            package(archive, known=[INSTALLED])
            plan = stage_update(archive, root, root / "jogo", report=lambda _: None)

            def fail(_):
                raise ProjectError("synthetic compile failure")
            with self.assertRaisesRegex(ProjectError, "synthetic"):
                install_files(plan, fail)
            self.assertEqual((root / "manage.py").read_bytes(), b"# installed\n")
            self.assertFalse((plan.parent / "anterior").exists())
            self.assertEqual(clear_abandoned(root / "atualizacoes", report=lambda _: None), 1)
            self.assertFalse(plan.parent.exists())


if __name__ == "__main__":
    unittest.main()
