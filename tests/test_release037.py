"""Regressions from the real 0.3.6 build and inaccessible RomFS report."""
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from akynoleyend.errors import ProjectError
from akynoleyend.romfs import audit_romfs, require_romfs
from akynoleyend.timing import BuildTimings
from akynoleyend.prebuilt import renderer_identity, renderer_prebuilt
from akynoleyend.files import sha256
from akynoleyend.build import cached_file, prepare_inputs
from akynoleyend.config import BuildRequest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "nx2"))
import chunks
from test_chunks import SyntheticLifter


class Release037Tests(unittest.TestCase):
    def test_incomplete_input_is_rejected_before_a_second_large_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d);nup = root / "own.nup";nup.write_bytes(b"synthetic input")
            request = BuildRequest(output=root / "out", work=root / "work", tools=root / "tools", nup=nup)
            private = request.work / "inputs" / sha256(nup);private.mkdir(parents=True)
            with patch("akynoleyend.build.verify_nup"), patch("akynoleyend.build.run") as child:
                with self.assertRaisesRegex(ProjectError, "nao foi iniciada uma segunda extracao"):
                    prepare_inputs(request, {}, lambda _: None)
                child.assert_not_called()
            self.assertTrue(private.is_dir())
    def test_inaccessible_extraction_marker_does_not_become_a_cache_miss(self):
        with patch.object(Path, "stat", side_effect=PermissionError(errno.EACCES, "denied")):
            with self.assertRaisesRegex(ProjectError, "cache inacessivel"):
                cached_file(Path("work/inputs/input.json"))
        with patch.object(Path, "stat", side_effect=FileNotFoundError()):
            self.assertFalse(cached_file(Path("work/inputs/input.json")))
    def test_prebuilt_renderer_requires_matching_sources_config_and_binary(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d);deps = root / "deps";ready = root / "prebuilt"
            ready.mkdir();(root / "gpu").mkdir()
            source = root / "gpu/test.cpp";source.write_text("int renderer_version = 1;\n")
            binary = ready / "AkynoLeyend.dll";binary.write_bytes(b"generic test renderer")
            env = {"OCARINA_TARGET": "windows-gnu", "RX_RELEASE": "1"}
            manifest = {"schema": 1, "source_sha256": renderer_identity(root, deps),
                        "binary_sha256": sha256(binary),
                        "config": {"target": "windows-gnu", "march": "x86-64-v3", "release": "1"}}
            (ready / "renderer.json").write_text(json.dumps(manifest))
            resolve = lambda e=env: renderer_prebuilt(root, deps, ready, e, lambda _: None)
            self.assertEqual(resolve(), binary)
            self.assertIsNone(resolve(dict(env, OCARINA_BUILD_RENDERER="1")))
            self.assertIsNone(resolve(dict(env, OCARINA_TARGET="linux")))
            source.write_text("int renderer_version = 2;\n")
            self.assertIsNone(resolve())
            source.write_text("int renderer_version = 1;\n")
            binary.write_bytes(b"tampered renderer")
            self.assertIsNone(resolve())

    def test_prebuilt_malformed_manifest_falls_back_without_loading_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d);(root / "AkynoLeyend.dll").write_bytes(b"x")
            (root / "renderer.json").write_text("[]")
            self.assertIsNone(renderer_prebuilt(root, root, root, {}, lambda _: None))

    def test_access_denied_is_not_reported_as_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            original = Path.stat
            def denied(path, *args, **kwargs):
                if path == root / "System":
                    raise PermissionError(errno.EACCES, "Access denied", str(path))
                return original(path, *args, **kwargs)
            with patch.object(Path, "stat", denied):
                report = "\n".join(audit_romfs(root))
                self.assertIn("Pasta System: INACESSIVEL", report)
                self.assertNotIn("Pasta System: AUSENTE", report)
                with self.assertRaisesRegex(ProjectError, "RomFS inacessivel"):
                    require_romfs(root)

    def test_observed_times_include_a_failed_phase_and_keep_original_error(self):
        with tempfile.TemporaryDirectory() as d:
            timing = BuildTimings(Path(d), lambda _: None)
            self.assertEqual(timing.measure("inputs", lambda: 17), 17)
            failure = ValueError("compiler failed")
            def fail():
                raise failure
            with self.assertRaises(ValueError) as caught:
                timing.measure("compile", fail)
            self.assertIs(caught.exception, failure)
            phases = json.loads(timing.path.read_text())["phases"]
            self.assertEqual([(p["phase"], p["status"]) for p in phases],
                             [("inputs", "completed"), ("compile", "failed")])
            self.assertTrue(all(p["seconds"] >= 0 for p in phases))

    def test_new_smaller_chunks_preserve_bodies_and_saved_boundaries(self):
        class LargeLifter(SyntheticLifter):
            funcs = {0x80000000 + 4 * n: None for n in range(10)}
            def emit_function(self, address, texts):
                return super().emit_function(address, texts) + "/*" + "x" * (1 << 20) + "*/\n"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d);gen = root / "gen";meta = root / "image"
            with patch.dict(os.environ, {"OCARINA_CHUNK_MIB": "3"}), contextlib.redirect_stdout(io.StringIO()):
                files = chunks.write(LargeLifter(), str(gen), str(meta))
            before = {name: (gen / name).read_bytes() for name in files}
            self.assertGreater(len(files), 1)
            joined = b"".join(before.values())
            self.assertEqual(joined.count(b"void f_"), 10)
            with patch.dict(os.environ, {"OCARINA_CHUNK_MIB": "24"}), contextlib.redirect_stdout(io.StringIO()):
                again = chunks.write(LargeLifter(), str(gen), str(meta))
            self.assertEqual(files, again)
            self.assertEqual(before, {name: (gen / name).read_bytes() for name in again})

    def test_saved_single_chunk_is_not_implicitly_repartitioned(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d);gen = root / "gen";meta = root / "image"
            with contextlib.redirect_stdout(io.StringIO()):
                files = chunks.write(SyntheticLifter(), str(gen), str(meta))
            with patch.object(chunks.a64_lift, "CHUNK_BYTES", 80), contextlib.redirect_stdout(io.StringIO()):
                again = chunks.write(SyntheticLifter(), str(gen), str(meta))
                changed = chunks.write(SyntheticLifter(), str(gen), str(meta), rechunk=True)
            self.assertEqual(files, again)
            self.assertGreater(len(changed), len(files))

    def test_real_native_mirror_policy(self):
        compiler = shutil.which("c++") or shutil.which("clang++")
        if not compiler:
            self.skipTest("no native C++ compiler")
        with tempfile.TemporaryDirectory() as d:
            binary = Path(d) / ("policy.exe" if os.name == "nt" else "policy")
            built = subprocess.run([compiler, "-std=c++20", "-Wall", "-Wextra", "-Werror",
                                    "-I" + str(ROOT / "gpu/vk"), str(ROOT / "tests/native/mirror_policy_test.cpp"),
                                    "-o", str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stderr)
            child = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
            self.assertEqual(child.returncode, 0, child.stderr)
