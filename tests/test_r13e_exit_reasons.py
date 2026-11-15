"""r13e (the Intel branch), as merged in 0.4.4: the launcher says why the game closed when the code alone tells the player
nothing. 0xC000013A (the console closed or the process cancelled, seen when a shader preparation crawled for half an hour
with 2 GB of RAM free), and a notice before preparing shaders with little RAM free. 0xC000001D, an illegal instruction, was
here too in r13e ("this package needs x86-64-v3"); in 0.4.4 it is cpu.py's (r13j: Criar compiles for the CPU's level, Jogar
refuses a build the CPU cannot run, and the reason names what it lacks): tests/test_r13j_cpu.py. Python only."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from akynoleyend.hardware import GIB, exit_explanation, low_ram_notice  # noqa: E402


class ExitReasons(unittest.TestCase):
    def test_illegal_instruction_is_cpu_py(self):
        for status in (3221225501, -1073741795):
            self.assertEqual(exit_explanation(status), "")

    def test_interrupted(self):
        for status in (3221225786, -1073741510):
            self.assertIn("0xC000013A", exit_explanation(status))
        self.assertTrue(exit_explanation(-1073741510, preparing=True).startswith("A preparacao de shaders foi interrompida"))
        self.assertTrue(exit_explanation(-1073741510).startswith("O jogo foi interrompido"))

    def test_other_codes_say_nothing(self):
        for status in (0, 1, 70, 0xC0000005, 0xC0000409):
            self.assertEqual(exit_explanation(status), "")


class LowRam(unittest.TestCase):
    def info(self, free_gib):
        return {"ram_total": 32 * GIB, "ram_available": int(free_gib * GIB)}

    def test_notice_only_when_preparing_with_little_ram(self):
        self.assertIn("2.1 GB", low_ram_notice(self.info(2.1), preparing=True))
        self.assertEqual(low_ram_notice(self.info(2.1), preparing=False), "")
        self.assertEqual(low_ram_notice(self.info(12), preparing=True), "")
        self.assertEqual(low_ram_notice({"ram_total": 0, "ram_available": 0}, preparing=True), "")


class Wiring(unittest.TestCase):
    def test_launch_prints_the_reason_after_the_code(self):
        launch = (ROOT / "akynoleyend/launch.py").read_text(encoding="utf-8")
        code = launch.index('print("Codigo de encerramento:"')
        reason = launch.index('print("@@error " + explanation')
        self.assertLess(code, reason)
        # (a renderer, memory or illegal-instruction failure keeps its own reason)
        self.assertIn('explanation = "" if memory or failure or illegal else exit_explanation(', launch)
        # (the notice runs before the game starts, so it is in the console the interface shows)
        self.assertLess(launch.index("low_ram_notice(machine"), launch.index("child = subprocess.Popen("))
        # (no AVX2 warning before every start any more: a build the CPU cannot run is refused, cpu.py launch_refusal)
        self.assertNotIn("cpu_lacks_avx2", launch)
        self.assertLess(launch.index("refusal = launch_refusal("), launch.index("child = subprocess.Popen("))


if __name__ == "__main__":
    unittest.main()
