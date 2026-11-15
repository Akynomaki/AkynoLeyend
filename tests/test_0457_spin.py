"""0.4.5-test.7: the main thread's short sleeps spin on the clock with a pause instead of SwitchToThread, and a thread
waiting for a virtual core spins before it sleeps (host/hos_thread.c); the two comparison modes (neither, as in test.6;
every short sleep spinning).

The choices are compiled and run; the rest is read from the sources. No game: none of this says how long the game sleeps
or how fast it runs."""
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
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#ifndef _WIN32
#include <strings.h>
#define _stricmp strcasecmp
#endif
%s
%s
int main(void) {
    /* not set: every one (0.4.5-test.8; the main thread's in test.7); off: none; "all": every one */
    assert(hos_short_sleep_spin(NULL) == 2);
    assert(hos_short_sleep_spin("0") == 0 && hos_short_sleep_spin("off") == 0 && hos_short_sleep_spin("") == 0);
    assert(hos_short_sleep_spin("all") == 2 && hos_short_sleep_spin("ALL") == 2);
    assert(hos_short_sleep_spin("1") == 1 && hos_short_sleep_spin("main") == 1);
    /* the core waiter's spin: 150 us not set, 0 off, bounded to a millisecond */
    assert(vc_spin_ns(NULL) == 150000 && vc_spin_ns("") == 150000);
    assert(vc_spin_ns("0") == 0 && vc_spin_ns("-5") == 0);
    assert(vc_spin_ns("250") == 250000 && vc_spin_ns("99999") == 1000000);
    return 0;
}
'''


class Choices(unittest.TestCase):
    def test_compiled_and_run(self):
        compiler = native_cc()
        if not compiler:
            self.skipTest("C compiler unavailable")
        host = source("host/hos_thread.c")
        sleep = cut(host, "static int short_sleep_value_off(const char *v) {", "    return !_stricmp(asked, \"all\") ? 2 : 1;\n}\n")
        sleep = sleep.replace(cut(sleep, "static int hos_short_sleep_timer(", "\n}\n"), "")
        spin = cut(host, "enum { VC_SPIN_US = 150, VC_SPIN_MAX_US = 1000 };", "* 1000LL;\n}\n")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "check.c").write_text(CHECK % (sleep, spin), encoding="utf-8")
            binary = path / ("check.exe" if os.name == "nt" else "check")
            flags = ["-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function"] + (["-static"] if os.name == "nt" else [])
            built = subprocess.run([compiler, *flags, str(path / "check.c"), "-o", str(binary)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


class Sleep(unittest.TestCase):
    def test_spin_before_yield_and_timer(self):
        host = source("host/hos_thread.c")
        sleep = cut(host, "static void sleep_ns(int64_t ns, int guest) {\n    /* A high", "\n}\n")
        self.assertIn('short_spin = hos_short_sleep_spin(getenv("HOS_SHORT_SLEEP_SPIN"));', sleep)
        self.assertLess(sleep.index("short_spin = hos_short_sleep_spin("), sleep.index("short_timer = how;"))
        spin = sleep.index("if (short_spin == 2 || (short_spin == 1 && yields && main_thread)) {")
        pause = sleep.index("                for (int i = 0; i < 8; i++) _mm_pause();")
        yields = sleep.index("            if (!SwitchToThread()) YieldProcessor();")
        self.assertLess(sleep.index("const int yields ="), spin)
        self.assertLess(spin, pause)
        self.assertLess(pause, yields)
        self.assertLess(yields, sleep.index("if (!tried) {"))
        # a spinning sleep never yields
        self.assertNotIn("SwitchToThread", sleep[spin:pause])


class CoreWaiter(unittest.TestCase):
    def test_spins_once_without_the_lock_then_sleeps(self):
        host = source("host/hos_thread.c")
        acquire = cut(host, "static void vc_acquire(HosThread *t) {", "\n}\n")
        self.assertIn('spin = vc_spin_ns(getenv("HOS_VCORE_SPIN_US"));', acquire)
        self.assertLess(acquire.index("spin = vc_spin_ns("), acquire.index('esc_better = vc_env_ns("HOS_VCORE_ESCAPE_US"'))
        body = cut(acquire, "        if (spin > 0 && !spun) {", "            SleepConditionVariableSRW(&t->vc_cv, &vc_lock, 1, 0);")
        self.assertLess(acquire.index("vc_st.kicks++;"), acquire.index("if (spin > 0 && !spun) {"))
        self.assertIn("spun = 1;", body)
        release = body.index("ReleaseSRWLockExclusive(&vc_lock);")
        loop = body.index("while (!__atomic_load_n(&t->vc_held, __ATOMIC_ACQUIRE) && hos_now_ns() < end)")
        again = body.index("AcquireSRWLockExclusive(&vc_lock);")
        self.assertLess(release, loop)
        self.assertLess(loop, again)
        self.assertIn("} else\n", body)
        # the grant still sets vc_held under the lock before it wakes the waiter
        grant = cut(host, "static void vc_grant(int c) {", "\n}\n")
        self.assertLess(grant.index("vc_take(best, c);"), grant.index("WakeConditionVariable(&best->vc_cv);"))
        self.assertIn("%lld waits ended in the spin in %.0f s", host)

    def test_the_summary_still_reads_the_vcores_line(self):
        import re
        sys.path.insert(0, str(ROOT / "tools"))
        text = (ROOT / "tools" / "resumo_medicao.py").read_text(encoding="utf-8")
        self.assertIn(r'"vcores": re.compile(r"vcores: (\d+) takes, (\d+) waits \(mean "', text)
        num = r"([0-9]+(?:\.[0-9]+)?)"
        line = ("vcores: 120 takes, 30 waits (mean 85 us, longest 2.1 ms), 4 kicks, 2 yields, 0 escapes, "
                "17 waits ended in the spin in 5 s")
        self.assertTrue(re.search(r"vcores: (\d+) takes, (\d+) waits \(mean " + num + r" us, longest " + num + r" ms\), (\d+) kicks", line))


class Modes(unittest.TestCase):
    def test_two_comparisons_with_the_same_measurement(self):
        from akynoleyend.environment import EXPERIMENTS
        base = EXPERIMENTS["esperas"]
        no_spin = {"HOS_SHORT_SLEEP_SPIN": "0", "HOS_VCORE_SPIN_US": "0"}
        self.assertEqual(EXPERIMENTS["esperas-como-test6"], dict(base, **no_spin))
        self.assertEqual(EXPERIMENTS["esperas-todas-giram"], dict(base, HOS_SHORT_SLEEP_SPIN="all"))
        for key in ("HOS_SHORT_SLEEP_SPIN", "HOS_VCORE_SPIN_US"):
            self.assertNotIn(key, base)
        # (0.4.6: the launcher's Teste de desempenho is gone, test_046_final)

    def test_the_environment_carries_them(self):
        from akynoleyend.environment import runtime_environment
        env = runtime_environment({"HOS_SHORT_SLEEP_SPIN": "all", "HOS_VCORE_SPIN_US": "0"}, "original", measure=True,
                                  experiment="esperas")
        self.assertNotIn("HOS_SHORT_SLEEP_SPIN", env)   # inherited values are cleared
        self.assertNotIn("HOS_VCORE_SPIN_US", env)
        env = runtime_environment({}, "original", measure=True, experiment="esperas-como-test6")
        self.assertEqual((env["HOS_SHORT_SLEEP_SPIN"], env["HOS_VCORE_SPIN_US"]), ("0", "0"))
        self.assertEqual(env["HOS_SLEEP_LOG"], "1")
        env = runtime_environment({}, "original", measure=True, experiment="esperas-todas-giram")
        self.assertEqual(env["HOS_SHORT_SLEEP_SPIN"], "all")
        self.assertNotIn("HOS_VCORE_SPIN_US", env)


class Version(unittest.TestCase):
    def test_test_6_installs_update_in_place(self):   # (0.4.5-test.8: the version itself in test_0458_record_priority)
        from akynoleyend.coherence import PREVIOUS_HOST_SOURCES
        self.assertIn("83a595c1a6f66d713db571ca19263d8c36c6b4fd4be10ac6264b407eafbbc530",
                      PREVIOUS_HOST_SOURCES["0.4.5-test.6"])
        self.assertIn('"0.4.5-test.6"', source("builder/AkynoLeyendUpdater/Core.cs"))
        renderer = json.loads(source("ferramentas/prebuilt/renderer.json"))
        self.assertEqual(renderer["shader_stamp"], "4cdbb0029868040b")


if __name__ == "__main__":
    unittest.main()
