"""Ferramentas > EXPORTAR SAVES (akynoleyend/saves.py, from Hookshot's scripts/oot_saves.py): an emulator's Ocarina save
copied into the port's save folder. Run on temporary folders laid out as the emulators and the port keep them; no game,
no emulator and no real save folder of this PC is touched."""
import hashlib
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from akynoleyend import saves  # noqa: E402
from akynoleyend.errors import ProjectError  # noqa: E402

PROFILE = "39B517F1E3F888DA8F9083B93BE41189"
HEADER = bytes.fromhex("04030201eb802d00")   # (the header both sides share)


def write_save(folder: Path, tag: bytes, slot_count=3, when=None):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "account.sav").write_bytes(HEADER + b"account" + tag)
    (folder / "option.sav").write_bytes(HEADER + b"option" + tag * 50)
    for n in range(slot_count):
        slot = folder / ("slot_%02d" % n)
        slot.mkdir(exist_ok=True)
        (slot / "progress.sav").write_bytes(HEADER + b"progress" + tag * (100 + n))
        (slot / "caption.sav").write_bytes(HEADER + b"caption" + tag * (30 + n))
    if when is not None:
        for path in folder.rglob("*"):
            if path.is_file():
                os.utime(path, (when, when))


def tree(folder: Path) -> dict:
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def eden_save(appdata: Path, data="eden", profile=PROFILE) -> Path:
    return appdata / data / "nand" / "user" / "save" / "0000000000000000" / profile / "0400486024DEC000"


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.appdata = self.base / "Roaming"
        self.game = self.base / "jogo"
        self.game.mkdir()
        self.env = mock.patch.dict(os.environ, {"APPDATA": str(self.appdata)})
        self.env.start()
        self.lines = []

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def export(self, name, **kw):
        kw.setdefault("check_running", False)
        return saves.export_saves(name, self.game, report=self.lines.append, **kw)

    @property
    def target(self):
        return self.game / "user" / "save" / saves.PORT_UID


class Find(Case):
    def test_the_empty_profile_000_is_not_a_save(self):
        eden_save(self.appdata, profile="0" * 32).mkdir(parents=True)   # (an emulator keeps it empty)
        write_save(eden_save(self.appdata), b"E")
        folder, found = saves.locate(saves.EMULATORS["pokedinner"], None)
        self.assertEqual(folder, self.appdata / "eden")
        self.assertEqual(list(found), [PROFILE])

    def test_lichii_and_mdias_look_in_lichii_first_then_eden(self):
        write_save(eden_save(self.appdata), b"E")
        for name in ("lichii", "mdias"):
            self.assertEqual(saves.locate(saves.EMULATORS[name], None)[0], self.appdata / "eden")
        write_save(eden_save(self.appdata, data="lichii"), b"L")
        for name in ("lichii", "mdias"):
            self.assertEqual(saves.locate(saves.EMULATORS[name], None)[0], self.appdata / "lichii")
        for name in ("fritz", "pokedinner"):   # (Fritchii and PokeDinner keep Eden's folder)
            self.assertEqual(saves.locate(saves.EMULATORS[name], None)[0], self.appdata / "eden")

    def test_newer_account_layout(self):
        newer = self.appdata / "eden" / "nand" / "user" / "save" / "account" / PROFILE / "0400486024DEC000" / "0"
        write_save(newer, b"N")
        self.assertEqual(saves.locate(saves.EMULATORS["fritz"], None)[1], {PROFILE: newer})

    def test_portable_user_folder_and_save_folder_given(self):
        portable = self.base / "Lichii-portatil"
        write_save(eden_save(portable, data="user"), b"P")
        self.assertEqual(list(saves.locate(saves.EMULATORS["lichii"], portable)[1]), [PROFILE])
        self.assertEqual(list(saves.locate(saves.EMULATORS["lichii"], eden_save(portable, data="user"))[1]), [PROFILE])

    def test_nothing_found_says_where_it_looked(self):
        with self.assertRaises(ProjectError) as caught:
            saves.locate(saves.EMULATORS["lichii"], None)
        self.assertIn(str(self.appdata / "lichii"), str(caught.exception))
        self.assertIn(str(self.appdata / "eden"), str(caught.exception))

    def test_the_last_saved_profile_unless_one_is_named(self):
        old, new = "A" * 32, "B" * 32
        write_save(eden_save(self.appdata, profile=old), b"O", when=time.time() - 86400)
        write_save(eden_save(self.appdata, profile=new), b"N", when=time.time())
        found = saves.locate(saves.EMULATORS["fritz"], None)[1]
        self.assertEqual(saves.pick(found, None)[0], new)
        self.assertEqual(saves.pick(found, old.lower())[0], old)
        with self.assertRaises(ProjectError):
            saves.pick(found, "C" * 32)


