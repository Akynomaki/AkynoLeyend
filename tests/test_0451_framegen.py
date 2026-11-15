"""0.4.5-test.1: dynamic frame generation and the new pacer.

The controller (gpu/vk/fg_dynamic.h over MFG-Unlocker's fg_dynamic_count.h) and the pacer (gpu/vk/fg_pacer.h) run natively
against simulated games and GPUs; the wiring into vk_framegen.cpp, the F1 panel, the launcher and the CLI is read from the
sources. No game or GPU: none of this says the mode was tried in the game or looked smooth on a screen.
"""
import hashlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

UPSTREAM_COUNT_SHA256 = "6b9fec52a8c24faa80fc21fb88e1a0845a68e29d0d0498ecd2556de3bcd483e8"


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


def run_native(name):
    from tests.native_tools import native_cxx
    cxx = native_cxx()
    if not cxx:
        raise unittest.SkipTest("no native C++ compiler")
    with tempfile.TemporaryDirectory(prefix="fg-") as tmp:
        exe = Path(tmp) / (name + ".exe")
        subprocess.run([cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-I" + str(ROOT / "gpu/vk"),
                        str(ROOT / "tests/native" / (name + ".cpp")), "-o", str(exe)], check=True)
        # (llvm-mingw's C++ runtime DLLs sit beside its compiler)
        env = dict(__import__("os").environ)
        env["PATH"] = str(Path(cxx).parent) + __import__("os").pathsep + env.get("PATH", "")
        result = subprocess.run([str(exe)], capture_output=True, text=True, env=env)
        return result.returncode, result.stdout + result.stderr


class Native(unittest.TestCase):
    def test_dynamic_count_settles_where_expected(self):
        code, out = run_native("fg_dynamic_test")
        self.assertEqual(code, 0, out)
        self.assertNotIn("FAIL", out)

    def test_pacer_is_even_and_not_later_than_needed(self):
        code, out = run_native("fg_pacer_test")
        self.assertEqual(code, 0, out)
        self.assertNotIn("FAIL", out)


class Licence(unittest.TestCase):
    def test_the_controller_is_the_upstream_file_under_its_notice(self):
        text = source("gpu/vk/fg_dynamic_count.h")
        self.assertIn("Copyright (c) 2026 Michael Robles", text)
        self.assertIn("Permission is hereby granted, free of charge", text)
        body = text[text.index("#pragma once"):]
        self.assertEqual(hashlib.sha256(body.encode("utf-8")).hexdigest(), UPSTREAM_COUNT_SHA256)
        self.assertIn("Michael Robles", (ROOT / "licenses/mfg-unlocker/LICENSE.txt").read_text(encoding="utf-8"))
        self.assertIn("MFG-Unlocker", source("THIRD_PARTY_NOTICES.md"))
        self.assertIn(UPSTREAM_COUNT_SHA256, source("THIRD_PARTY_NOTICES.md"))

    def test_our_headers_call_no_windows_or_vulkan(self):
        for name in ("gpu/vk/fg_dynamic.h", "gpu/vk/fg_pacer.h"):
            text = source(name)
            for word in ("windows.h", "vulkan", "vk_internal.h", "HWND", "VkEvent"):
                self.assertNotIn(word, text, name)


