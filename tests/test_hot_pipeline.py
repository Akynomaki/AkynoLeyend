"""Run the orchestration through lift, optional splitting, compilation and publication."""

import contextlib
import importlib.util
import io
import tempfile
import os
import unittest

from akynoleyend.files import read_json
from pathlib import Path
from unittest.mock import patch

from akynoleyend.build import build
from akynoleyend.config import BuildRequest
from akynoleyend.hot import configure_hot, has_fresh_hot_source
from akynoleyend.launch import verify_build

ROOT = Path(__file__).resolve().parent.parent


class HotPipelineTests(unittest.TestCase):
    def scenario(self, profile, hot, stale):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            exefs, romfs = folder / "exefs", folder / "romfs"
            exefs.mkdir()
            romfs.mkdir()
            (romfs / "System").mkdir()
            (romfs / "Pack").mkdir()
            main = bytearray(0x100)
            main[:4] = b"NSO0"
            main[0x40:0x44] = bytes.fromhex("e0f3ccfa")
            (exefs / "main").write_bytes(main)
            request = BuildRequest(
                folder / "out", folder / "work", folder / "tools", exefs=exefs, romfs=romfs
            )
            if profile:
                names = folder / "profiles/e0f3ccfa/hot_funcs.txt"
                names.parent.mkdir(parents=True)
                names.write_text("f_80000000\n")
            calls, messages = [], []

            def memory_after_lift():
                self.assertIn(calls[-1], ("lift.py", "split_hot.py"))
                return 16 << 30

            def run(command, cwd, environment, log, report):
                script = Path(next(arg for arg in command[1:] if not arg.startswith("-"))).name
                calls.append(script)
                generated = request.work / "sa/gen"
                if script == "lift.py":
                    self.assertEqual("A64_HOT_FUNCS" in environment, profile)
                    generated.mkdir(parents=True)
                    (generated / "code_000.c").write_text("/* synthetic normal unit */\n")
                    if hot:
                        (generated / "code_hot.c").write_text(
                            '#include "a64.h"\nvoid f_80000000(Ctx *__restrict A64_NOESC c) {\n}\n'
                        )
                    if stale:
                        (generated / "code_hot_99.c").write_text("stale duplicate")
                        (generated / "code_hot.c.whole").write_text("stale whole")
                elif script == "split_hot.py":
                    spec = importlib.util.spec_from_file_location(
                        "split_test", ROOT / "nx2/split_hot.py"
                    )
                    splitter = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(splitter)
                    with contextlib.redirect_stdout(io.StringIO()):
                        splitter.split(str(generated), 2)
                elif script == "build.py":
                    if not hot:
                        self.assertFalse(list(generated.glob("code_hot*.c*")))
                        self.assertIn(
                            "compilando os arquivos normais",
                            (request.work / "logs/split.log").read_text(),
                        )
                    built, image = request.work / "sa/build", request.work / "sa/image"
                    built.mkdir(parents=True)
                    image.mkdir(parents=True)
                    for name in ("AkynoLeyend.exe", "AkynoLeyend.dll"):
                        (built / name).write_bytes(b"synthetic binary")
                    (image / "image.bin").write_bytes(b"synthetic image")
                else:
                    self.fail(script)

            with (
                patch("akynoleyend.build.ROOT", folder),
                patch("akynoleyend.build.require_tools", return_value={}),
                patch("akynoleyend.build.prepare_inputs", return_value=(exefs, romfs)),
                patch("akynoleyend.build.run", side_effect=run),
                patch("akynoleyend.build.source_identity", return_value="synthetic"),
                patch("akynoleyend.build.available_memory", side_effect=memory_after_lift),
            ):
                build(request, messages.append)
            self.assertEqual("split_hot.py" in calls, hot)
            self.assertIn("build.py", calls)
            self.assertEqual(verify_build(request.output)["source_sha256"], "synthetic")
            # (0.4.5: with 16 GiB free, one compiler a thread, at most 8; 4 was the old 3.5 GiB rule)
            jobs = verify_build(request.output)["jobs"]
            self.assertEqual(jobs, read_json(request.work / "build-request.json")["jobs"])
            self.assertGreater(jobs, 1 if (os.cpu_count() or 1) > 1 else 0)
            self.assertLessEqual(jobs, 8)
            self.assertTrue(any(line.startswith("@@done ") for line in messages))

    def test_without_profile_reaches_compilation_and_publication(self):
        self.scenario(profile=False, hot=False, stale=False)

    def test_without_hot_matches_discards_stale_pieces_and_compiles(self):
        self.scenario(profile=True, hot=False, stale=True)

    def test_hot_profile_produces_split_units_and_publishes(self):
        self.scenario(profile=True, hot=True, stale=False)

    def test_profile_missing_clears_old_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = {"A64_HOT_FUNCS": "untrusted", "A64_HOT_CHUNK": "1"}
            configure_hot(Path(directory), environment)
            self.assertEqual(environment, {})

    def test_normal_sources_are_preserved_when_stale_hot_files_are_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory)
            for name in ("code_000.c", "code_hot_notes.c", "code_hot_7.c", "code_hot.c.whole"):
                (generated / name).write_text(name)
            self.assertFalse(has_fresh_hot_source(generated))
            self.assertTrue((generated / "code_000.c").exists())
            self.assertTrue((generated / "code_hot_notes.c").exists())
            self.assertFalse((generated / "code_hot_7.c").exists())
