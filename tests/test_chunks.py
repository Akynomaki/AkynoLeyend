"""Regression for a first standalone lift with no shared work/image directory."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "nx2"))
import kit  # noqa: E402,F401  (bootstrap the vendored lifter's module paths)
import chunks  # noqa: E402


class SyntheticLifter:
    """Small generated text using the same chunk boundary callback as Lifter.write."""

    funcs = {0x80000000: None, 0x80000004: None, 0x80000008: None, 0x8000000C: None}

    def emit_function(self, address, texts):
        return f"void f_{address:x}(Ctx *__restrict A64_NOESC c) {{\n}}\n"

    def write(self, gen_dir, chunk_bytes):
        Path(gen_dir).mkdir(parents=True, exist_ok=True)
        files = []
        text = ""
        for address in self.funcs:
            text += self.emit_function(address, {})
            if len(text) >= chunk_bytes:
                name = f"code_{len(files):03d}.c"
                (Path(gen_dir) / name).write_text(text)
                files.append(name)
                text = ""
        if text:
            name = f"code_{len(files):03d}.c"
            (Path(gen_dir) / name).write_text(text)
            files.append(name)
        return files


class ChunksTests(unittest.TestCase):
    def test_old_normal_chunk_is_removed_when_hot_file_is_also_emitted(self):
        class HotLifter(SyntheticLifter):
            def write(self, gen_dir, chunk_bytes):
                normal = Path(gen_dir) / "code_000.c"
                hot = Path(gen_dir) / "code_hot.c"
                normal.write_text("/* current normal unit */")
                hot.write_text("/* current hot unit */")
                return [str(normal), str(hot)]

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            gen = work / "gen"
            gen.mkdir()
            (gen / "code_001.c").write_text("/* stale translated functions */")
            with contextlib.redirect_stdout(io.StringIO()):
                chunks.write(HotLifter(), str(gen), str(work / "image"))
            self.assertFalse((gen / "code_001.c").exists())
            self.assertTrue((gen / "code_000.c").exists())
            self.assertTrue((gen / "code_hot.c").exists())

    def test_save_creates_shared_metadata_directory(self):
        with tempfile.TemporaryDirectory(prefix="chunks-") as directory:
            shared = Path(directory) / "pasta com espaços" / "work" / "image"
            chunks.save(shared, [0x80000008, 0x80000004])
            self.assertEqual(chunks.load(shared), [0x80000004, 0x80000008])

    def test_first_standalone_write_preserves_image_and_resumes_boundaries(self):
        with tempfile.TemporaryDirectory(prefix="standalone-") as directory:
            work = Path(directory)
            shared = work / "image"
            image = work / "sa" / "image"
            image.mkdir(parents=True)
            (image / "image.bin").write_bytes(b"synthetic image")
            gen = work / "sa" / "gen"
            with patch.object(chunks.a64_lift, "CHUNK_BYTES", 80):
                with contextlib.redirect_stdout(io.StringIO()):
                    files = chunks.write(SyntheticLifter(), str(gen), str(shared))
                boundaries = chunks.load(shared)
                self.assertEqual(boundaries, [0x80000008])
                before = {name: (gen / name).read_bytes() for name in files}
                with contextlib.redirect_stdout(io.StringIO()):
                    again = chunks.write(SyntheticLifter(), str(gen), str(shared))
            self.assertEqual(again, files)
            self.assertEqual({name: (gen / name).read_bytes() for name in files}, before)
            self.assertEqual(chunks.load(shared), boundaries)
            self.assertEqual((image / "image.bin").read_bytes(), b"synthetic image")
            self.assertFalse((shared / "image.bin").exists())

    def test_retry_seeds_boundaries_from_text_written_before_failure(self):
        with tempfile.TemporaryDirectory(prefix="resume-") as directory:
            work = Path(directory)
            gen = work / "sa" / "gen"
            lifter = SyntheticLifter()
            files = lifter.write(str(gen), chunk_bytes=80)
            shared = work / "image"
            self.assertFalse(shared.exists())
            with contextlib.redirect_stdout(io.StringIO()):
                resumed = chunks.write(lifter, str(gen), str(shared))
            self.assertEqual(resumed, files)
            self.assertEqual(chunks.load(shared), [0x80000008])


if __name__ == "__main__":
    unittest.main()
