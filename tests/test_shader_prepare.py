"""Python writer -> real C++ reader, corruption guards and renderer-only update."""
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from akynoleyend.config import ROOT
from akynoleyend import __version__
from akynoleyend.coherence import HOST_REVISION
from akynoleyend.errors import ProjectError
from akynoleyend.files import read_json, sha256, write_json
from akynoleyend.launch import verify_build
from akynoleyend.shader_prepare import _update_renderer, prepare_shaders

spec = importlib.util.spec_from_file_location("seed_census", ROOT / "nx2/shader_census.py")
census = importlib.util.module_from_spec(spec)
spec.loader.exec_module(census)


def fixture(writer):
    control = b"\x34\x12\x76\x98" + b"\0" * 212
    code = bytes(n % 251 for n in range(140000))
    a, b = (0, control, code), (1, control, b"small")
    assert writer.add([a, b])
    assert not writer.add([a, b])
    assert writer.add([b])


class SeedTests(unittest.TestCase):
    def test_spooled_python_format_interoperates_with_real_bounded_cpp_reader(self):
        compiler = shutil.which("c++") or shutil.which("clang++")
        if not compiler:
            self.skipTest("native C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); bank = root / "bank.bin"; exe = root / "seed-test"
            with census.SeedWriter(root) as writer:
                fixture(writer); writer.publish(bank)
            args = [compiler, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-pthread",
                    "-I" + str(ROOT / "gpu/vk"), str(ROOT / "tests/native/test_shader_seed.cpp"), "-o", str(exe)]
            built = subprocess.run(args, capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stderr)
            child = subprocess.run([str(exe), str(bank), "valid"], capture_output=True, text=True, timeout=20)
            self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
            self.assertIn("indexed seed checks passed", child.stdout)
            original = bank.read_bytes()
            samples = [b"bad", original[:16], original[:-1], original + b"trailing"]
            bad_counts = bytearray(original); struct.pack_into("<I", bad_counts, 8, 0xffffffff); samples.append(bad_counts)
            bad_stage = bytearray(original); struct.pack_into("<I", bad_stage, 24, 99); samples.append(bad_stage)
            bad_code = bytearray(original); struct.pack_into("<I", bad_code, 32, 17 << 20); samples.append(bad_code)
            bad_id = bytearray(original); struct.pack_into("<I", bad_id, len(original) - 4, 2); samples.append(bad_id)
            for data in samples:
                bank.write_bytes(data)
                child = subprocess.run([str(exe), str(bank), "reject"], capture_output=True, timeout=10)
                self.assertEqual(child.returncode, 0, child.stderr)

    def test_writer_deduplicates_on_disk_and_failed_publication_keeps_previous_bank(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); bank = root / "bank.bin"
            with census.SeedWriter(root) as writer:
                fixture(writer)
                self.assertEqual(len(writer.stage_index), 2)
                self.assertEqual(writer.program_count, 2)
                self.assertFalse(hasattr(writer, "stage_list"))
                writer.publish(bank)
            original = bank.read_bytes()
            with census.SeedWriter(root) as writer:
                with self.assertRaises(ValueError):
                    writer.publish(bank)
            self.assertEqual(bank.read_bytes(), original)
            with census.SeedWriter(root) as writer:
                fixture(writer)
                original_replace = Path.replace
                def fail(path, destination):
                    if destination == bank: raise PermissionError("sharing denied")
                    return original_replace(path, destination)
                with patch.object(Path, "replace", fail):
                    with self.assertRaises(PermissionError): writer.publish(bank)
            self.assertEqual(bank.read_bytes(), original)
            self.assertEqual(list(root.iterdir()), [bank])

    def test_census_bounds_reject_truncated_headers_before_publishing(self):
        with self.assertRaises(ValueError):
            list(census.bnsh_programs(b"BNSH" + b"\0" * 100, {}))


class RendererUpdateTests(unittest.TestCase):
    def test_renderer_only_update_keeps_game_exe_image_save_and_their_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); folder = root / "jogo"; folder.mkdir()
            ready = root / "ready"; ready.mkdir()
            romfs = root / "romfs"
            for name in ("System", "Pack"): (romfs / name).mkdir(parents=True)
            for name in ("AkynoLeyend.exe", "image.bin", "AkynoLeyend.dll"): (folder / name).write_bytes(name.encode())
            (folder / "user/save").mkdir(parents=True); save = folder / "user/save/keep"; save.write_bytes(b"save")
            dll = ready / "AkynoLeyend.dll"; dll.write_bytes(b"new generic renderer")
            write_json(ready / "renderer.json", {"source_sha256": "fixture", "binary_sha256": sha256(dll)})
            old = {"schema": 1, "project": "AkynoLeyend", "version": __version__, "host_revision": HOST_REVISION,
                   "game_build_id": "e0f3ccfa", "romfs": str(romfs),
                   "files": {name: sha256(folder / name) for name in ("AkynoLeyend.exe", "image.bin", "AkynoLeyend.dll")}}
            write_json(folder / "AkynoLeyend-build.json", old)
            before = {p: p.read_bytes() for p in (folder / "AkynoLeyend.exe", folder / "image.bin", save)}
            with patch("akynoleyend.shader_prepare.renderer_prebuilt", return_value=dll):
                updated = _update_renderer(folder, old, lambda _: None)
            for p, data in before.items(): self.assertEqual(p.read_bytes(), data)
            self.assertEqual(updated["version"], __version__)
            self.assertEqual(verify_build(folder)["files"], updated["files"])
            self.assertEqual((folder / "AkynoLeyend.dll").read_bytes(), dll.read_bytes())
            # A denied final manifest write rolls the DLL and metadata back.
            (folder / "AkynoLeyend.dll").write_bytes(b"AkynoLeyend.dll")
            write_json(folder / "AkynoLeyend-build.json", old)
            real_write = write_json
            def fail_manifest(path, value):
                if value != old: raise PermissionError("manifest write denied")
                return real_write(path, value)
            with patch("akynoleyend.shader_prepare.renderer_prebuilt", return_value=dll), \
                    patch("akynoleyend.shader_prepare.write_json", side_effect=fail_manifest):
                with self.assertRaises(ProjectError): _update_renderer(folder, old, lambda _: None)
            self.assertEqual(verify_build(folder), old)
            self.assertEqual(read_json(folder / "AkynoLeyend-build.json"), old)
            with self.assertRaisesRegex(ProjectError, "ABI"):
                _update_renderer(folder, dict(old, version="unknown"), lambda _: None)

    def test_real_census_subprocess_is_cached_and_input_files_are_preserved(self):
        try:
            import zstandard
        except ImportError:
            self.skipTest("zstandard unavailable")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); folder = root / "jogo"; folder.mkdir()
            ready = root / "ready"; ready.mkdir()
            work = root / "work"; romfs = root / "romfs"
            for name in ("System", "Pack", "Shader"): (romfs / name).mkdir(parents=True)
            sarc = bytearray(32); sarc[:4] = b"SARC"; struct.pack_into("<I", sarc, 12, 32)
            (romfs / "Pack/ZsDic.pack.zs").write_bytes(zstandard.ZstdCompressor().compress(sarc))
            data = bytearray(2048); data[:4] = b"BNSH"; data[12:14] = b"\xff\xfe"
            struct.pack_into("<I", data, 28, len(data)); data[96:100] = b"grsc"
            struct.pack_into("<IQ", data, 124, 1, 192); struct.pack_into("<Q", data, 208, 256)
            struct.pack_into("<Q", data, 264, 400)
            struct.pack_into("<QQII", data, 408, 512, 1024, 128, 216)
            data[512:516] = b"\x34\x12\x76\x98"
            data[1024:1152] = bytes(range(128))
            source = romfs / "Shader/fixture.bfsha"; source.write_bytes(data)
            for name in ("AkynoLeyend.exe", "image.bin", "AkynoLeyend.dll"): (folder / name).write_bytes(name.encode())
            dll = ready / "AkynoLeyend.dll"; dll.write_bytes(b"new generic renderer")
            write_json(ready / "renderer.json", {"source_sha256": "fixture", "binary_sha256": sha256(dll)})
            manifest = {"schema": 1, "project": "AkynoLeyend", "version": __version__, "host_revision": HOST_REVISION,
                        "game_build_id": "e0f3ccfa", "romfs": str(romfs),
                        "files": {name: sha256(folder / name) for name in ("AkynoLeyend.exe", "image.bin", "AkynoLeyend.dll")}}
            write_json(folder / "AkynoLeyend-build.json", manifest)
            with patch("akynoleyend.shader_prepare.renderer_prebuilt", return_value=dll):
                self.assertEqual(prepare_shaders(folder, work, start_game=False, report=lambda _: None), 0)
                bank = folder / "AkynoLeyend_shaders.bin"
                self.assertEqual(bank.read_bytes()[:16], b"HKSEED01" + struct.pack("<II", 1, 1))
                before = bank.read_bytes()
                with patch("akynoleyend.shader_prepare.run") as census_process, \
                        patch("akynoleyend.shader_prepare.sha256", wraps=sha256) as hashing:
                    self.assertEqual(prepare_shaders(folder, work, start_game=False, report=lambda _: None), 0)
                    census_process.assert_not_called()
                    self.assertFalse(any(Path(call.args[0]) in {bank, work/'shaders'/bank.name}
                                         for call in hashing.call_args_list))
                self.assertEqual(bank.read_bytes(), before)
                marker = work / "shaders/seed.json"
                real_read = Path.read_text
                def deny(path, *args, **kwargs):
                    if path == marker: raise PermissionError(13, "index blocked", str(path))
                    return real_read(path, *args, **kwargs)
                with patch.object(Path, "read_text", deny), patch("akynoleyend.shader_prepare.run") as census_process:
                    with self.assertRaises(ProjectError):
                        prepare_shaders(folder, work, start_game=False, report=lambda _: None)
                    census_process.assert_not_called()
            self.assertEqual(source.read_bytes(), data)
            self.assertFalse((folder / "diagnosticos").exists())


if __name__ == "__main__": unittest.main()
