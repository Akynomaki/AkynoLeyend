"""A package's maintenance accepts only its verified ready renderer and never starts compiling it."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from akynoleyend.coherence import HOST_REVISION, PREVIOUS_HOST_SOURCES
from akynoleyend.config import MANIFEST, ROOT
from akynoleyend.errors import ProjectError
from akynoleyend.files import read_json, sha256, write_json
from akynoleyend.maintenance import maintain_build, require_ready_renderer
from akynoleyend.prebuilt import renderer_identity

ENV = {"OCARINA_TARGET": "windows-gnu", "RX_RELEASE": "1"}


def ready_renderer(tools, target="windows-gnu"):
    """A receipt made the way a release makes it: exact sources, dependencies, configuration and binary."""
    for name in ("vulkan", "spirv", "vma"):
        (tools / "deps" / name / "include").mkdir(parents=True, exist_ok=True)
    (tools / "deps/vulkan/include/vulkan.h").write_bytes(b"// pinned headers\n")
    prebuilt = tools / "prebuilt"
    prebuilt.mkdir(parents=True, exist_ok=True)
    (prebuilt / "AkynoLeyend.dll").write_bytes(b"MZ generic renderer")
    write_json(prebuilt / "renderer.json", {
        "schema": 1, "release": "fixture",
        "config": {"target": target, "march": "x86-64-v3", "release": "1"},
        "source_sha256": renderer_identity(ROOT, tools / "deps"),
        "binary_sha256": sha256(prebuilt / "AkynoLeyend.dll")})
    return prebuilt


def installed_test3(root):
    folder, work, romfs = root / "jogo", root / "work", root / "romfs"
    folder.mkdir()
    for n in ("Pack", "System"):
        (romfs / n).mkdir(parents=True)
    (folder / "user").mkdir()
    (folder / "user/save.dat").write_bytes(b"keep-save")
    for n in ("AkynoLeyend.exe", "AkynoLeyend.dll", "image.bin"):
        (folder / n).write_bytes(n.encode())
    old = {"schema": 1, "project": "AkynoLeyend", "version": "0.4.3-test.3", "host_revision": HOST_REVISION,
           "source_sha256": next(iter(PREVIOUS_HOST_SOURCES["0.4.3-test.3"])), "game_build_id": "e0f3ccfa",
           "romfs": str(romfs),
           "files": {n: sha256(folder / n) for n in ("AkynoLeyend.exe", "AkynoLeyend.dll", "image.bin")}}
    write_json(folder / MANIFEST, old)
    gen = work / "sa/gen"
    gen.mkdir(parents=True)
    for n in ("a64_table.c", "a64_hooks.c", "a64_suyu.c", "a64_stubs.c", "hos_image.c", "nvn2_exports.c", "code_000.c"):
        (gen / n).write_text("/* generated */")
    (gen / "akyno-frame-step-v1").touch()   # (r10: a work whose step hook was checked; only the relink runs)
    (gen / "akyno-panel-hooks-r13-v5").touch()   # (r13: and whose panel hooks are in: tests/test_r13_*.py cover that step)
    image = work / "sa/image/image.bin"
    image.parent.mkdir()
    image.write_bytes((folder / "image.bin").read_bytes())
    write_json(work / "build-request.json", {"game_build_id": "e0f3ccfa", "output": str(folder)})
    return folder, work, old


class ReadyRendererTests(unittest.TestCase):
    def maintain(self, root, folder, work, summary=True):
        calls = []

        def build(command, *_):
            calls.append(command)
            built = work / "sa/build"
            built.mkdir(exist_ok=True)
            for n in ("AkynoLeyend.exe", "AkynoLeyend.dll"):
                (built / n).write_bytes(b"new-" + n.encode())
            write_json(work / "logs/compile-summary.json",
                       {"schema": 1, "renderer_prebuilt": summary, "compiled": 34})
        with patch("akynoleyend.maintenance.require_tools", return_value=dict(ENV)), \
             patch("akynoleyend.maintenance.run", side_effect=build), \
             patch("akynoleyend.build.renderer_identity", return_value="generic-test-renderer"):
            try:
                return maintain_build(folder, work, root / "tools", report=lambda _: None), calls
            except ProjectError as error:
                return error, calls

    def assert_untouched(self, folder, old):
        self.assertEqual(read_json(folder / MANIFEST), old)
        self.assertEqual((folder / "user/save.dat").read_bytes(), b"keep-save")
        for n in old["files"]:
            self.assertEqual((folder / n).read_bytes(), n.encode())

    def test_compatible_ready_renderer_is_used_and_no_renderer_unit_is_compiled(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder, work, _ = installed_test3(root)
            ready_renderer(root / "tools")
            updated, calls = self.maintain(root, folder, work)
            self.assertIsInstance(updated, dict)
            self.assertEqual(len(calls), 1)
            # The child build sees the same verified prebuilt and is told not to build the renderer.
            self.assertTrue(read_json(work / "logs/compile-summary.json")["renderer_prebuilt"])

    def test_mismatched_receipt_refuses_before_any_compiler_starts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder, work, old = installed_test3(root)
            prebuilt = ready_renderer(root / "tools")
            receipt = read_json(prebuilt / "renderer.json")
            receipt["source_sha256"] = "0" * 64
            write_json(prebuilt / "renderer.json", receipt)
            error, calls = self.maintain(root, folder, work)
            self.assertIsInstance(error, ProjectError)
            self.assertIn("renderizador pronto", str(error))
            self.assertEqual(calls, [])
            self.assert_untouched(folder, old)

    def test_other_sdk_dependencies_refuse_before_any_compiler_starts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder, work, old = installed_test3(root)
            ready_renderer(root / "tools")
            (root / "tools/deps/vulkan/include/vulkan.h").write_bytes(b"// another SDK\n")
            error, calls = self.maintain(root, folder, work)
            self.assertIsInstance(error, ProjectError)
            self.assertEqual(calls, [])
            self.assert_untouched(folder, old)

    def test_missing_or_altered_binary_and_forced_source_build_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            tools = Path(d) / "tools"
            prebuilt = ready_renderer(tools)
            self.assertEqual(require_ready_renderer(ROOT, tools, dict(ENV)), prebuilt / "AkynoLeyend.dll")
            for environment in (dict(ENV, OCARINA_BUILD_RENDERER="1"), dict(ENV, RX_VK_ONLY="1"),
                                dict(ENV, OCARINA_TARGET="other")):
                with self.assertRaises(ProjectError):
                    require_ready_renderer(ROOT, tools, environment)
            (prebuilt / "AkynoLeyend.dll").write_bytes(b"MZ altered")
            with self.assertRaises(ProjectError):
                require_ready_renderer(ROOT, tools, dict(ENV))
            (prebuilt / "AkynoLeyend.dll").unlink()
            with self.assertRaises(ProjectError):
                require_ready_renderer(ROOT, tools, dict(ENV))

    def test_build_that_did_not_use_the_ready_renderer_is_not_published(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder, work, old = installed_test3(root)
            ready_renderer(root / "tools")
            error, calls = self.maintain(root, folder, work, summary=False)
            self.assertIsInstance(error, ProjectError)
            self.assertEqual(len(calls), 1)
            self.assert_untouched(folder, old)


if __name__ == "__main__":
    unittest.main()
