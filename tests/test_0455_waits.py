"""0.4.5-test.5: a measurement mode for the game's main thread's waits (its sleeps by caller and two job workers' samples).

Read from the sources and run on a made-up log. No game: none of this says how long the game sleeps or what it waits for.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class WaitsMode(unittest.TestCase):
    def test_mode_samples_the_main_thread_and_two_workers_and_logs_sleeps(self):
        from akynoleyend.environment import EXPERIMENTS
        self.assertEqual(EXPERIMENTS["esperas"], {"HOS_SAMPLE": "sead::MainThread|BaseProcExecutor0|BaseProcExecutor1",
                                                  "HOS_SLEEP_LOG": "1"})
        self.assertIn('getenv("HOS_SLEEP_LOG")', source("host/hos_thread.c"))
        # (0.4.6: the launcher's Teste de desempenho is gone, test_046_final)

    def test_summary_adds_up_sleeps_by_caller(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import resumo_medicao
        with tempfile.TemporaryDirectory(prefix="sonos-") as tmp:
            folder = Path(tmp)
            (folder / "erros.log").write_text("\n".join([
                "[hos sead::MainThread] sleep: lr 0x80099b10: 4000 calls, asked 6.40 ms, slept 120.50 ms (30.1 us each)",
                "[hos BaseProcExecutor0] sleep: lr 0x80099b10: 1000 calls, asked 1.60 ms, slept 30.00 ms (30.0 us each)",
                "[hos sead::MainThread] sleep: lr 0x8051a000: 10 calls, asked 160.00 ms, slept 161.00 ms (16100.0 us each)",
            ]) + "\n", encoding="utf-8")
            r = resumo_medicao.summarize(folder, symbols=False)
        self.assertEqual(r["sleeps"][0], {"lr": 0x8051a000, "calls": 10, "asked_ms": 160.0, "slept_ms": 161.0})
        self.assertEqual(r["sleeps"][1], {"lr": 0x80099b10, "calls": 5000, "asked_ms": 8.0, "slept_ms": 150.5})
        text = resumo_medicao.report(r)
        self.assertIn("lr 0x80099b10: 5000 chamadas, 8 ms pedidos / 150 ms dormidos (2 / 30 us)", text)


class Version(unittest.TestCase):
    def test_test_4_installs_update_in_place(self):   # (0.4.5-test.6: the version itself in test_0456_main_sleep)
        from akynoleyend.coherence import PREVIOUS_HOST_SOURCES
        self.assertIn("8c0c9073fec691692e9071da977e973ff4894bd5f14cc8dfae199c5b742f92d1",
                      PREVIOUS_HOST_SOURCES["0.4.5-test.4"])
        self.assertIn('"0.4.5-test.4"', source("builder/AkynoLeyendUpdater/Core.cs"))
        renderer = json.loads(source("ferramentas/prebuilt/renderer.json"))
        self.assertEqual(renderer["shader_stamp"], "4cdbb0029868040b")


if __name__ == "__main__":
    unittest.main()
