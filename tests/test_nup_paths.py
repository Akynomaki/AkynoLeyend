"""Exercise real extraction and failure cleanup without user game data."""

import builtins
import errno
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from test_nup_packed import make_archive, reader


LONG_NAME = "IgnoreDissentPlayEventAndStartInterval.engineeventActorStateSetting.bgyml"
RELATIVE = "Event/EventSetting/EventSettingComponent/ActorStateSetting/" + LONG_NAME


class NupPathTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nup-path-")
        self.addCleanup(self.temporary.cleanup)
        if os.name == "nt":
            self.addCleanup(shutil.rmtree, reader.filesystem_path(self.temporary.name), ignore_errors=True)
        self.root = Path(self.temporary.name)
        self.source = self.root / "fixture.nup"
        self.data = b"synthetic archive content" * 20
        make_archive(self.source, [("romfs", RELATIVE, self.data, "plain")])
        self.archive = reader.Nup(self.source)
        self.addCleanup(self.archive.f.close)
        self.output = self.root / "game"

    def test_short_temporary_name_avoids_reported_create_failure(self):
        target = self.output / "romfs" / RELATIVE

        def limited_open(path, *args, **kwargs):
            if os.fspath(path).endswith(LONG_NAME + ".part"):
                raise FileNotFoundError(errno.ENOENT, "simulated Windows temporary-path failure", str(path))
            return builtins.open(path, *args, **kwargs)

        with patch.object(reader, "open", limited_open, create=True):
            written, _ = reader.extract(self.archive, self.archive.titles[0], self.output, quiet=True)
        self.assertEqual(written, 1)
        self.assertEqual(target.read_bytes(), self.data)
        self.assertEqual(list(target.parent.glob("*.part")), [])

    def test_drive_unc_unicode_and_prefixed_paths_are_normalized(self):
        examples = {
            "S:/Pasta com acentuação/./pasta/../game": "\\\\?\\S:\\Pasta com acentuação\\game",
            "\\\\server\\share\\pasta\\..\\game": "\\\\?\\UNC\\server\\share\\game",
            "\\\\?\\S:\\game": "\\\\?\\S:\\game",
            "\\\\?\\UNC\\server\\share\\game": "\\\\?\\UNC\\server\\share\\game",
        }
        for original, expected in examples.items():
            with self.subTest(path=original):
                self.assertEqual(reader.extended_windows_path(original), expected)

    def test_real_extraction_with_output_longer_than_max_path(self):
        output = self.root / ("p" * 90) / ("q" * 90) / ("r" * 90)
        reader.extract(self.archive, self.archive.titles[0], output, quiet=True)
        target = output / "romfs" / RELATIVE
        self.assertGreater(len(str(target)), 350)
        self.assertEqual(Path(reader.filesystem_path(target)).read_bytes(), self.data)

    def test_copy_failure_preserves_previous_file_and_cleans_own_temp(self):
        target = self.output / "romfs" / RELATIVE
        target.parent.mkdir(parents=True)
        target.write_bytes(b"previous complete asset")
        sentinel = self.root / "existing-game.o"
        sentinel.write_bytes(b"compiled object")

        def failed_copy(record, stream, *args, **kwargs):
            stream.write(b"partial")
            raise OSError(errno.ENOSPC, "synthetic full disk")

        with patch.object(self.archive, "copy_to", failed_copy):
            with self.assertRaisesRegex(OSError, "diretorio pai existe=True"):
                reader.extract(self.archive, self.archive.titles[0], self.output, quiet=True)
        self.assertEqual(target.read_bytes(), b"previous complete asset")
        self.assertEqual(sentinel.read_bytes(), b"compiled object")
        self.assertEqual(list(target.parent.glob("*.part")), [])

    def test_completed_plain_entry_is_reused_without_copy(self):
        reader.extract(self.archive, self.archive.titles[0], self.output, quiet=True)
        with patch.object(self.archive, "copy_to", side_effect=AssertionError("copied completed entry")):
            self.assertEqual(reader.extract(self.archive, self.archive.titles[0], self.output, quiet=True), (0, 0))

    def test_missing_parent_diagnostic_does_not_blame_archive_or_shader(self):
        missing = FileNotFoundError(errno.ENOENT, "missing parent")
        # (0.4.5: a new file is created under its own name, create_new; one that exists goes by mkstemp)
        with patch.object(reader.tempfile, "mkstemp", side_effect=missing),                 patch.object(reader, "create_new", side_effect=missing):
            with self.assertRaisesRegex(FileNotFoundError, "Confira a disponibilidade da unidade") as caught:
                reader.extract(self.archive, self.archive.titles[0], self.output, quiet=True)
        self.assertEqual(caught.exception.errno, errno.ENOENT)

    def test_archive_traversal_is_still_rejected(self):
        with patch.object(self.archive, "walk", return_value=iter([("../outside.bin", self.archive.files[0])])):
            with self.assertRaisesRegex(SystemExit, "invalid archive path"):
                reader.extract(self.archive, self.archive.titles[0], self.output, only="romfs", quiet=True)
        self.assertFalse((self.root / "outside.bin").exists())


if __name__ == "__main__":
    unittest.main()