class Wiring(unittest.TestCase):
    def test_renderer(self):
        fg = source("gpu/vk/vk_framegen.cpp")
        self.assertIn('#include "fg_dynamic.h"', fg)
        self.assertIn('#include "fg_pacer.h"', fg)
        self.assertIn("constexpr int kDynamicRow = 9;", fg)
        # the sets are made for the most frames once; the count per game frame never passes what was made
        self.assertIn("if (fg.w == w && fg.h == h && fg.mult == allocated()) return true;", fg)
        self.assertIn("m = fg.dyn_on ? std::clamp(fg.dyn_frames, 1, fg.mult) : multiplier();", fg)
        # the display thread waits for the GPU, then the pacer's line; the event is reset before it is recorded again
        self.assertIn("const int64_t ready = wait_made(*j.set, j.at + pacer.lag());", fg)
        self.assertIn("const int64_t due = pacer.due(now, pace, k == 0);", fg)
        self.assertLess(fg.index("vkResetEvent(dev.device, set->ready)"), fg.index("vkCmdSetEvent(cmd, set->ready"))
        self.assertIn('getenv("RX_VK_FG_TRACE")', fg)
        self.assertIn('getenv("RX_VK_FG_READY")', fg)
        loader = source("gpu/vk/vk_loader.h")
        for name in ("vkCreateEvent", "vkCmdSetEvent", "vkGetEventStatus", "vkResetEvent"):
            self.assertIn("X(%s)" % name, loader)

    def test_panel_rows(self):
        menu = source("gpu/vk/vk_menu.cpp")
        self.assertIn('{"Frame generation", "Geração de quadros", &opts.framegen, 0, 9, 1, tx_framegen,', menu)
        self.assertIn('"Dinâmica"};', menu)
        names = re.findall(r'^    \{"([A-Za-z ]+)", "[^"]+", &opts\.', menu, re.M)
        for name in ("Framegen maximum", "Framegen target"):
            self.assertIn(name, names)
            self.assertLess(len(name), 31)   # (ini_key's buffer)
        video = re.search(r"constexpr Setting video_rows\[\] = \{([^}]+)\}", menu).group(1)
        self.assertIn("Framegen, FgMax, FgTarget, Pacing", video)
        header = source("gpu/vk/vk_menu.h")
        self.assertIn("int fg_max = 4;", header)
        self.assertIn("int fg_target = 0;", header)
        self.assertIn("opts.framegen = std::clamp(atoi(e), 0, 9)", menu)

    def test_launcher_and_cli(self):
        from akynoleyend.errors import ProjectError
        from akynoleyend.graphics import graphics_environment
        self.assertEqual(graphics_environment(framegen=9)["AKYNO_FRAMEGEN"], "9")
        with self.assertRaises(ProjectError):
            graphics_environment(framegen=10)
        self.assertIn("choices=(0, 2, 3, 4, 5, 6, 7, 8, 9)", source("akynoleyend/cli.py"))
        self.assertIn('Add("--framegen",Framegen,"0","2","3","4","5","6","7","8","9");',
                      source("builder/AkynoLeyendBuilder/LaunchOptions.cs"))
        self.assertIn('Tag="9"', source("builder/AkynoLeyendBuilder/MainWindow.xaml"))

    def test_shader_stamp_unchanged(self):
        from akynoleyend.build_support import shader_cache_stamp
        self.assertEqual(shader_cache_stamp(ROOT / "gpu/vk"), "4cdbb0029868040b")


class TraceSummary(unittest.TestCase):
    def test_a_small_trace(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("fg_trace_summary", ROOT / "tools/fg_trace_summary.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.csv"
            lines = ["batch,k,shown,at_ms,ready_ms,due_ms,shown_ms,interval_ms,lag_ms,dynamic,target_fps,refresh_hz"]
            for batch in range(60):
                at = batch * 25.0
                for k in range(4):
                    t = at + 10 + k * 6.25
                    lines.append("%d,%d,4,%.3f,%.3f,%.3f,%.3f,25,10,1,138,144" % (batch, k, at, at + 9, t, t))
            lines.append("60,0,4,1500")   # (a line cut by the game closing)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            text = "\n".join(tool.summary(tool.read(path)))
        self.assertIn("4x em 100%", text)
        self.assertIn("alvo 138 FPS, monitor 144 Hz", text)
        self.assertIn("Dentro de 25% do passo: 100.0%", text)
        self.assertIn("Atrasados (mais de 2 ms depois do lugar): 0", text)


if __name__ == "__main__":
    unittest.main()
