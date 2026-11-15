"""r13i: three changes from Hookshot (GPL-3.0, the base), for a 6-core CPU and an 8 GB card.

- PR 2263: the game's short sleeps wait on the timer where the process has six logical processors or fewer (host/hos_thread.c).
- PR 1334: the task and mesh stages inline the global-load helper, the floating trees (Eden's spirv_emit_context.cpp), and the
  program cache translates those programs again, once (gpu/vk/vk_shader.cpp, record kind 16).
- PR 2826: the VRAM rules let go of their excess, not an eighth of the texture cache (gpu/vk/vram_policy.h evict_target).

The sleep choice, the stale-record rule and the eviction target are compiled and run; the rest is read from the sources. No game
or GPU: none of this says how the game runs or what it draws."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from native_tools import native_cc, native_cxx  # noqa: E402


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


def build_and_run(test, compiler, name, text, flags, env=None):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path / name).write_text(text, encoding="utf-8")
        binary = path / ("check.exe" if os.name == "nt" else "check")
        if os.name == "nt":
            flags = [*flags, "-static"]
        built = subprocess.run([compiler, *flags, str(path / name), "-o", str(binary)],
                               capture_output=True, text=True, timeout=120)
        test.assertEqual(built.returncode, 0, built.stderr)
        ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30,
                             env={**os.environ, **(env or {})})
        test.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


EVICT = r'''
#include <cassert>
#include <cstdint>
#include "vram_policy.h"
using namespace mkwvk;
constexpr uint64_t MB = 1ull << 20;
int main() {
    // this PC's log: 2936 MB of textures, a few dozen MB over the 90% line. Before: 7/8 of the rule's budget, ~360 MB gone
    assert(evict_target(2936 * MB, 4096 * MB, 2876 * MB) == 2812 * MB);              // the excess and 64 MB more
    assert(evict_target(2936 * MB, 4096 * MB, 2876 * MB, false) == 2876 * MB / 8 * 7);  // RX_VK_EVICT_EXCESS=0: as before
    // no rule cut the budget: the size still asks for its 7/8
    assert(evict_target(3500 * MB, 3000 * MB, 3000 * MB) == 3000 * MB / 8 * 7);
    // over the size and over a rule: the lower of the two
    assert(evict_target(3500 * MB, 3000 * MB, 2900 * MB) == 3000 * MB / 8 * 7);
    assert(evict_target(3500 * MB, 3000 * MB, 2000 * MB) == 1936 * MB);
    // a rule's budget under the slack: down to 0, never below
    assert(evict_target(100 * MB, 3000 * MB, 40 * MB) == 0);
    // under the rule's budget (the pass is a sweep then): nothing asked for
    assert(evict_target(1000 * MB, 3000 * MB, 2000 * MB) == UINT64_MAX);
}
'''

SLEEP_MAIN = r'''
#include <assert.h>
#include <stddef.h>
#include <string.h>
#ifndef _WIN32
#include <strings.h>
#define _stricmp strcasecmp
#endif
%s
int main(void) {
    /* not set: by the processors, the game's sleeps (1) up to six of them */
    assert(hos_short_sleep_timer(NULL, 6) == 1);   /* a Ryzen 5 3500X: 6 cores, no SMT */
    assert(hos_short_sleep_timer(NULL, 4) == 1);
    assert(hos_short_sleep_timer(NULL, 1) == 1);
    assert(hos_short_sleep_timer(NULL, 8) == 0);
    assert(hos_short_sleep_timer(NULL, 16) == 0);
    assert(hos_short_sleep_timer(NULL, 0) == 0);   /* not known: as before */
    /* set: all on the timer, or all yielding */
    assert(hos_short_sleep_timer("1", 16) == 2);
    assert(hos_short_sleep_timer("yes", 6) == 2);
    assert(hos_short_sleep_timer("0", 6) == 0);
    assert(hos_short_sleep_timer("", 6) == 0);
    assert(hos_short_sleep_timer("off", 4) == 0);
    assert(hos_short_sleep_timer("FALSE", 4) == 0);
    assert(hos_short_sleep_timer("No", 4) == 0);
    return 0;
}
'''

STALE = r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
%s
int main() {
    const bool on = !getenv("EDEN_NX2_GM_INLINE") || getenv("EDEN_NX2_GM_INLINE")[0] != '0';
    assert(mesh_loads_inlined() == on);
    for (uint32_t kind = 0; kind <= kRecordKinds; kind++) {
        const bool task_mesh = (kind & 6u) != 0;
        assert(stale_mesh_record(kind) == (on && task_mesh && !(kind & kKindMeshLoadsInlined)));
    }
    assert(!stale_mesh_record(1) && !stale_mesh_record(0));   // compute and graphics records: kept, whatever the switch
    assert(stale_mesh_record(2) == on && stale_mesh_record(4) == on && stale_mesh_record(12) == on);
    assert(!stale_mesh_record(18) && !stale_mesh_record(20) && !stale_mesh_record(28));
    static_assert(kKindFloatAtomicNative == 32u && (kRecordKinds & kKindFloatAtomicNative));   // (r13l)
}
'''


def cut(text, start, end):
    at = text.index(start)
    return text[at:text.index(end, at) + len(end)]


class ShortSleep(unittest.TestCase):
    def test_choice_compiled_and_run(self):
        compiler = native_cc()
        if not compiler:
            self.skipTest("C compiler unavailable")
        host = source("host/hos_thread.c")
        part = cut(host, "enum { SHORT_SLEEP_TIMER_THREADS = 6 };", "    return threads > 0 && threads <= SHORT_SLEEP_TIMER_THREADS ? 1 : 0;\n}\n")
        build_and_run(self, compiler, "check.c", SLEEP_MAIN % part, ["-std=c11", "-O1", "-Wall", "-Wextra", "-Werror"])

    def test_the_games_sleeps_only(self):
        host = source("host/hos_thread.c")
        logged = cut(host, "void hos_sleep_logged(int64_t ns, uint64_t lr) {", "\n}\n")
        self.assertEqual(logged.count("sleep_away(ns, 1)"), 2)
        self.assertNotIn("hos_sleep_ns(ns)", logged)
        self.assertIn("void hos_sleep_ns(int64_t ns) { sleep_away(ns, 0); }", host)   # the host's: the frame limiter, audio
        # (0.4.5-test.6: or the game's main thread, test_0456_main_sleep)
        # (0.4.5-test.7: the condition in two lines, test_0456_main_sleep and test_0457_spin)
        self.assertIn("const int yields = short_timer < (guest ? 1 : 2) || ", host)
        self.assertIn("GetActiveProcessorGroupCount() == 1 && GetProcessAffinityMask(GetCurrentProcess(), &proc, &sys)", host)
        self.assertIn('hos_short_sleep_timer(getenv("HOS_SHORT_SLEEP_TIMER"), threads)', host)
        self.assertNotIn('getenv("HOS_SHORT_SLEEP_TIMER") != NULL', host)
        # (the game's SleepThread, nn::os and the kernel's, both go through hos_sleep_logged)
        self.assertIn("hos_sleep_logged((int64_t)c->x[0], c->x[30] | 1);", source("host/hos_svc.c"))
        self.assertIn("hos_sleep_logged((int64_t)ARG(0), c->x[30]);", host)


class FloatingTrees(unittest.TestCase):
    def test_eden_inlines_the_task_and_mesh_loads(self):
        eden = source("gpu/vk/eden/shader_recompiler/backend/spirv/spirv_emit_context.cpp")
        load = cut(eden, "    const auto define_load{[&](DefPtr ssbo_member, Id element_pointer, Id type, u32 shift) {", "\n    }};")
        self.assertIn('static const bool gm_inline{!getenv("EDEN_NX2_GM_INLINE") || getenv("EDEN_NX2_GM_INLINE")[0] != \'0\'};', load)
        self.assertIn("const bool inline_here{gm_inline && (stage == Stage::Task || stage == Stage::Mesh)};", load)
        self.assertIn("inline_here ? spv::FunctionControlMask::Inline : spv::FunctionControlMask::DontInline", load)
        # the store and atomic helpers stay DontInline (compute's culling programs: NVIDIA took 41 s on one inlined)
        rest = eden[eden.index(load) + len(load):]
        self.assertIn("OpFunction(void_id, spv::FunctionControlMask::DontInline, function_type)", rest)

    def test_stale_records_compiled_and_run(self):
        compiler = native_cxx()
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        shader = source("gpu/vk/vk_shader.cpp")
        part = cut(shader, "constexpr uint32_t kRecordKinds = 63u;", "    return on;\n}\n")
        part += cut(shader, "bool stale_mesh_record(uint32_t kind) {", "\n}\n")
        flags = ["-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-D_CRT_SECURE_NO_WARNINGS"]
        for env in ({}, {"EDEN_NX2_GM_INLINE": "0"}):
            with self.subTest(env=env):
                build_and_run(self, compiler, "check.cpp", STALE % part, flags, env)

    def test_the_cache_keeps_its_stamp_and_retranslates_task_and_mesh(self):
        shader = source("gpu/vk/vk_shader.cpp")
        # the same switch as Eden's
        self.assertIn('static const bool on = !getenv("EDEN_NX2_GM_INLINE") || getenv("EDEN_NX2_GM_INLINE")[0] != \'0\';', shader)
        self.assertIn("(task_mesh && mesh_loads_inlined() ? kKindMeshLoadsInlined : 0u)", shader)
        index = cut(shader, "if (rec[1]<=cache::Policy::max_record && !(kind&~kRecordKinds)) {", "                    }\n")
        self.assertLess(index.index("if (stale_mesh_record(kind)) ++stale_mesh;"), index.index("disk_records[rec[0]].push_back"))
        self.assertIn("else if (indexed<cache::policy().index_records) {", index)
        self.assertEqual(re.findall(r"constexpr uint32_t kKindMeshLoadsInlined = (\d+)u;", shader), ["16"])
        # the prepared marker differs from r13h's, so the first start prepares again (the task and mesh programs before the game)
        self.assertIn("return disk_stamp() ^ (mesh_loads_inlined() ? 0x7231336900000001ull : 0ull);", shader)
        draw = source("gpu/vk/vk_draw.cpp")
        prepare = cut(draw, "void prepare_run(void (*progress)(size_t done, size_t total)) {", "\n}\n")
        self.assertIn("const uint64_t stamp = program_prepared_stamp();", prepare)
        self.assertIn("if (FILE* f = fopen(path.c_str(), \"wb\")) fwrite(&stamp, 8, 1, f), fclose(f);", prepare)
        self.assertIn("uint64_t program_prepared_stamp();", source("gpu/vk/vk_shader.h"))


class Vram(unittest.TestCase):
    def test_evict_target_compiled_and_run(self):
        compiler = native_cxx()
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        build_and_run(self, compiler, "check.cpp", EVICT,
                      ["-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-I" + str(ROOT / "gpu/vk")])

    def test_the_eviction_pass_uses_it(self):
        texture = source("gpu/vk/vk_texture.cpp")
        self.assertIn("const uint64_t size_budget = budget;", texture)
        self.assertLess(texture.index("uint64_t budget = own;"), texture.index("const uint64_t size_budget = budget;"))
        self.assertLess(texture.index("const uint64_t size_budget = budget;"),
                        texture.index("if (known && pressure > allowed / 10 * 9) {"))
        self.assertIn("const uint64_t evict_to = evict_target(total_bytes, size_budget, budget, excess_only);", texture)
        self.assertIn("if ((!sweep && total_bytes <= evict_to) ||", texture)
        self.assertNotIn("total_bytes <= budget / 8 * 7", texture)


if __name__ == "__main__":
    unittest.main()
