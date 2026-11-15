"""Synthetic archives verify dump wrappers without decompressing native game .zs files."""

import importlib.util
import io
import struct
import tempfile
import unittest
from pathlib import Path

import zstandard

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("packed_nup_test", ROOT / "nx2/nup.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def make_archive(path, files):
    # files: (section, relative name, actual file bytes, wrapper: plain/packed/unknown)
    names = bytearray(b"rootexefsromfs")
    records = []
    stored = []
    for section, name, data, mode in files:
        offset = len(names)
        encoded = name.encode()
        names.extend(encoded)
        records.append((offset, len(encoded), len(data)))
        stored.append(
            data
            if mode == "plain"
            else zstandard.ZstdCompressor(write_content_size=mode != "unknown").compress(data)
        )
    dirs_at = 0xF0
    files_at = dirs_at + 3 * 24
    kids_at = files_at + 80 * len(files)
    strings_at = kids_at + 4 * (2 + len(files))
    data_at = strings_at + len(names)
    result = bytearray(data_at + sum(map(len, stored)))
    result[:4] = b"NUP\x01"
    struct.pack_into("<Q", result, 0x40, len(result))
    result[0x80:0x84] = b"TOC\x01"
    struct.pack_into("<IQQQQ", result, 0x84, 1, 3, len(files), strings_at - 0x80, len(names))
    struct.pack_into("<QIIII", result, 0xB0, 1, 0, 1, 2, 1)
    ex = [3 + i for i, file in enumerate(files) if file[0] == "exefs"]
    rom = [3 + i for i, file in enumerate(files) if file[0] == "romfs"]
    for i, record in enumerate(((0, 4, 0, 2), (4, 5, 2, len(ex)), (9, 5, 2 + len(ex), len(rom)))):
        struct.pack_into("<4I", result, dirs_at + 24 * i, *record)
    kids = [1, 2, *ex, *rom]
    struct.pack_into(f"<{len(kids)}I", result, kids_at, *kids)
    result[strings_at:data_at] = names
    at = data_at
    for i, ((name, length, size), content) in enumerate(zip(records, stored)):
        struct.pack_into("<IIQQQ", result, files_at + 80 * i, name, length, size, at, size)
        result[at : at + len(content)] = content
        at += len(content)
    path.write_bytes(result)


class PackedNupTests(unittest.TestCase):
    def extract(self, files):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "fixture.nup"
        make_archive(source, files)
        archive = reader.Nup(source)
        self.addCleanup(archive.f.close)
        output = root / "output"
        reader.extract(archive, archive.titles[0], output, quiet=True)
        return archive, output

    def test_plain_files_remain_byte_identical(self):
        _, output = self.extract([("romfs", "raw.bin", b"plain file data", "plain")])
        self.assertEqual((output / "romfs/raw.bin").read_bytes(), b"plain file data")

    def test_wrapped_files_with_and_without_frame_size_are_decoded(self):
        for mode in ("packed", "unknown"):
            with self.subTest(mode=mode):
                _, output = self.extract([("romfs", "data.bin", b"content" * 300, mode)])
                self.assertEqual((output / "romfs/data.bin").read_bytes(), b"content" * 300)

    def test_small_incompressible_wrapper_larger_than_plain_file(self):
        _, output = self.extract([("romfs", "small.bin", b"xyz", "unknown")])
        self.assertEqual((output / "romfs/small.bin").read_bytes(), b"xyz")

    def test_native_zs_frame_is_not_decompressed(self):
        native = zstandard.ZstdCompressor().compress(b"game content" * 400)
        _, output = self.extract([("romfs", "native.zs", native, "plain")])
        self.assertEqual((output / "romfs/native.zs").read_bytes(), native)

    def test_outer_wrapper_is_removed_but_inner_zs_is_preserved(self):
        native = zstandard.ZstdCompressor().compress(b"game content" * 400)
        for mode in ("packed", "unknown"):
            with self.subTest(mode=mode):
                _, output = self.extract([("romfs", "wrapped.zs", native, mode)])
                self.assertEqual((output / "romfs/wrapped.zs").read_bytes(), native)

    def test_cache_file_with_right_size_but_old_compressed_bytes_is_repaired(self):
        archive, output = self.extract([("romfs", "repair.bin", b"correct content" * 50, "packed")])
        target = output / "romfs/repair.bin"
        target.write_bytes(b"x" * target.stat().st_size)
        reader.extract(archive, archive.titles[0], output, quiet=True)
        self.assertEqual(target.read_bytes(), b"correct content" * 50)

    def test_read_returns_decompressed_nso_header(self):
        header = bytearray(0x100)
        header[:4] = b"NSO0"
        header[0x40:0x44] = bytes.fromhex("e0f3ccfa")
        archive, _ = self.extract([("exefs", "main", bytes(header), "packed")])
        record = next(archive.walk(1))[1]
        self.assertEqual(archive.read(record, 0x60), bytes(header[:0x60]))
        target = io.BytesIO()
        archive.copy_to(record, target)
        self.assertEqual(target.getvalue(), bytes(header))

    def test_truncated_wrapper_does_not_replace_an_existing_target(self):
        archive, output = self.extract([("romfs", "asset.bin", b"correct data" * 80, "packed")])
        target = output / "romfs/asset.bin"
        original = target.read_bytes()
        source = Path(archive.path)
        archive.f.close()
        source.write_bytes(source.read_bytes()[:-1])
        broken = reader.Nup(source)
        self.addCleanup(broken.f.close)
        with self.assertRaises(ValueError):
            reader.extract(broken, broken.titles[0], output, quiet=True)
        self.assertEqual(target.read_bytes(), original)

    def test_module_fallback_uses_a_complete_nso_from_another_title(self):
        nso = b"NSO0" + bytes(252)
        archive, output = self.extract(
            [("exefs", "rtld", nso, "packed"), ("romfs", "rtld", b"partial module", "plain")]
        )
        archive.titles = [
            {"index": 0, "version": 1, "exefs": 1},
            {"index": 1, "version": 2, "exefs": 2},
        ]
        destination = output / "private-modules"
        destination.mkdir()
        (destination / "rtld").write_bytes(b"partial module")
        reader.heal(archive, archive.titles[1], str(destination), ["rtld"])
        self.assertEqual((destination / "rtld").read_bytes(), nso)
