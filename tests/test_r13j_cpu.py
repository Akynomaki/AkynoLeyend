"""r13j: the x86-64 level the game is compiled for, chosen by the CPU of the PC that builds it, and 0xC000001D explained.

A build for x86-64-v3 (AVX2, FMA, BMI1/2) stopped at once with 0xC000001D on a CPU without them (a tester's PC with an RX 590,
Teste 4 r3: the game's registers all zero, the host's boot code). The level choice and the messages are run; the probe is
compiled and run where the packaged clang is; the build, update, renderer and launch wiring is read from the sources. No game
was run on a CPU without AVX2: none of this says that it runs there."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from akynoleyend import cpu  # noqa: E402

ALL = {name: True for name in cpu.NAMES}


def without(*names):
    return {**ALL, **{name: False for name in names}}


# (CPUID of known processors, by what they lack)
HASWELL_ON = ALL                                                         # Core 4th gen, Ryzen: everything
IVY_BRIDGE = without("avx2", "bmi1", "bmi2", "fma", "lzcnt", "movbe")    # Core 3rd gen: AVX and F16C, no AVX2
PILEDRIVER = without("avx2", "bmi2", "movbe")                            # FX-8350: AVX, FMA, BMI1, no AVX2
PENRYN = without("avx", "avx2", "bmi1", "bmi2", "f16c", "fma", "lzcnt", "movbe", "os_avx", "popcnt", "sse42")
NO_OS_AVX = without("os_avx")                                            # AVX2 CPU, Windows not saving the AVX registers


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Level(unittest.TestCase):
    def test_choice(self):
        self.assertEqual(cpu.choose_march(HASWELL_ON), "x86-64-v3")
        self.assertEqual(cpu.choose_march(IVY_BRIDGE), "x86-64-v2")
        self.assertEqual(cpu.choose_march(PILEDRIVER), "x86-64-v2")
        self.assertEqual(cpu.choose_march(NO_OS_AVX), "x86-64-v2")
        self.assertEqual(cpu.choose_march(PENRYN), "x86-64")
        self.assertEqual(cpu.choose_march({}), "x86-64")

    def test_levels_as_the_psabi(self):
        self.assertEqual(set(cpu.REQUIRED["x86-64-v2"]), {"cx16", "lahf", "popcnt", "sse3", "ssse3", "sse41", "sse42"})
        self.assertTrue(set(cpu.REQUIRED["x86-64-v2"]) < set(cpu.REQUIRED["x86-64-v3"]))
        for name in ("avx", "avx2", "bmi1", "bmi2", "f16c", "fma", "lzcnt", "movbe", "os_avx"):
            self.assertIn(name, cpu.REQUIRED["x86-64-v3"])
        self.assertEqual(cpu.MARCH_LEVELS[-1], cpu.DEFAULT_MARCH)   # never above what the project ships
        self.assertEqual(cpu.missing(PILEDRIVER, "x86-64-v3"), ["AVX2", "BMI2", "MOVBE"])
        self.assertEqual(cpu.missing(PILEDRIVER, "x86-64-v2"), [])

    def test_old_builds_are_v3(self):
        self.assertEqual(cpu.build_march({}), "x86-64-v3")
        self.assertEqual(cpu.build_march({"march": "x86-64-v2"}), "x86-64-v2")
        self.assertEqual(cpu.build_march({"march": "native"}), "x86-64-v3")


class Messages(unittest.TestCase):
    def test_before_launch(self):
        text = cpu.unsupported_message("AMD FX(tm)-8350", "x86-64-v3", PILEDRIVER)
        for part in ("x86-64-v3", "AMD FX(tm)-8350", "AVX2", "0xC000001D", "Criar", "x86-64-v2"):
            self.assertIn(part, text)

    def test_after_the_exit_code(self):
        self.assertIn("nao tem: AVX2", cpu.illegal_instruction_message("x", "x86-64-v3", IVY_BRIDGE))
        unknown = cpu.illegal_instruction_message("x", "x86-64-v3", None)
        self.assertIn("0xC000001D", unknown)
        self.assertIn("machine:", unknown)
        self.assertIn("parece ter", cpu.illegal_instruction_message("x", "x86-64-v3", HASWELL_ON))

    def test_launch_refusal(self):
        tools = ROOT / "ferramentas"
        with mock.patch.object(cpu, "windows_says_avx2", return_value=True), \
             mock.patch.object(cpu, "detect", side_effect=AssertionError("no probe needed")):
            self.assertIsNone(cpu.launch_refusal({}, tools, "x"))
        with mock.patch.object(cpu, "windows_says_avx2", return_value=False), \
             mock.patch.object(cpu, "detect", return_value=IVY_BRIDGE):
            self.assertIn("nao tem", cpu.launch_refusal({}, tools, "x"))
            self.assertIsNone(cpu.launch_refusal({"march": "x86-64-v2"}, tools, "x"))
        with mock.patch.object(cpu, "windows_says_avx2", return_value=False), \
             mock.patch.object(cpu, "detect", return_value=None):
            self.assertIsNone(cpu.launch_refusal({}, tools, "x"))   # not known: no refusal, as before


class Probe(unittest.TestCase):
    def test_probe_runs_here(self):
        if os.name != "nt" or not (ROOT / "ferramentas/llvm/bin/clang.exe").is_file():
            self.skipTest("Windows and the packaged clang only")
        features = cpu.detect(ROOT / "ferramentas")
        self.assertIsNotNone(features)
        self.assertEqual(set(features), set(cpu.NAMES))
        self.assertTrue(features["cx16"])   # 64-bit Windows 8.1 and later require it
        self.assertIn(cpu.choose_march(features), cpu.MARCH_LEVELS)
        if cpu.windows_says_avx2():
            self.assertTrue(features["avx2"] and features["os_avx"])

    def test_probe_is_baseline(self):
        self.assertNotIn("-march", cpu._probe.__wrapped__.__code__.co_consts)
        self.assertIn('"xgetbv"', cpu.PROBE)


class Wiring(unittest.TestCase):
    def test_build_sets_the_level_before_compiling(self):
        build = source("akynoleyend/build.py")
        at = build.index('environment["RX_MARCH"] = march')
        self.assertLess(build.index("cpu_features = detect_cpu(request.tools)"), at)
        self.assertLess(at, build.index('str(ROOT / "nx2/lift.py")'))
        self.assertIn('"march": march,', build)
        self.assertIn('timing.measure("publish", publish, request, romfs, identity, jobs, started, march)', build)
        # nx2/build.py takes it for the game, the host and the renderer; its default stays x86-64-v3
        self.assertIn('CPU = ["-march=" + os.environ.get("RX_MARCH", "x86-64-v3"), "-ffp-contract=off"]', source("nx2/build.py"))
        self.assertIn('"march": environment.get("RX_MARCH", "x86-64-v3")', source("akynoleyend/prebuilt.py"))

    def test_the_packaged_renderer_is_not_used_below_v3(self):
        from akynoleyend.prebuilt import renderer_prebuilt
        base = {"OCARINA_TARGET": "windows-gnu", "RX_RELEASE": "1"}
        tools = ROOT / "ferramentas"
        self.assertIsNone(renderer_prebuilt(ROOT, tools / "deps", tools / "prebuilt", {**base, "RX_MARCH": "x86-64-v2"},
                                            lambda _: None))
        self.assertIsNone(renderer_prebuilt(ROOT, tools / "deps", tools / "prebuilt", {**base, "RX_MARCH": "x86-64"},
                                            lambda _: None))

    def test_update_keeps_the_builds_level(self):
        maintenance = source("akynoleyend/maintenance.py")
        self.assertIn("march = build_march(manifest)", maintenance)
        self.assertIn('environment["RX_MARCH"] = march', maintenance)
        self.assertIn("if not prebuilt_used and build_march(manifest) == DEFAULT_MARCH:", maintenance)
        self.assertIn("build_march(manifest))", maintenance)
        prepare = source("akynoleyend/shader_prepare.py")
        guard = prepare.index("if build_march(manifest) != DEFAULT_MARCH:")
        self.assertLess(guard, prepare.index("source = renderer_prebuilt("))

    def test_launch_refuses_and_explains(self):
        launch = source("akynoleyend/launch.py")
        self.assertIn('refusal = launch_refusal(manifest, ROOT / "ferramentas", snapshot().get("cpu", ""))', launch)
        self.assertIn("status & 0xFFFFFFFF == ILLEGAL_INSTRUCTION_EXIT", launch)
        self.assertIn('print("@@error " + illegal, flush=True)', launch)
        self.assertEqual(cpu.ILLEGAL_INSTRUCTION_EXIT, 3221225501)   # the tester's execucao.json


if __name__ == "__main__":
    unittest.main()
