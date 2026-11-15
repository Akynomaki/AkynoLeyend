"""0.4.5-test.2: the submit's replay without the virtual core, the performance measurement and its A/B experiments.

The host changes are read from the sources (they run only inside the game); the measurement's switches, the CLI and
tools/resumo_medicao.py run here. No game: none of this says the frame rate changed.
"""
import json
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


def function(text, head):
    """The body of the C function whose definition starts with head (braces counted)."""
    start = text.index(head)
    i = text.index("{", start)
    depth = 0
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[start:j + 1]
    raise AssertionError(head)


class SubmitWithoutCore(unittest.TestCase):
    def setUp(self):
        self.text = source("host/nvn_native.c")

    def test_the_replay_gives_the_core_up_only_when_asked(self):   # (0.4.5-test.3: kept by default)
        body = function(self.text, "static void replay_submit(")
        away, submit, back = body.index("hos_vcore_away()"), body.index("rx_nvn_submit_q("), body.index("hos_vcore_back()")
        self.assertLess(away, submit)
        self.assertLess(submit, back)
        self.assertIn("submit_keep_core() ? 0 : hos_vcore_away()", body)
        keep = function(self.text, "static int submit_keep_core(")
        self.assertIn('getenv("HOS_SUBMIT_FREE_CORE")', keep)
        self.assertIn("v = !(e && atoi(e) != 0);", keep)

    def test_every_submit_goes_through_it(self):
        for head in ("NV(nvnQueueSubmitCommands)", "static void held_flush("):
            body = function(self.text, head)
            self.assertIn("replay_submit(", body, head)
            self.assertIsNone(re.search(r"(?<!replay_)\brx_nvn_submit(_q)?\(", body), head)

    def test_the_log_counts_the_replays(self):
        self.assertIn("nvn: submits in 5 s: %lld replayed on the submitting threads in %.0f ms, %lld of them with the core given up",
                      self.text)


class MemoryMap(unittest.TestCase):
    def test_the_map_is_logged_every_30_s_with_hos_mem_map(self):
        body = function(source("host/mkw_glue.c"), "static DWORD WINAPI mem_watch(")
        self.assertIn('getenv("HOS_MEM_MAP")', body)
        self.assertIn("tick % 15 == 0", body)   # (2 s ticks)
        self.assertIn("hos_memory_map_log();", body)


class Switches(unittest.TestCase):
    def test_measure_adds_its_variables_on_top_of_a_profile(self):
        from akynoleyend.environment import MEASURE, PROFILES, runtime_environment
        env = runtime_environment({}, "8gb", measure=True)
        for key, value in {**MEASURE, **PROFILES["8gb"]}.items():
            self.assertEqual(env[key], value)
        self.assertNotIn("HOS_PROFILE", runtime_environment({}, "8gb"))

    def test_experiments_need_the_measurement(self):
        from akynoleyend.environment import runtime_environment
        from akynoleyend.errors import ProjectError
        self.assertEqual(runtime_environment({}, "original", measure=True, experiment="nucleo-solto")["HOS_SUBMIT_FREE_CORE"], "1")
        self.assertEqual(runtime_environment({}, "original", measure=True, experiment="gravacao-paralela")["RX_VK_PARALLEL"], "3")
        with self.assertRaises(ProjectError):
            runtime_environment({}, "original", experiment="nucleo-solto")
        with self.assertRaises(ProjectError):
            runtime_environment({}, "original", measure=True, experiment="turbo")

    def test_inherited_experiment_variables_are_dropped(self):
        from akynoleyend.environment import runtime_environment
        env = runtime_environment({"HOS_SUBMIT_KEEP_CORE": "1", "RX_VK_PARALLEL": "8", "HOS_PROFILE": "1"}, "original")
        self.assertFalse({"HOS_SUBMIT_KEEP_CORE", "RX_VK_PARALLEL", "HOS_PROFILE"} & set(env))

    def test_the_cli_takes_them(self):
        from akynoleyend.cli import parser
        args = parser().parse_args(["run", "--measure", "--experiment", "gravacao-paralela"])
        self.assertTrue(args.measure)
        self.assertEqual(args.experiment, "gravacao-paralela")
        self.assertEqual(parser().parse_args(["run"]).experiment, "nenhum")

    def test_the_launcher_offers_them(self):  # (0.4.6: the launcher's Teste de desempenho is gone, test_046_final)
        self.assertIn('environment["AKYNO_FRAMETIMES"] = str(logs / "quadros.bin")', source("akynoleyend/launch.py"))


