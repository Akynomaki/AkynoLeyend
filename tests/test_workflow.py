import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from akynoleyend.build import check_output, prepare_inputs, publish, verify_version
from akynoleyend.build_support import object_key
from akynoleyend.config import MANIFEST, BuildRequest, compile_jobs
from akynoleyend.environment import runtime_environment
from akynoleyend.errors import ProjectError
from akynoleyend.files import workspace_lock
from akynoleyend.launch import launch, verify_build
from akynoleyend.process import run

ROOT = Path(__file__).resolve().parent.parent


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="akynoleyend-test-")
        self.folder = Path(self.temporary.name)
        self.exefs = self.folder / "exefs"
        self.romfs = self.folder / "romfs"
        self.exefs.mkdir()
        self.romfs.mkdir()
        (self.romfs / "System").mkdir()
        (self.romfs / "Pack").mkdir()
        header = bytearray(0x100)
        header[:4] = b"NSO0"
        header[0x40:0x44] = bytes.fromhex("e0f3ccfa")
        (self.exefs / "main").write_bytes(header)

    def tearDown(self):
        self.temporary.cleanup()

    def request(self, **overrides):
        values = dict(
            output=self.folder / "out",
            work=self.folder / "work",
            tools=self.folder / "tools",
            exefs=self.exefs,
            romfs=self.romfs,
        )
        values.update(overrides)
        return BuildRequest(**values)

    def test_launch_before_first_build_has_actionable_error(self):
        with self.assertRaisesRegex(ProjectError, "Execute Compilar.cmd"):
            verify_build(self.folder / "not-built")

    def test_low_memory_allows_one_compile(self):
        # (0.4.5: 0.4 GiB a typical unit, 1 GiB left to the system, at most 8; the memory gate weighs each unit)
        self.assertEqual(compile_jobs(None, 4 << 30, 32), 7)
        self.assertEqual(compile_jobs(None, 2 << 30, 32), 2)
        self.assertEqual(compile_jobs(None, 1 << 30, 32), 1)
        self.assertEqual(compile_jobs(None, 16 << 30, 32), 8)
        self.assertEqual(compile_jobs(None, 128 << 30, 2), 2)
        self.assertEqual(compile_jobs(None, 128 << 30, 32), 8)
        self.assertEqual(compile_jobs(None, 0, 32), 1)
        with self.assertRaises(ProjectError):
            compile_jobs(0)

    def test_build_lock_is_exclusive_and_reusable(self):
        work = self.folder / "locked-work"
        with workspace_lock(work):
            with self.assertRaises(ProjectError):
                with workspace_lock(work):
                    self.fail("Concurrent build acquired the workspace")
        with workspace_lock(work):
            pass

    def test_original_profile_does_not_inherit_experiments(self):
        original = {
            "PATH": "tools",
            "TOTK_PIPE_SYNC": "1",
            "RX_VK_ASTC_RGBA8": "1",
            "HOS_NO_SDL": "1",
            "VK_INSTANCE_LAYERS": "VK_LAYER_KHRONOS_validation",
        }
        result = runtime_environment(original, "original")
        self.assertEqual(result, {"PATH": "tools", "RX_BACKEND": "vulkan"})
        self.assertEqual(original["RX_VK_ASTC_RGBA8"], "1")

    def test_8gb_profile_preserves_compression_and_mirrors(self):
        result = runtime_environment({}, "8gb")
        self.assertEqual(result["RX_VK_MIRROR_MB"], "1024")
        self.assertNotIn("RX_VK_MIRROR", result)
        self.assertNotIn("RX_VK_ASTC_RGBA8", result)
        self.assertNotIn("RX_VK_ASTC_CPU", result)
        self.assertNotIn("RX_VK_PIPE_WAIT", result)

    def test_motion_comparison_keeps_pipeline_wait_and_temporal_clamp_off(self):
        inherited = {"RX_VK_TAAU_CLAMP": "1", "RX_VK_PIPE_SKIP": "1", "RX_VK_OOT_EXPOSURE": "3"}
        result = runtime_environment(inherited, "nitido")
        self.assertEqual(result["RX_VK_TAAU_KEYS"], "fd029a317a9a4b94")
        self.assertEqual(result["HOS_DYNRES"], "0")
        self.assertNotIn("RX_VK_TAAU_CLAMP", result)
        self.assertNotIn("RX_VK_PIPE_SKIP", result)
        self.assertNotIn("RX_VK_OOT_EXPOSURE", result)
        self.assertEqual(runtime_environment({}, "original"), {"RX_BACKEND": "vulkan"})

    def test_diagnostic_validation_is_separate(self):
        self.assertNotIn("RX_VK_VALIDATION", runtime_environment({}, "original"))
        self.assertEqual(runtime_environment({}, "original", True)["RX_VK_VALIDATION"], "1")
        self.assertNotIn("RX_VK_FRAMELOG", runtime_environment({}, "original", True))

    def test_output_cannot_cover_input_data(self):
        with self.assertRaises(ProjectError):
            self.request(output=self.folder).validate()
        self.request().validate()

    def test_wrong_and_truncated_game_versions_fail_early(self):
        self.assertTrue(verify_version(self.exefs).startswith("e0f3ccfa"))
        (self.exefs / "main").write_bytes(b"NSO0")
        with self.assertRaises(ProjectError):
            verify_version(self.exefs)
        (self.exefs / "main").write_bytes(b"NSO0" + bytes(0x100))
        with self.assertRaises(ProjectError):
            verify_version(self.exefs)

    def test_unowned_output_is_preserved(self):
        output = self.folder / "out"
        output.mkdir()
        old = output / "my-file.txt"
        old.write_text("keep")
        with self.assertRaises(ProjectError):
            check_output(output)
        self.assertEqual(old.read_text(), "keep")

    def test_module_preparation_uses_a_private_copy(self):
        original = (self.exefs / "main").read_bytes()
        request = self.request()
        exefs, romfs = prepare_inputs(request, dict(os.environ), lambda _: None)
        self.assertNotEqual(exefs, self.exefs)
        self.assertEqual(romfs, self.romfs)
        self.assertEqual((self.exefs / "main").read_bytes(), original)
        self.assertEqual((exefs / "main").read_bytes(), original)

    def test_compiler_and_include_changes_invalidate_cached_object(self):
        compiler = self.folder / "compiler"
        source = self.folder / "source.c"
        compiler.write_bytes(b"compiler-one")
        source.write_text("int value;")
        initial = object_key(str(compiler), str(source), ["-Ia"], b"header")
        self.assertNotEqual(initial, object_key(str(compiler), str(source), ["-Ib"], b"header"))
        compiler.write_bytes(b"a-different-compiler")
        self.assertNotEqual(initial, object_key(str(compiler), str(source), ["-Ia"], b"header"))

    def test_publish_and_tamper_detection(self):
        request = self.request()
        built = request.work / "sa/build"
        image = request.work / "sa/image"
        built.mkdir(parents=True)
        image.mkdir(parents=True)
        (built / "AkynoLeyend.exe").write_bytes(b"synthetic-executable")
        (built / "AkynoLeyend.dll").write_bytes(b"synthetic-renderer")
        (image / "image.bin").write_bytes(b"synthetic-image")
        with patch("akynoleyend.build.source_identity", return_value="test-source"):
            publish(request, self.romfs, "e0f3ccfa", 1, time.monotonic())
        self.assertEqual(verify_build(request.output)["source_sha256"], "test-source")
        self.assertEqual(launch(request.output, dry_run=True), 0)
        (request.output / "AkynoLeyend.dll").write_bytes(b"stale-renderer")
        with self.assertRaises(ProjectError):
            verify_build(request.output)

    def test_incomplete_build_does_not_publish_a_manifest(self):
        request = self.request()
        with self.assertRaises(ProjectError):
            publish(request, self.romfs, "e0f3ccfa", 1, time.monotonic())
        self.assertFalse((request.output / MANIFEST).exists())

    def test_subprocess_preserves_spaces_and_reports_failure(self):
        log = self.folder / "a folder/log.txt"
        run(
            [sys.executable, "-c", "import sys; print(sys.argv[1])", "a b $ literal"],
            self.folder,
            os.environ,
            log,
            lambda _: None,
        )
        self.assertIn("a b $ literal", log.read_text())
        with self.assertRaisesRegex(ProjectError, "codigo 7"):
            run(
                [sys.executable, "-c", "print('failure detail'); raise SystemExit(7)"],
                self.folder,
                os.environ,
                log,
                lambda _: None,
            )
        self.assertIn("failure detail", log.read_text())


class ArchiveTests(unittest.TestCase):
    def test_archive_path_cannot_escape_destination(self):
        specification = importlib.util.spec_from_file_location("test_nup", ROOT / "nx2/nup.py")
        reader = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(reader)

        class FakeArchive:
            def walk(self, _):
                yield "../../outside.txt", (0, 0, 4, 0)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                reader.extract(FakeArchive(), {"exefs": 0, "romfs": 0}, directory, "exefs")
            self.assertFalse(list(Path(directory).iterdir()))


if __name__ == "__main__":
    unittest.main()
