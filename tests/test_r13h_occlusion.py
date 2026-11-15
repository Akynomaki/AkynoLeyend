"""r13h: NVN's samples-passed counter from Vulkan occlusion queries, and the game's own occlusion queries on again. The
running count is compiled and run (gpu/vk/occlusion_count.h); the queries' place in the passes, the reports written after the
GPU, the render conditions and the launch mode are read from the sources. No game or GPU: none of this says what the game
culls on screen."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from native_tools import native_cxx  # noqa: E402

FOLD = r'''
#include <cassert>
#include "occlusion_count.h"
using namespace mkwvk;
int main() {
    OcclusionRunning r;
    assert(occlusion_fold(r, 0, false, true) == 0);            // reset
    assert(occlusion_fold(r, 120, false, false) == 120);       // report: the samples of its queries
    assert(occlusion_fold(r, 30, false, false) == 150);        // another report without a reset: NVN's count runs on
    assert(occlusion_fold(r, 0, false, true) == 0);            // reset
    assert(occlusion_fold(r, 0, false, false) == 0);           // nothing passed: 0, the game culls what it tested
    assert(occlusion_fold(r, 0, true, false) == 1);            // a draw uncounted: never 0
    assert(occlusion_fold(r, 0, false, false) == 1);           // still since the reset
    assert(occlusion_fold(r, 0, false, true) == 0);            // a reset forgets it
    assert(occlusion_fold(r, 0, false, false) == 0);
    assert(occlusion_fold(r, 7, true, false) == 7);            // a count above 0 stays as counted
    return 0;
}
'''


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Count(unittest.TestCase):
    def test_running_count_compiled_and_run(self):
        compiler = native_cxx()
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "check.cpp").write_text(FOLD, encoding="utf-8")
            binary = path / ("check.exe" if os.name == "nt" else "check")
            flags = ["-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-I" + str(ROOT / "gpu/vk")]
            if os.name == "nt":
                flags.append("-static")
            built = subprocess.run([compiler, *flags, str(path / "check.cpp"), "-o", str(binary)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


class Queries(unittest.TestCase):
    def test_a_query_lives_inside_one_pass(self):
        draw = source("gpu/vk/vk_draw.cpp")
        end = draw[draw.index("void end_pass(VkCommandBuffer cmd) {"):]
        end = end[:end.index("\n}\n")]
        self.assertLess(end.index("occlusion_pass_end(cmd);"), end.index("vkCmdEndRendering(cmd);"))
        self.assertIn("    begin_pass(cmd, at);\n    occlusion_draw_in_pass(cmd);", draw)

    def test_the_module(self):
        occ = source("gpu/vk/vk_occlusion.cpp")
        self.assertIn("qi.queryType = VK_QUERY_TYPE_OCCLUSION;", occ)
        self.assertIn("if (!dev.vk12.hostQueryReset)", occ)   # (slots reset from the host: no reset commands recorded)
        self.assertIn("dev.features.occlusionQueryPrecise ? VK_QUERY_CONTROL_PRECISE_BIT : 0", occ)
        self.assertIn('getenv("RX_VK_OCCLUSION")', occ)
        # (one query active at a time: a pass's is closed before another begins, at a reset and at a report)
        self.assertIn("if (state <= 0 || !counting || open_slot >= 0) return;", occ)
        for fn in ("void occlusion_reset(", "void occlusion_report("):
            body = occ[occ.index(fn):]
            body = body[:body.index("\n}\n")]
            self.assertLess(body.index("close_open(cmd);"), body.index("push("))
        # (a full ring leaves the draw uncounted, its report at least 1)
        self.assertIn("lost = true;", occ[occ.index("void occlusion_draw_in_pass("):occ.index("void occlusion_pass_end(")])
        collect = occ[occ.index("void occlusion_collect(uint64_t done) {"):]
        collect = collect[:collect.index("\n}\n")]
        self.assertIn("entries.front().value <= done", collect)   # (in stream order, once the GPU is done)
        self.assertIn("occlusion_fold(running, sum, missed, e.reset)", collect)
        self.assertIn("guest_cpu_write(e.addr, rec, sizeof rec);", collect)
        self.assertLess(collect.index("vkGetQueryPoolResults"), collect.index("vkResetQueryPool(dev.device, pool, s, 1);"))


class Replay(unittest.TestCase):
    def test_reports_and_resets_through_the_queries(self):
        replay = source("gpu/vk/vk_replay.cpp")
        self.assertIn("const bool occ = !parallel && !dry && !worker && occlusion_on();", replay)
        report = replay[replay.index("case NOP_REPORT_COUNTER: {"):replay.index("case NOP_RESET_COUNTER: {")]
        self.assertIn("if (samples && !flag_written && occ) {", report)
        occ = report[report.index("if (samples && !flag_written && occ) {"):]
        self.assertLess(occ.index("memory_cpu_owned("), occ.index("occlusion_report(cmd, rec_value_now, c.addr, rec[1]);"))
        self.assertLess(report.index("occlusion_report("), report.index("guest_cpu_write(c.addr, rec, sizeof rec);"))
        reset = replay[replay.index("case NOP_RESET_COUNTER: {"):replay.index("case NOP_COPY_B2B: {")]
        self.assertIn("if (occ) occlusion_reset(cmd, rec_value_now);", reset)

    def test_an_unknown_count_renders(self):
        replay = source("gpu/vk/vk_replay.cpp")
        cond = replay[replay.index("case NOP_RENDER_COND: {"):replay.index("case NOP_SET_TEX_POOL:")]
        self.assertIn("if (occ && (occlusion_pending(r.addr) || occlusion_pending(r.addr + 16))) s.render_enabled = true;", cond)
        self.assertLess(cond.index("s.render_enabled = r.mode == 0 ? x == y : x != y;"), cond.index("occlusion_pending(r.addr)"))

    def test_a_skipped_draw_is_uncounted(self):
        replay = source("gpu/vk/vk_replay.cpp")
        self.assertEqual(replay.count("counted_draw([&] { draw(cmd, s, da); });"), 4)
        self.assertIn("if (k1 != k0) occlusion_draw_lost();", replay)

    def test_collected_at_each_recording_and_at_the_games_waits(self):
        replay = source("gpu/vk/vk_replay.cpp")
        begin = replay[replay.index("Recording& begin_recording(uint64_t value) {"):]
        begin = begin[:begin.index("\n}\n")]
        self.assertIn("occlusion_collect(done);", begin)
        wait = replay[replay.index("int wait(uint64_t f, uint64_t timeout_ns) {"):]
        wait = wait[:wait.index("\n}\n")]
        self.assertIn("struct Collect { ~Collect() { occlusion_collect(completed()); } } collect;", wait)
        self.assertLess(wait.index("struct Collect"), wait.index("if (completed() >= f) return 1;"))


class LaunchMode(unittest.TestCase):
    def test_the_games_occlusion_on_by_default(self):
        from akynoleyend.environment import VISUAL_MODES
        self.assertEqual(VISUAL_MODES["patched"]["AKYNO_OCCLUSION_OFF"], "0")
        self.assertEqual(VISUAL_MODES["sem-oclusao"]["AKYNO_OCCLUSION_OFF"], "1")
        # (the rest of the default mode as it was)
        for key in ("RX_VK_BARE_READ_MB", "RX_VK_KEEP_FINALIZED_MB", "RX_VK_EVICT_MIN_UNUSED"):
            self.assertEqual(VISUAL_MODES["patched"][key], VISUAL_MODES["sem-oclusao"][key])
        from akynoleyend.cli import parser
        self.assertEqual(parser().parse_args(["run", "--visual-mode", "sem-oclusao"]).visual_mode, "sem-oclusao")


if __name__ == "__main__":
    unittest.main()
