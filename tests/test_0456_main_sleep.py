"""0.4.5-test.6: the game's main thread's short sleeps yield instead of waiting on the timer (host/hos_thread.c), and the two
comparison modes (the main thread on the timer too, as in test.5; every thread yielding).

The choice is compiled and run; the rest is read from the sources. No game: none of this says how long the game sleeps or
how fast it runs."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from native_tools import native_cc  # noqa: E402


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


def cut(text, start, end):
    at = text.index(start)
    return text[at:text.index(end, at) + len(end)]


CHECK = r'''
#include <assert.h>
#include <stddef.h>
#include <string.h>
#ifndef _WIN32
#include <strings.h>
#define _stricmp strcasecmp
#endif
%s
int main(void) {
    /* not set: the main thread yields, every other thread does not */
    assert(hos_short_sleep_main_yields("sead::MainThread", NULL) == 1);
    assert(hos_short_sleep_main_yields("BaseProcExecutor0", NULL) == 0);
    assert(hos_short_sleep_main_yields("ModuleSystemWorker1", NULL) == 0);
    assert(hos_short_sleep_main_yields("OptimizeChangeBanc", NULL) == 0);
    assert(hos_short_sleep_main_yields("MainThread", NULL) == 0);   /* the host's own name for it before the game names it */
    assert(hos_short_sleep_main_yields("sead::MainThread2", NULL) == 0);
    assert(hos_short_sleep_main_yields("", NULL) == 0);
    assert(hos_short_sleep_main_yields(NULL, NULL) == 0);
    /* HOS_SHORT_SLEEP_MAIN_TIMER set and not off: the main thread on the timer too, as before */
    assert(hos_short_sleep_main_yields("sead::MainThread", "1") == 0);
    assert(hos_short_sleep_main_yields("sead::MainThread", "yes") == 0);
    assert(hos_short_sleep_main_yields("sead::MainThread", "0") == 1);
    assert(hos_short_sleep_main_yields("sead::MainThread", "off") == 1);
    assert(hos_short_sleep_main_yields("sead::MainThread", "") == 1);
    /* r13i's choice is unchanged */
    assert(hos_short_sleep_timer(NULL, 6) == 1 && hos_short_sleep_timer(NULL, 8) == 0 && hos_short_sleep_timer("0", 6) == 0);
    return 0;
}
'''


class MainThreadSleep(unittest.TestCase):
    def test_choice_compiled_and_run(self):
        compiler = native_cc()
        if not compiler:
            self.skipTest("C compiler unavailable")
        host = source("host/hos_thread.c")
        part = cut(host, "enum { SHORT_SLEEP_TIMER_THREADS = 6 };",
                   "    return name && !strcmp(name, SHORT_SLEEP_MAIN_THREAD);\n}\n")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "check.c").write_text(CHECK % part, encoding="utf-8")
            binary = path / ("check.exe" if os.name == "nt" else "check")
            flags = ["-std=c11", "-O1", "-Wall", "-Wextra", "-Werror"] + (["-static"] if os.name == "nt" else [])
            built = subprocess.run([compiler, *flags, str(path / "check.c"), "-o", str(binary)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_only_the_games_sleeps_on_the_main_thread_with_the_game_s_rule(self):
        host = source("host/hos_thread.c")
        sleep = cut(host, "static void sleep_ns(int64_t ns, int guest) {\n    /* A high", "\n}\n")
        # read once, with r13i's choice; the main thread's own check only where that choice is 1 (the game's on the timer)
        self.assertIn('main_timer = !hos_short_sleep_main_yields(SHORT_SLEEP_MAIN_THREAD, getenv("HOS_SHORT_SLEEP_MAIN_TIMER"));',
                      sleep)
        self.assertLess(sleep.index("main_timer = !hos_short_sleep_main_yields("), sleep.index("short_timer = how;"))
        # (0.4.5-test.7: the same condition, in two lines)
        self.assertIn("const int main_thread = guest && cur && hos_short_sleep_main_yields(cur->name, NULL);", sleep)
        self.assertIn("const int yields = short_timer < (guest ? 1 : 2) || (short_timer == 1 && main_thread && !main_timer);",
                      sleep)
        # the yield loop it takes is the one the other yielding sleeps take
        cond = sleep.index("const int yields = short_timer < (guest ? 1 : 2)")
        self.assertLess(cond, sleep.index("            if (!SwitchToThread()) YieldProcessor();"))
        self.assertLess(sleep.index("            if (!SwitchToThread()) YieldProcessor();"), sleep.index("if (!tried) {"))
        self.assertIn('"the game\'s (but sead::MainThread\'s)"', sleep)


class Modes(unittest.TestCase):
    def test_two_comparisons_with_the_same_measurement(self):
        from akynoleyend.environment import EXPERIMENTS
        base = EXPERIMENTS["esperas"]
        # (0.4.5-test.7: neither spins in them, test_0457_spin)
        no_spin = {"HOS_SHORT_SLEEP_SPIN": "0", "HOS_VCORE_SPIN_US": "0"}
        self.assertEqual(EXPERIMENTS["esperas-como-antes"], dict(base, HOS_SHORT_SLEEP_MAIN_TIMER="1", **no_spin))
        self.assertEqual(EXPERIMENTS["esperas-todas-cedem"], dict(base, HOS_SHORT_SLEEP_TIMER="0", **no_spin))
        self.assertNotIn("HOS_SHORT_SLEEP_MAIN_TIMER", base)
        self.assertNotIn("HOS_SHORT_SLEEP_TIMER", base)
        # (0.4.6: the launcher's Teste de desempenho is gone, test_046_final)

    def test_the_environment_carries_them(self):
        from akynoleyend.environment import runtime_environment
        env = runtime_environment({"HOS_SHORT_SLEEP_MAIN_TIMER": "1"}, "original", measure=True, experiment="esperas")
        self.assertNotIn("HOS_SHORT_SLEEP_MAIN_TIMER", env)   # an inherited value is cleared
        env = runtime_environment({}, "original", measure=True, experiment="esperas-como-antes")
        self.assertEqual(env["HOS_SHORT_SLEEP_MAIN_TIMER"], "1")
        self.assertEqual(env["HOS_SLEEP_LOG"], "1")
        env = runtime_environment({}, "original", measure=True, experiment="esperas-todas-cedem")
        self.assertEqual(env["HOS_SHORT_SLEEP_TIMER"], "0")


class Version(unittest.TestCase):
    def test_test_5_installs_update_in_place(self):   # (0.4.5-test.7: the version itself in test_0457_spin)
        from akynoleyend.coherence import PREVIOUS_HOST_SOURCES
        self.assertIn("d79a9a71f95d0d8458f912b52f3a6ec47c5f050da9e6c9a1d846edd9ecf7922e",
                      PREVIOUS_HOST_SOURCES["0.4.5-test.5"])
        self.assertIn('"0.4.5-test.5"', source("builder/AkynoLeyendUpdater/Core.cs"))
        renderer = json.loads(source("ferramentas/prebuilt/renderer.json"))
        self.assertEqual(renderer["shader_stamp"], "4cdbb0029868040b")


if __name__ == "__main__":
    unittest.main()