class Summary(unittest.TestCase):
    def test_a_run_folder_is_summarized(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import resumo_medicao
        with tempfile.TemporaryDirectory(prefix="medicao-") as tmp:
            folder = Path(tmp)
            times = [20.0] * 980 + [100.0] * 10 + [300.0] * 10
            (folder / "quadros.bin").write_bytes(struct.pack("<%df" % len(times), *times))
            (folder / "execucao.json").write_text(json.dumps({"measure": True, "experiment": "nenhum"}), encoding="utf-8")
            (folder / "erros.log").write_text("\n".join([
                "[hos Presentation Thread] vk: 600 presents, 30.0 fps; a frame: 2400 draws (0 skipped), 150 dispatches, 9 passes",
                "[hos Presentation Thread] vk: GPU time 17.5 ms a frame (the longest submission 18.0 ms)",
                "[hos Presentation Thread] vk: a frame's replay time (ms): submit 28.00, present 0.40, draw 20.00",
                "[hos Presentation Thread] nvn: submits in 5 s: 900 replayed on the submitting threads in 2500 ms, 900 of them with the core given up",
                "[hos sead::MainThread] nvn: GPU waits in 5 s: 300 sync waits (1500 ms), 0 polls timed out (0 ms), 0 queue finishes (0 ms)",
                "[hos host] prof: busiest threads (% of a core): Presentation Thread 61, sead::MainThread 55, mkw_vk order 2, all 190",
                "[hos host] prof: busiest threads (% of a core): Presentation Thread 59, sead::MainThread 45, all 170",
                "[hos sead::MainThread] vcores: sead::MainThread (priority 16) ran without a core after 250.2 ms: core 0: Presentation Thread (17) asked;",
                "[hos host] mem: measured: RAM 900 MB free of 16310; system commit 20000 MB used of 24000 (4000 free); this process 15000 MB private (peak 15500), 9000 MB working set",
                "[hos host] mem: guest window 5500 MB committed in 4000 regions",
                "[hos host] mem: private outside the guest window 3200 MB; largest: 1 100 MB",
            ]) + "\n", encoding="utf-8")
            r = resumo_medicao.summarize(folder)
        f = r["frames"]
        self.assertEqual(f["frames"], 1000)
        self.assertEqual(f["fps_median"], 50.0)
        self.assertEqual(f["over_250ms"], 10)
        self.assertEqual(f["fps_1pct_low"], round(1000 / 300, 1))
        self.assertEqual(r["draws_a_frame"], 2400)
        self.assertEqual(r["gpu_ms_a_frame"], 17.5)
        self.assertEqual(r["submit_replay_ms_per_s"], 500.0)
        self.assertEqual(r["submits_core_given_up_pct"], 100.0)
        self.assertEqual(r["main_gpu_wait_ms_per_s"], 300.0)
        self.assertEqual(r["threads_pct_of_a_core"]["Presentation Thread"], 60.0)
        self.assertEqual(r["replay_ms_a_frame"]["submit"], 28.0)
        self.assertEqual(r["vcore_escapes"], {"sead::MainThread <- Presentation Thread": 1})
        self.assertEqual((r["process_private_max_mb"], r["guest_committed_max_mb"], r["outside_private_max_mb"]), (15000, 5500, 3200))
        self.assertIn("pior 1%", resumo_medicao.report(r))


class Version(unittest.TestCase):
    def test_test_1_installs_update_in_place(self):
        from akynoleyend import __version__
        from akynoleyend.coherence import HOST_REVISION, compatible_previous_host
        self.assertTrue(__version__.startswith("0.4.5-test.") or __version__ in ("0.4.6", "0.4.7", "0.4.8"))
        for identity in ("df76cd9ce03758f3382f2d8c92875eb4d7623808f53c77ed53357e18acf309ca",
                         "e8a1da01e2f0e1be65e599551e06e3027cacf7190a9142c86efa689a60dc6b32"):
            self.assertTrue(compatible_previous_host({"version": "0.4.5-test.1", "source_sha256": identity,
                                                      "host_revision": HOST_REVISION, "game_build_id": "e0f3ccfa"}))
        self.assertIn('"0.4.5-test.1"', source("builder/AkynoLeyendUpdater/Core.cs"))


if __name__ == "__main__":
    unittest.main()
