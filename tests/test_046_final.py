"""0.4.6, the final one after the 0.4.5 tests: every short sleep still spins by default (host/hos_thread.c), test.8's
highest priority for the Presentation Thread is gone (no gain measured), and the launcher no longer has the Teste de
desempenho choice (manage.py run --measure [--experiment] stays).

The sleep choice is compiled and run; the rest is read from the sources. No game: none of this says how fast it runs."""
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
    assert(hos_short_sleep_spin(NULL) == 2);
    assert(hos_short_sleep_spin("main") == 1 && hos_short_sleep_spin("1") == 1);
    assert(hos_short_sleep_spin("0") == 0 && hos_short_sleep_spin("off") == 0 && hos_short_sleep_spin("all") == 2);
    return 0;
}
'''


class Sleeps(unittest.TestCase):
    def test_every_short_sleep_spins_by_default(self):
        compiler = native_cc()
        if not compiler:
            self.skipTest("C compiler unavailable")
        host = source("host/hos_thread.c")
        code = cut(host, "static int short_sleep_value_off(const char *v) {", "\n}\n")
        code += cut(host, "static int hos_short_sleep_spin(const char *asked) {", "\n}\n")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "check.c").write_text(CHECK % code, encoding="utf-8")
            binary = path / ("check.exe" if os.name == "nt" else "check")
            flags = ["-std=c11", "-O1", "-Wall", "-Wextra", "-Werror"] + (["-static"] if os.name == "nt" else [])
            built = subprocess.run([compiler, *flags, str(path / "check.c"), "-o", str(binary)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        self.assertIn('getenv("HOS_VCORE_SPIN_US")', host)   # the core waiter's spin (test.7) stays


class Priority(unittest.TestCase):
    def test_the_recording_thread_keeps_the_normal_priority(self):
        host = source("host/hos_thread.c")
        for gone in ("hos_present_thread_high", "HOS_PRESENT_NORMAL\")", "PRESENT_THREAD[]"):
            self.assertNotIn(gone, host)
        pin = cut(host, "void hos_thread_pin(void *h, const char *name) {", "\n}\n")
        self.assertEqual(pin.count("THREAD_PRIORITY_HIGHEST"), 1)   # only in HOS_PRIO's levels
        self.assertIn('else if (strstr(name, "OptimizeChange") && !getenv("HOS_OCB_NORMAL")) {', pin)
        from akynoleyend.environment import EXPERIMENTS
        for tag, values in EXPERIMENTS.items():
            self.assertNotIn("HOS_PRESENT_NORMAL", values, tag)
        self.assertEqual(EXPERIMENTS["esperas-como-test7"], dict(EXPERIMENTS["esperas"], HOS_SHORT_SLEEP_SPIN="main"))


class Launcher(unittest.TestCase):
    def test_no_teste_de_desempenho(self):
        xaml = source("builder/AkynoLeyendBuilder/MainWindow.xaml")
        code = source("builder/AkynoLeyendBuilder/MainWindow.xaml.cs")
        launch = source("builder/AkynoLeyendBuilder/LaunchOptions.cs")
        checks = source("builder/RunnerChecks/Program.cs")
        for text in (xaml, code, checks):
            self.assertNotIn("MeasureBox", text)
            self.assertNotIn("Measurement.Arguments", text)
        self.assertNotIn("Medir ·", xaml)
        self.assertNotIn('Text="Teste de desempenho"', xaml)
        self.assertNotIn("static class Measurement", launch)
        self.assertNotIn('"--measure"', launch)
        self.assertIn("try{args.AddRange(CaptureGraphics().Arguments());}", code)

    def test_the_cli_still_measures(self):
        from akynoleyend.cli import parser
        args = parser().parse_args(["run", "--measure", "--experiment", "esperas"])
        self.assertTrue(args.measure)
        self.assertEqual(parser().parse_args(["run"]).experiment, "nenhum")


class Version(unittest.TestCase):
    def test_test_8_installs_update_in_place(self):
        from akynoleyend import __version__
        from akynoleyend.coherence import PREVIOUS_HOST_SOURCES
        self.assertIn(__version__, ("0.4.6", "0.4.7", "0.4.8", "0.4.9"))   # (0.4.7: test_047_launcher)
        self.assertIn("b7e6521ffb4b78b043c1401eb444dc82901890974d95310aa5176b71cd64de06",
                      PREVIOUS_HOST_SOURCES["0.4.5-test.8"])
        self.assertIn('"0.4.5-test.8"', source("builder/AkynoLeyendUpdater/Core.cs"))
        renderer = json.loads(source("ferramentas/prebuilt/renderer.json"))
        self.assertEqual(renderer["shader_stamp"], "4cdbb0029868040b")


if __name__ == "__main__":
    unittest.main()
