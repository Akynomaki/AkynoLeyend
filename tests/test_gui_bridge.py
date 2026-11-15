"""Exercise the GUI's CLI boundary with small synthetic inputs, never game data."""

import contextlib
import io
import struct
import tempfile
import unittest
from pathlib import Path

from akynoleyend.cli import main
from akynoleyend.errors import ProjectError
from akynoleyend.game import verify_nup
from akynoleyend.progress import CompileProgress


def synthetic_nup(path: Path, identity: str = "e0f3ccfa") -> bytes:
    names = b"rootexefsromfsmain"
    title_at = 0xB0
    dirs_at = title_at + 0x40
    files_at = dirs_at + 3 * 24
    kids_at = files_at + 80
    strings_at = kids_at + 3 * 4
    data_at = strings_at + len(names)
    result = bytearray(data_at + 0x60)
    result[:4] = b"NUP\x01"
    struct.pack_into("<Q", result, 0x40, len(result))
    result[0x80:0x84] = b"TOC\x01"
    struct.pack_into("<IQQQQ", result, 0x84, 1, 3, 1, strings_at - 0x80, len(names))
    struct.pack_into("<QIIII", result, title_at, 1, 0, 1, 2, 1)
    for index, record in enumerate(((0, 4, 0, 2), (4, 5, 2, 1), (9, 5, 3, 0))):
        struct.pack_into("<4I", result, dirs_at + index * 24, *record)
    struct.pack_into("<IIQQQ", result, files_at, 14, 4, 0x60, data_at, 0x60)
    struct.pack_into("<3I", result, kids_at, 1, 2, 3)
    result[strings_at:data_at] = names
    result[data_at : data_at + 4] = b"NSO0"
    result[data_at + 0x40 : data_at + 0x44] = bytes.fromhex(identity)
    path.write_bytes(result)
    return bytes(result)


class GuiInputTests(unittest.TestCase):
    def test_nup_check_does_not_extract_or_change_input(self):
        with tempfile.TemporaryDirectory(prefix="gui-check-") as directory:
            folder = Path(directory)
            source = folder / "cópia com espaços.nup"
            original = synthetic_nup(source)
            self.assertTrue(verify_nup(source).startswith("e0f3ccfa"))
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(list(folder.iterdir()), [source])

    def test_malformed_archives_return_project_error_and_close_files(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "broken.nup"
            for data in (b"", b"NUP\x01", bytes(0x80), b"NUP\x01" + bytes(200)):
                with self.subTest(size=len(data)):
                    source.write_bytes(data)
                    with self.assertRaises(ProjectError):
                        verify_nup(source)
                    source.unlink()

    def test_cli_rejects_wrong_version_with_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "wrong.nup"
            synthetic_nup(source, "12345678")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main(["check", "--nup", str(source)])
            self.assertEqual(status, 1)
            self.assertIn("@@error Build do jogo 12345678", output.getvalue())
            self.assertIn("e0f3ccfa", output.getvalue())

    def test_cli_accepts_nup_without_tools_or_compilation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.nup"
            synthetic_nup(source)
            for command in (["check"], ["build", "--check"]):
                with self.subTest(command=command):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        status = main([*command, "--nup", str(source)])
                    self.assertEqual(status, 0)
                    self.assertIn("@@check ok e0f3ccfa", output.getvalue())

    def test_cli_accepts_exefs_and_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            header = bytearray(0x60)
            header[:4] = b"NSO0"
            header[0x40:0x44] = bytes.fromhex("e0f3ccfa")
            (folder / "main").write_bytes(header)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["check", "--exefs", directory]), 0)
                (folder / "main").unlink()
                self.assertEqual(main(["check", "--exefs", directory]), 1)


class ProgressTests(unittest.TestCase):
    def test_progress_counts_only_actual_compiler_completions(self):
        progress = CompileProgress()
        self.assertIsNone(progress.feed("2 files, 2 jobs, -O1 -DTEST"))
        self.assertIsNone(progress.feed("FAILED file.c (2 MB, 1s):"))
        self.assertEqual(progress.feed("  code_007.c         22 MB     150s  (155s)"), 0.5)
        self.assertIsNone(progress.feed("linked AkynoLeyend.exe: 80 MB (5s)"))
        self.assertEqual(progress.feed("  host.c              1 MB       1s  (156s)"), 1.0)

    def test_progress_never_divides_by_zero_and_resets_for_new_batch(self):
        progress = CompileProgress()
        completion = "  host.c              1 MB       1s  (1s)"
        self.assertIsNone(progress.feed(completion))
        progress.feed("0 files, 1 jobs, -O1")
        self.assertIsNone(progress.feed(completion))
        progress.feed("1 files, 1 jobs, -O1")
        self.assertEqual(progress.feed(completion), 1.0)
        self.assertEqual(progress.feed(completion), 1.0)
        progress.feed("2 files, 1 jobs, -O1")
        self.assertEqual(progress.feed(completion), 0.5)


if __name__ == "__main__":
    unittest.main()
