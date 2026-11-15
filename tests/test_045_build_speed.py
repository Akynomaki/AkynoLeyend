"""0.4.5: compilers by measured memory, longest first; the .nup written directly and decompressed once."""

import importlib.util
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import zstandard

from akynoleyend import compile_plan
from akynoleyend.compile_plan import GIB, MIB, MemoryGate, compile_slots, order, unit_peak
from akynoleyend.config import compile_jobs

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("speed_nup", ROOT / "nx2/nup.py")
nup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nup)


class SlotTests(unittest.TestCase):
    def test_a_16_gb_pc_with_8_gib_free_compiles_on_every_thread(self):
        # the r13c log: 7.7 GiB free, 6 threads, 1 process (3.5 GiB set aside for each)
        self.assertEqual(compile_jobs(None, int(7.7 * GIB), 6), 6)
        self.assertEqual(compile_jobs(None, int(8.85 * GIB), 6), 6)

    def test_little_memory_still_compiles_and_the_cap_holds(self):
        self.assertEqual(compile_slots(int(1.5 * GIB), 6), 1)
        self.assertEqual(compile_slots(0, 6), 1)
        self.assertEqual(compile_slots(2 * GIB, 6), 2)     # (2 - 1 reserved) / 0.4 a typical unit
        self.assertEqual(compile_slots(4 * GIB, 6), 6)
        self.assertEqual(compile_slots(128 * GIB, 32), compile_plan.MAX_SLOTS)
        self.assertEqual(compile_slots(128 * GIB, 2), 2)
        self.assertEqual(compile_jobs(3, 0, 1), 3)

    def test_hot_pieces_at_o2_weigh_more_than_ordinary_chunks(self):
        hot = unit_peak("code_hot_7.c", 9 * MIB, hot=True)
        chunk = unit_peak("code_087.c", 10 * MIB, hot=False)
        small = unit_peak("hos_main.c", 200 * 1024, hot=False)
        self.assertGreater(hot, unit_peak("code_044.c", 6 * MIB, hot=False))
        self.assertGreater(chunk, small)
        self.assertLess(small, GIB)