class Export(Case):
    def test_into_an_existing_port_save_with_a_backup(self):
        source = eden_save(self.appdata)
        write_save(source, b"E", slot_count=6)
        write_save(self.target, b"P", slot_count=6)
        (self.target / "slot_09").mkdir()   # (a slot only on the port's side does not stay mixed in)
        before_source, before_port = tree(source), tree(self.target)
        result = self.export("pokedinner")
        self.assertEqual(tree(self.target), before_source)            # every file, byte for byte
        self.assertFalse((self.target / "slot_09").exists())
        self.assertEqual(tree(source), before_source)                  # the emulator's side only read
        backup = Path(result["backup"]) / saves.PORT_UID
        self.assertEqual(tree(backup), before_port)                    # the port's old save kept whole
        self.assertTrue(str(backup).startswith(str(self.game / "user" / "save-backups")))
        self.assertEqual(sorted(p.name for p in (self.game / "user" / "save").iterdir()), [saves.PORT_UID])   # no stage left
        self.assertEqual(result["files"], 2 + 6 * 2)

    def test_into_a_port_that_never_saved(self):
        write_save(eden_save(self.appdata), b"E")
        result = self.export("fritz")
        self.assertEqual(tree(self.target), tree(eden_save(self.appdata)))
        self.assertIsNone(result["backup"])

    def test_a_failed_copy_leaves_the_port_save_as_it_was(self):
        write_save(eden_save(self.appdata), b"E")
        write_save(self.target, b"P")
        before = tree(self.target)
        real, calls = saves.shutil.copy2, []

        def failing(*args, **kw):
            calls.append(args)
            if len(calls) == 4:
                raise OSError("disco cheio")
            return real(*args, **kw)
        with mock.patch.object(saves.shutil, "copy2", failing), self.assertRaises(OSError):
            self.export("lichii")
        self.assertEqual(tree(self.target), before)
        self.assertEqual(sorted(p.name for p in (self.game / "user" / "save").iterdir()), [saves.PORT_UID])
        self.assertFalse((self.game / "user" / "save-backups").exists())

    def test_a_copy_that_does_not_match_is_refused(self):
        write_save(eden_save(self.appdata), b"E")
        write_save(self.target, b"P")
        before = tree(self.target)
        real = saves.shutil.copy2

        def corrupting(src, dst, **kw):
            real(src, dst, **kw)
            if str(dst).endswith("progress.sav"):
                with open(dst, "r+b") as f:
                    f.write(b"\xff")
        with mock.patch.object(saves.shutil, "copy2", corrupting), self.assertRaises(ProjectError) as caught:
            self.export("mdias")
        self.assertIn("nao confere", str(caught.exception))
        self.assertEqual(tree(self.target), before)

    def test_dry_run_changes_nothing(self):
        write_save(eden_save(self.appdata), b"E")
        write_save(self.target, b"P")
        before = tree(self.target)
        self.export("pokedinner", dry_run=True)
        self.assertEqual(tree(self.target), before)
        self.assertFalse((self.game / "user" / "save-backups").exists())

    def test_refused_while_the_game_or_the_emulator_runs(self):
        write_save(eden_save(self.appdata), b"E")
        write_save(self.target, b"P")
        before = tree(self.target)
        with mock.patch.object(saves, "running", return_value=["o jogo (AkynoLeyend.exe)"]), \
             self.assertRaises(ProjectError) as caught:
            self.export("lichii", check_running=True)
        self.assertIn("Feche", str(caught.exception))
        self.assertEqual(tree(self.target), before)

    def test_a_link_in_the_save_is_refused(self):
        source = eden_save(self.appdata)
        write_save(source, b"E")
        outside = self.base / "segredo.txt"
        outside.write_text("nao e um save")
        try:
            os.symlink(outside, source / "slot_00" / "link.sav")
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links unavailable here")
        with self.assertRaises(ProjectError):
            self.export("fritz")
        self.assertFalse(self.target.exists())

    def test_unknown_emulator_and_missing_game_folder(self):
        with self.assertRaises(ProjectError):
            self.export("ryujinx")
        with self.assertRaises(ProjectError):
            saves.export_saves("lichii", self.base / "nao-existe", check_running=False, report=self.lines.append)


class Wiring(unittest.TestCase):
    def test_the_port_save_folder_is_the_hosts(self):
        applet = (ROOT / "host/nn_applet.c").read_text(encoding="utf-8")
        self.assertIn("user_uid[2] = {0x0000000000000001ULL, 0x5a3c9e1f0b7d2468ULL}", applet)
        self.assertIn('"save\\\\%016llx%016llx", (unsigned long long)G64(ARG(1) + 8)', (ROOT / "host/nn_fs.c").read_text(encoding="utf-8"))
        self.assertEqual(saves.PORT_UID, "%016x%016x" % (0x5a3c9e1f0b7d2468, 1))

    def test_cli_and_launcher(self):
        from akynoleyend.cli import parser
        args = parser().parse_args(["export-saves", "--emulator", "mdias", "--out", str(ROOT)])
        self.assertEqual(args.emulator, "mdias")
        xaml = (ROOT / "builder/AkynoLeyendBuilder/MainWindow.xaml").read_text(encoding="utf-8")
        dlss = xaml.index('Content="Baixar DLSS da NVIDIA"')
        button = xaml.index('Content="Exportar Save"')   # (EXPORTAR SAVES before 0.4.7)
        self.assertLess(dlss, button)
        self.assertLess(button, xaml.index("</WrapPanel>", dlss))   # (beside it, in the same row)
        code = (ROOT / "builder/AkynoLeyendBuilder/MainWindow.xaml.cs").read_text(encoding="utf-8")
        self.assertIn('new Runner(tools,"export-saves",', code)
        for name in ("fritz", "mdias", "pokedinner", "lichii"):
            self.assertIn('"%s"' % name, code)


if __name__ == "__main__":
    unittest.main()
