"""0.4.5-test.1, unified: the F1 panel's Render distance. The hook in the lifted code (nx2/oot_patches.py patch_render_distance,
after the engine's perspective projection loads its near and far planes) is applied to a stand-in of that function and run with
the host's own clamp (host/nn_vi.c), compiled alone; the panel's row, its option id and the update's stamp are read from the
sources. No game here: none of this says what the picture or the frame rate is at a given distance."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "nx2"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import oot_patches as patches  # noqa: E402
from native_tools import native_cc  # noqa: E402


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


def block(text, head):
    """The function starting with head, to its closing brace at column 0"""
    start = text.index(head)
    return text[start:text.index("\n}\n", start) + 3]


# (a stand-in with the function's shape: the load of both planes, once, and the depth row's -1 after it)
LIFTED = ('#include "a64.h"\n'
          "void f_834a5cc0(Ctx *__restrict A64_NOESC c) {\n"
          "    a64_vset64(c->vreg[2],0x3f800000ULL);\n"
          + patches.FAR_OLD +
          "    c->x[8] = 0xbf800000ULL;\n"
          "return;\n"
          "}\n"
          "void f_834a5d80(Ctx *__restrict A64_NOESC c) {\n"
          "    { { uint64_t _v=recomp_load32(c,(c->x[0]+152ULL)); a64_vset64(c->vreg[0],_v); } }\n"
          "return;\n"
          "}\n")


class Patch(unittest.TestCase):
    def test_hook_after_the_planes_are_loaded(self):
        out = patches.patch_render_distance(LIFTED)
        self.assertEqual(out.count(patches.FAR_MARK), 1)
        self.assertEqual(out.index(patches.FAR_OLD) + len(patches.FAR_OLD), out.index(patches.FAR_ADD % (0, 0)))
        self.assertLess(out.index(patches.FAR_ADD % (0, 0)), out.index("0xbf800000ULL"))
        self.assertEqual(out.count(patches.FAR_DECL), 1)
        self.assertEqual(patches.patch_render_distance(out), out)   # (a second run)

    def test_the_cameras_inlined_copy(self):
        # (f_8035a8c0: the same code on x2, among other loads of +152 on other registers)
        lifted = (LIFTED.replace("f_834a5cc0", "f_8035a8c0").replace("c->x[0]; int64_t _o=152;", "c->x[2]; int64_t _o=152;")
                  .replace("a64_vset64(c->vreg[2],0x3f800000ULL);\n",
                           "a64_vset64(c->vreg[2],0x3f800000ULL);\n    { uint64_t _b=c->x[19]; int64_t _o=152; }\n"))
        out = patches.patch_render_distance(lifted)
        self.assertEqual(out.count(patches.FAR_MARK), 1)
        load = patches.FAR_LOAD % 2
        self.assertEqual(out.index(load) + len(load), out.index(patches.FAR_ADD % (2, 2)))
        self.assertEqual(patches.patch_render_distance(out), out)
        self.assertEqual([reg for _, reg in patches.FAR_SITES], [0, 2])

    def test_the_v4_hook_is_replaced(self):
        # (a work updated with the matrix-only hook: the new one in its place, its declaration swapped)
        v4 = LIFTED.replace(patches.FAR_OLD, patches.FAR_OLD + patches.FAR_ADD_V4).replace(
            '#include "a64.h"\n', '#include "a64.h"\n' + patches.FAR_DECL_V4)
        out = patches.patch_render_distance(v4)
        self.assertNotIn(patches.FAR_ADD_V4, out)
        self.assertNotIn(patches.FAR_DECL_V4, out)
        self.assertEqual(out, patches.patch_render_distance(LIFTED))

    def test_left_alone_elsewhere(self):
        self.assertIsNone(patches.patch_render_distance(LIFTED.replace("f_834a5cc0", "f_834a5cc4")))
        # (another game version: the planes loaded another way, or twice, or no depth row)
        for other in (LIFTED.replace("_o=152;", "_o=156;"), LIFTED.replace(patches.FAR_OLD, patches.FAR_OLD * 2),
                      LIFTED.replace("0xbf800000ULL", "0x3f000000ULL")):
            self.assertEqual(patches.patch_render_distance(other), other)

    def test_among_the_panel_hooks(self):
        names = [name for name, _, _ in patches.PANEL_HOOKS]
        self.assertEqual(names[-1], "render distance")
        text, held = patches.patch_panel_hooks(LIFTED)
        self.assertIn("render distance", held)
        self.assertIn(patches.FAR_MARK, text)

    def test_registers_through_ctx_and_the_update_looks_again(self):
        self.assertIn("0x834A5CC0", source("nx2/lift.py"))
        upgrade = source("nx2/upgrade_output.py")
        self.assertIn('HOOKS_STAMP = "akyno-panel-hooks-r13-v5"', upgrade)
        self.assertIn("oot_patches.FAR_HEADS", upgrade)
        self.assertIn("0x8035A8C0", source("nx2/lift.py"))
        self.assertIn('HOOKS_STAMP = "akyno-panel-hooks-r13-v5"', source("akynoleyend/maintenance.py"))


FIXTURE = r'''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); exit(1); } } while (0)
typedef long LONG;
static LONG InterlockedIncrement(volatile LONG *v) { return ++*v; }
typedef int SRWLOCK;
#define SRWLOCK_INIT 0
static int locked;
static void AcquireSRWLockExclusive(SRWLOCK *l) { (void)l; CHECK(!locked); locked = 1; }
static void ReleaseSRWLockExclusive(SRWLOCK *l) { (void)l; CHECK(locked); locked = 0; }
static int logged;
static void hos_log(const char *f, ...) { (void)f; logged++; }
typedef struct { uint64_t x[32]; uint64_t vreg[32][2]; } Ctx;
static inline void a64_vset64(uint64_t *d, uint64_t v) { d[0] = v; d[1] = 0; }
static float kept_far[4];                          /* (the projections' far field, +0x9c of the object at 0x1000 * (i + 1)) */
static int stores;
static void recomp_store32(Ctx *c, uint64_t at, uint32_t v) {
    (void)c;
    CHECK(at % 0x1000 == 156 && at / 0x1000 >= 1 && at / 0x1000 <= 4);
    memcpy(&kept_far[at / 0x1000 - 1], &v, 4), stores++;
}
@IDS@
@HOST@
static float frame(int which, float near_plane) {  /* the update of projection which: its planes loaded, then the hook */
    Ctx ctx, *c = &ctx;
    uint32_t n, f;
    memset(c, 0, sizeof *c);
    c->x[0] = 0x1000u * (uint64_t)(which + 1);
    memcpy(&n, &near_plane, 4), memcpy(&f, &kept_far[which], 4);
    a64_vset64(c->vreg[4], n), a64_vset64(c->vreg[3], f);
@SNIPPET@    float r;
    memcpy(&r, c->vreg[3], 4);
    CHECK(c->vreg[3][1] == 0);
    return r;
}
int main(void) {
    CHECK(akyno_render_distance(0) == 0 && akyno_render_distance(1) == 2500 && akyno_render_distance(8) == 60);
    CHECK(akyno_render_distance(9) == 0 && akyno_render_distance(-1) == 0);
    for (int row = 2; row <= 8; row++) CHECK(akyno_render_distance(row) < akyno_render_distance(row - 1));
    CHECK(render_far(NULL, 0) == 0.0f && render_far(NULL, 4) == 400.0f && render_far("", 4) == 400.0f);
    CHECK(render_far("123.5", 4) == 123.5f && render_far("0", 4) == 0.0f);   /* AKYNO_RENDER_DISTANCE over the row */
    kept_far[0] = 20000.0f, kept_far[1] = 399.0f, kept_far[2] = 20000.0f, kept_far[3] = 20000.0f;
    hos_render_far = 0.0f;                         /* the game's own: nothing written */
    CHECK(frame(0, 0.1f) == 20000.0f && stores == 0);
    hos_render_far = 400.0f;
    CHECK(frame(0, 0.1f) == 400.0f && kept_far[0] == 400.0f);   /* the camera: cut at the limit, in the projection too */
    CHECK(frame(0, 0.1f) == 400.0f && stores == 1);             /* (the next frames: kept, nothing more written) */
    CHECK(frame(1, 0.1f) == 399.0f && kept_far[1] == 399.0f);   /* inside it already */
    CHECK(frame(2, 150.0f) == 20000.0f);           /* a near plane not well inside the limit */
    CHECK(frame(3, 0.0f) == 20000.0f && stores == 1);
    hos_render_far = 1000.0f;                      /* raised: the game's own value gives the new limit */
    CHECK(frame(0, 0.1f) == 1000.0f && kept_far[0] == 1000.0f);
    hos_render_far = 0.0f;                         /* lifted: the game's own value back in the projection */
    CHECK(frame(0, 0.1f) == 20000.0f && kept_far[0] == 20000.0f);
    CHECK(frame(0, 0.1f) == 20000.0f && stores == 3);
    hos_render_far = 400.0f;                       /* the game sets another far plane while the limit is on */
    CHECK(frame(0, 0.1f) == 400.0f);
    kept_far[0] = 300.0f;
    CHECK(frame(0, 0.1f) == 300.0f && kept_far[0] == 300.0f);
    hos_render_far = 0.0f;
    CHECK(frame(0, 0.1f) == 300.0f);
    CHECK(logged > 0 && logged <= 12 && !locked);  /* (the planes seen, a few) */
    return 0;
}
'''


class Host(unittest.TestCase):
    def test_the_far_plane_the_matrix_is_made_with(self):
        compiler = native_cc()
        if not compiler:
            self.skipTest("C compiler unavailable")
        host = source("host/nn_vi.c")
        ids = block(source("gpu/vk/menu_option_ids.h"), "static inline int akyno_render_distance(int row) {")
        body = ("volatile float hos_render_far = 0.0f;\n" + block(host, "static float render_far(") +
                block(host, "float hos_render_far_clamp(") + block(host, "float hos_render_far_site("))
        text = FIXTURE.replace("@IDS@", ids).replace("@HOST@", body).replace("@SNIPPET@", patches.FAR_ADD % (0, 0))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "t.c").write_text(text, encoding="utf-8")
            binary = path / ("t.exe" if os.name == "nt" else "t")
            built = subprocess.run([compiler, "-std=gnu11", "-O1", "-Wall", "-Wextra", "-Werror", str(path / "t.c"), "-o",
                                    str(binary)], capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_read_every_present(self):
        host = source("host/nn_vi.c")
        step = block(host, "static void realtime_step(")
        self.assertIn("render_far(env, rx_option(AKYNO_OPT_RENDER_DISTANCE, 0))", step)
        self.assertIn('getenv("AKYNO_RENDER_DISTANCE")', step)
        self.assertLess(step.index("hos_render_far = limit;"), step.index("if (!mod) return;"))
        self.assertIn("extern float hos_render_far_site(uint64_t at, float near_plane, float far_plane);", patches.FAR_DECL)


class Panel(unittest.TestCase):
    def test_row_and_option(self):
        menu = source("gpu/vk/vk_menu.cpp")
        self.assertIn('{"Render distance", "Distância de renderização", &opts.render_distance, 0, 8, 1, tx_render_distance,', menu)
        self.assertIn("FgMax, FgTarget, RenderDistance, SettingCount };", menu)
        video = re.search(r"constexpr Setting video_rows\[\] = \{(.*?)\};", menu, re.S).group(1)
        self.assertIn("RenderDistance", video)
        restart = re.search(r"constexpr Setting restart_rows\[\] = \{(.*?)\};", menu, re.S).group(1)
        self.assertNotIn("RenderDistance", restart)   # (at once)
        self.assertIn("int render_distance = 0;", source("gpu/vk/vk_menu.h"))
        self.assertIn("case AKYNO_OPT_RENDER_DISTANCE: return opts.render_distance;", source("gpu/vk/vk_replay.cpp"))

    def test_id_after_the_earlier_ones(self):
        ids = source("gpu/vk/menu_option_ids.h")
        order = re.findall(r"\b(AKYNO_OPT_\w+)", re.search(r"enum \{(.*?)\};", ids, re.S).group(1))
        self.assertEqual(order[-1], "AKYNO_OPT_RENDER_DISTANCE")
        self.assertEqual(order[-2], "AKYNO_OPT_HDR_WHITE")


if __name__ == "__main__":
    unittest.main()