class OrderTests(unittest.TestCase):
    def test_known_times_first_then_size(self):
        sizes = {"gen/code_hot_4.c": 9 * MIB, "gen/code_hot_7.c": 9 * MIB, "gen/code_087.c": 10 * MIB,
                 "gen/code_044.c": 6 * MIB, "host/hos_main.c": MIB // 4}
        times = {"code_hot_7.c": 510, "code_087.c": 303, "code_hot_4.c": 70, "code_044.c": 11}
        self.assertEqual(order(list(sizes), sizes, times),
                         ["gen/code_hot_7.c", "gen/code_087.c", "gen/code_hot_4.c", "gen/code_044.c", "host/hos_main.c"])
        self.assertEqual(order(list(sizes), sizes, {})[0], "gen/code_087.c")   # no times: biggest first, as before

    def test_shipped_hint_names_the_slow_units(self):
        times = compile_plan.load_times(ROOT / "nx2/compile_hint.json")
        self.assertGreater(len(times), 200)
        slowest = sorted(times, key=lambda name: -times[name])[:3]
        self.assertIn("code_hot_7.c", slowest)

    def test_this_pcs_times_win_and_are_merged(self):
        with tempfile.TemporaryDirectory() as folder:
            hint = Path(folder, "hint.json")
            hint.write_text(json.dumps({"units": {"code_001.c": 10, "code_002.c": 99}}), encoding="utf-8")
            mine = Path(folder, "logs/compile-units.json")
            compile_plan.save_times(mine, {"code_001.c": 50.04})
            compile_plan.save_times(mine, {"code_003.c": 7})
            times = compile_plan.load_times(hint, mine)
            self.assertEqual(times, {"code_001.c": 50.0, "code_002.c": 99.0, "code_003.c": 7.0})
            self.assertEqual(compile_plan.load_times(Path(folder, "missing.json")), {})


class GateTests(unittest.TestCase):
    def test_one_unit_always_runs_even_above_the_budget(self):
        gate = MemoryGate(GIB)
        gate.acquire(5 * GIB)
        self.assertEqual(gate.running, 1)
        gate.release(5 * GIB)

    def test_a_unit_waits_until_its_peak_fits(self):
        gate = MemoryGate(4 * GIB, poll=0.01)
        gate.acquire(3 * GIB)
        started = threading.Event()

        def second():
            gate.acquire(2 * GIB)
            started.set()

        worker = threading.Thread(target=second)
        worker.start()
        time.sleep(0.1)
        self.assertFalse(started.is_set())
        gate.release(3 * GIB)
        self.assertTrue(started.wait(2))
        worker.join(2)
        self.assertEqual(gate.waits, 1)
        self.assertEqual(gate.peak_running, 1)
        gate.release(2 * GIB)

    def test_other_programs_taking_memory_hold_the_next_unit(self):
        free = [10 * GIB]
        gate = MemoryGate(16 * GIB, lambda: free[0], poll=0.01)
        gate.acquire(GIB)
        free[0] = int(1.5 * GIB)   # a game opened during the build: 1 GiB more would leave less than RESERVE
        self.assertFalse(gate._fits(GIB))
        free[0] = 8 * GIB
        self.assertTrue(gate._fits(GIB))
        gate.release(GIB)

    def test_a_free_slot_takes_the_first_unit_that_fits(self):
        gate = MemoryGate(5 * GIB, poll=0.01)
        pending = [(2 * GIB, "hot_7"), (2 * GIB, "hot_5"), (2 * GIB, "code_087"), (GIB // 2, "light_a"),
                   (GIB // 2, "light_b")]
        self.assertEqual(gate.take(pending), (2 * GIB, "hot_7"))
        self.assertEqual(gate.take(pending), (2 * GIB, "hot_5"))
        # code_087 does not fit (6 > 5); a light one may use the rest, the head waits for a heavy one anyway
        self.assertEqual(gate.take(pending), (GIB // 2, "light_a"))
        self.assertEqual(gate.running, 3)
        gate.release(2 * GIB)                  # hot_7 ends: the head goes before the remaining light one
        self.assertEqual(gate.take(pending), (2 * GIB, "code_087"))

    def test_short_units_do_not_take_the_room_the_head_will_need(self):
        gate = MemoryGate(int(5.5 * GIB), poll=0.01)
        pending = [(2 * GIB, "hot_7"), (GIB // 2, "a"), (GIB // 2, "b"), (GIB // 2, "c"), (GIB // 2, "d")]
        for expected in ("hot_7", "a", "b", "c", "d"):
            self.assertEqual(gate.take(pending)[1], expected)
        pending[:0] = [(3 * GIB, "hot_5")]            # a long one arrives at the head: 4 + 3 > 5.5
        pending.append((GIB // 2, "e"))
        self.assertFalse(gate._may_pass(GIB // 2, 3 * GIB))   # hot_7 (2) + hot_5 (3) fit once the short ones end
        result = []
        worker = threading.Thread(target=lambda: result.append(gate.take(pending)))
        worker.start()
        time.sleep(0.05)
        self.assertEqual(result, [])
        gate.release(GIB // 2)
        gate.release(GIB // 2)
        gate.release(GIB // 2)                         # 2 + 0.5 + 3 = 5.5: hot_5 goes, before "e"
        worker.join(2)
        self.assertEqual(result[0][1], "hot_5")

    def test_short_units_run_while_the_head_waits_for_a_long_one(self):
        gate = MemoryGate(int(4.5 * GIB), poll=0.01)
        pending = [(2 * GIB, "hot_7"), (3 * GIB, "hot_5"), (GIB // 2, "a"), (GIB // 2, "b")]
        self.assertEqual(gate.take(pending)[1], "hot_7")
        # hot_5 cannot start before hot_7 ends (2 + 3 > 4.5): the cores are not left idle meanwhile
        self.assertEqual(gate.take(pending)[1], "a")
        self.assertEqual(gate.take(pending)[1], "b")

    def test_take_returns_none_when_the_plan_is_done(self):
        gate = MemoryGate(GIB)
        self.assertIsNone(gate.take([]))

    def test_gate_can_be_turned_off(self):
        with patch.dict(os.environ, {"RX_MEMORY_GATE": "0"}):
            gate = compile_plan.gate_from_environment()
        gate.acquire(100 * GIB)
        self.assertTrue(gate._fits(100 * GIB))
        gate.release(100 * GIB)

    def test_build_script_uses_the_gate_and_the_hint(self):
        text = (ROOT / "nx2/build.py").read_text(encoding="utf-8")
        self.assertIn("GATE.take(pending", text)
        self.assertIn("GATE.release(need)", text)
        self.assertNotIn("ThreadPoolExecutor(a.jobs)", text)
        self.assertIn("compile_hint.json", text)
        self.assertNotIn("3.5 GiB per O1", (ROOT / "akynoleyend/config.py").read_text(encoding="utf-8"))


class ParallelExtractTests(unittest.TestCase):
    def archive(self, folder, count=300):
        from test_nup_packed import make_archive
        native = zstandard.ZstdCompressor().compress(b"native frame " * 200)
        files = []
        for i in range(count):
            mode = ("plain", "packed", "unknown")[i % 3]
            if i % 10 == 0:
                files.append(("romfs", "dir%02d/native%04d.zs" % (i % 7, i), native, mode))
            else:
                files.append(("romfs", "dir%02d/file%04d.bin" % (i % 7, i), (b"%05d" % i) * (50 + i), mode))
        path = Path(folder, "fixture.nup")
        make_archive(path, files)
        return path, files

    def test_parallel_and_serial_extractions_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as folder:
            path, files = self.archive(folder)
            outputs = []
            for workers in (1, 6):
                archive = nup.Nup(path)
                try:
                    out = Path(folder, "out%d" % workers)
                    count, total = nup.extract(archive, archive.titles[0], out, quiet=True, workers=workers)
                finally:
                    archive.f.close()
                self.assertEqual(count, len(files))
                self.assertEqual(total, sum(len(data) for _, _, data, _ in files))
                outputs.append({p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()})
            self.assertEqual(outputs[0], outputs[1])
            for _, name, data, _ in files:
                self.assertEqual(outputs[1]["romfs/" + name], data)
            self.assertFalse([name for name in outputs[1] if name.endswith(".part")])

    def test_a_wrapped_zs_is_decompressed_once(self):
        with tempfile.TemporaryDirectory() as folder:
            native = zstandard.ZstdCompressor().compress(b"game content" * 400)
            from test_nup_packed import make_archive
            path = Path(folder, "one.nup")
            make_archive(path, [("romfs", "wrapped.zs", native, "unknown")])
            archive = nup.Nup(path)
            calls = []
            original = archive._unpacked_blocks

            def counted(record):
                calls.append(record)
                return original(record)

            archive._unpacked_blocks = counted
            try:
                nup.extract(archive, archive.titles[0], Path(folder, "out"), quiet=True, workers=1)
            finally:
                archive.f.close()
            self.assertEqual(Path(folder, "out/romfs/wrapped.zs").read_bytes(), native)
            self.assertEqual(len(calls), 1)

    def test_workers_default_and_override(self):
        with patch.dict(os.environ, {"NUP_WORKERS": "1"}):
            self.assertEqual(nup.extract_workers(), 1)
        with patch.dict(os.environ, {"NUP_WORKERS": ""}):
            self.assertEqual(nup.extract_workers(), 1)    # threads in the same folders were slower (measured)
        with patch.dict(os.environ, {"NUP_WORKERS": "4"}):
            self.assertEqual(nup.extract_workers(), 4)


class ReaderIdentityTests(unittest.TestCase):
    def test_an_extraction_by_the_previous_reader_is_not_repaired(self):
        from akynoleyend.build import SAME_OUTPUT_READERS, prepare_inputs
        from akynoleyend.config import BuildRequest
        from akynoleyend.files import sha256, write_json
        from test_nup_packed import make_archive
        self.assertIn("c1b9fb6f9bb6a6548d77d7a773a36fc852a37b40ba3c5285d27a1d8bcaef4374", SAME_OUTPUT_READERS)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            header = bytearray(0x100)
            header[:4] = b"NSO0"
            header[0x40:0x44] = bytes.fromhex("e0f3ccfa")
            source = root / "game.nup"
            make_archive(source, [("exefs", "main", bytes(header), "packed"), ("romfs", "a.bin", b"a" * 64, "plain")])
            request = BuildRequest(root / "out", root / "work", root / "tools", nup=source)
            inputs = request.work / "inputs" / sha256(source)
            (inputs / "exefs").mkdir(parents=True)
            (inputs / "romfs").mkdir()
            (inputs / "exefs/main").write_bytes(bytes(header))
            (inputs / "romfs/a.bin").write_bytes(b"a" * 64)
            write_json(inputs / "input.json", {"sha256": sha256(source), "source": str(source),
                                               "reader_sha256": SAME_OUTPUT_READERS[0]})
            with patch("akynoleyend.build.run", side_effect=AssertionError("should not re-extract")):
                exefs, romfs = prepare_inputs(request, dict(os.environ), lambda _: None)
            self.assertEqual(romfs, inputs / "romfs")


class NupIdentityTests(unittest.TestCase):
    def test_identity_is_remembered_for_the_same_file_only(self):
        from akynoleyend.build import nup_identity
        from akynoleyend.files import sha256
        with tempfile.TemporaryDirectory() as folder:
            source, work = Path(folder, "game.nup"), Path(folder, "work")
            source.write_bytes(b"first contents")
            lines = []
            first = nup_identity(source, work, lines.append)
            self.assertEqual(first, sha256(source))
            with patch("akynoleyend.build.sha256", side_effect=AssertionError("read again")):
                self.assertEqual(nup_identity(source, work, lines.append), first)
            self.assertIn("mesma do ultimo uso", lines[-1])
            source.write_bytes(b"other contents!")          # another size
            self.assertEqual(nup_identity(source, work, lines.append), sha256(source))
            stamp = source.stat()
            source.write_bytes(b"same size, new.")          # same size, other bytes and time
            os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 10**9))
            self.assertEqual(nup_identity(source, work, lines.append), sha256(source))
            (work / "inputs/nup-identity.json").write_text("not json", encoding="utf-8")
            self.assertEqual(nup_identity(source, work, lines.append), sha256(source))


if __name__ == "__main__":
    unittest.main()
