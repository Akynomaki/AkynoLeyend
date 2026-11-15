"""Verify an r9 maintenance update touches only the old resolution guards."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from akynoleyend.build_support import object_key, require_cached_game_objects
from akynoleyend.errors import ProjectError
from akynoleyend.maintenance import upgrade_output_sites
from nx2 import upgrade_output
from nx2.oot_output_size import (
    DISPLAY_EDITS, DISPLAY_SETTINGS, OUT_DECL, OUT_EDITS, OUTPUT_SITES_STAMP,
    PREVIOUS_OUTPUT_SITES_STAMP, SIZE_CHANGED, extended_output_emitted,
)


class IncrementalOutputTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="akyno-output-[cache]-")
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)
        self.gen = self.work / "sa/gen"
        self.built = self.work / "sa/build"
        self.cache = self.work / "objcache"
        self.gen.mkdir(parents=True)
        (self.built / "obj").mkdir(parents=True)
        self.cache.mkdir()
        self.paths = []
        for index, (_, current) in enumerate(OUT_EDITS):
            path = self.gen / ("code_hot_0.c" if index == 1 else f"code_{index:03d}.c")
            original = current.replace(SIZE_CHANGED, "hos_output_size(0) != 2560")
            path.write_text('#include "a64.h"\n' + OUT_DECL + original, newline="\r\n")
            self.paths.append(path)
        path = self.gen / "code_090.c"
        body = "\n".join(old for old, _ in DISPLAY_EDITS)
        path.write_text('#include "a64.h"\n' + DISPLAY_SETTINGS + "\n" + body + "\n}\n", newline="\r\n")
        self.paths.append(path)
        native = upgrade_output.native
        for change in (patch.object(native, "OBJ_CACHE", str(self.cache)),
                       patch.object(native.toolchain, "find", return_value=sys.executable)):
            change.start()
            self.addCleanup(change.stop)
        self.jobs = upgrade_output.translated_jobs(self.gen, self.built)
        self.keys = {}
        for source, (cc, _, output, flags, deps) in self.jobs.items():
            if not source.is_file():
                source.write_text("/* fixture */")
            key = object_key(cc, str(source), flags, deps)
            self.keys[source] = key
            Path(output).write_bytes(b"original object")
            Path(output + ".sha256").write_text(key)
        self.compiled = []

    def compile(self, job):
        cc, source, output, flags, deps = job
        self.compiled.append(Path(source))
        Path(output).write_bytes(b"updated object")
        upgrade_output.native.cache_put(output, object_key(cc, source, flags, deps))
        return source, 0, None

    def upgrade_child(self, command, *_):
        staging = Path(command[command.index("--staging") + 1])
        upgrade_output.upgrade(self.work, staging, workers=1)

    def test_refreshes_the_changed_guards_and_preserves_previous_objects(self):
        original = [path.read_bytes() for path in self.paths]
        with patch("akynoleyend.maintenance.run", side_effect=self.upgrade_child), \
             patch.object(upgrade_output.native, "compile_one", side_effect=self.compile):
            with upgrade_output_sites(self.work, {}, 1, lambda _: None):
                require_cached_game_objects(self.jobs.values(), self.cache)
                self.assertTrue(extended_output_emitted(self.gen))
        changed = [path for path, old in zip(self.paths, original) if path.read_bytes() != old]
        self.assertCountEqual(changed, [self.paths[1], self.paths[2], self.paths[-1]])
        self.assertCountEqual([p.name for p in self.compiled], [p.name for p in changed])
        for path in changed:
            if path == self.paths[-1]:
                self.assertIn(b"/* display settings: scaler reference */", path.read_bytes())
            else:
                self.assertIn(SIZE_CHANGED.encode(), path.read_bytes())
            self.assertNotIn(b"\n", path.read_bytes().replace(b"\r\n", b""))
            self.assertEqual((self.cache / (self.keys[path] + ".o")).read_bytes(), b"original object")

    def test_missing_cache_aborts_before_a_compile(self):
        original = [path.read_bytes() for path in self.paths]
        Path(self.jobs[self.paths[-1]][2]).unlink()
        with patch("akynoleyend.maintenance.run", side_effect=self.upgrade_child), \
             patch.object(upgrade_output.native, "compile_one", side_effect=self.compile):
            with self.assertRaisesRegex(ProjectError, "Cache da unidade"):
                with upgrade_output_sites(self.work, {}, 1, lambda _: None):
                    self.fail("missing cache was accepted")
        self.assertFalse(self.compiled)
        self.assertFalse(extended_output_emitted(self.gen))
        self.assertEqual(original, [path.read_bytes() for path in self.paths])

    def test_failed_link_restores_generated_sources_objects_and_marker(self):
        original = [path.read_bytes() for path in self.paths]
        with patch("akynoleyend.maintenance.run", side_effect=self.upgrade_child), \
             patch.object(upgrade_output.native, "compile_one", side_effect=self.compile):
            with self.assertRaisesRegex(ProjectError, "link failed"):
                with upgrade_output_sites(self.work, {}, 1, lambda _: None):
                    target = Path(self.jobs[self.paths[1]][2])
                    target.unlink()
                    target.write_bytes(b"relinked object")
                    target.with_suffix(".o.sha256").write_text("relinked")
                    raise ProjectError("link failed")
        self.assertFalse(extended_output_emitted(self.gen))
        self.assertEqual(original, [path.read_bytes() for path in self.paths])
        self.assertEqual(target.read_bytes(), b"original object")
        require_cached_game_objects(self.jobs.values(), self.cache)

    def test_failed_migration_keeps_previous_720p_support(self):
        previous = self.gen / PREVIOUS_OUTPUT_SITES_STAMP
        previous.touch()
        self.assertTrue(extended_output_emitted(self.gen))
        with patch("akynoleyend.maintenance.run", side_effect=self.upgrade_child), \
             patch.object(upgrade_output.native, "compile_one", side_effect=self.compile):
            with self.assertRaisesRegex(ProjectError, "publish failed"):
                with upgrade_output_sites(self.work, {}, 1, lambda _: None):
                    self.assertTrue((self.gen / OUTPUT_SITES_STAMP).is_file())
                    raise ProjectError("publish failed")
        self.assertTrue(previous.is_file())
        self.assertFalse((self.gen / OUTPUT_SITES_STAMP).exists())
        self.assertTrue(extended_output_emitted(self.gen))
