"""r13: Hookshot v2.1.0's ultrawide HUD, movie and save-picture sites (its nx2/oot_wide.py, commit 8ef84611) and its Ultrawide
menus row: the three sites placed by text in the lifted C (nx2/oot_patches.py), each compiled alone and run against a stand-in
of the game's memory, their update for a work lifted before them, and where the host and the renderer take the row. No game
or GPU: none of this says the menus were seen on an ultrawide screen."""
import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_r13_text_mouse import compile_and_run, load, patches, source  # noqa: E402

# (the shape of the three lifted functions, build e0f3ccfa, around each site)
HUD_LIFTED = ('#include "a64.h"\n' + patches.WIDE_HUD_HEAD
              + "    { uint64_t _b=c->x[2]; int64_t _o=32; recomp_ldp64(c,(_b+_o),&c->vreg[5][0],&c->vreg[5][1]); }\n"
              + patches.WIDE_HUD_AT + "    a64_vfpx_mul32(c,c->vreg[1],c->vreg[16],c->vreg[0],4);\n}\n")
MOVIE_LIFTED = ('#include "a64.h"\n' + patches.WIDE_MOVIE_HEAD + "L_83b7c744:; A64_POLL(c);\n"
                + patches.WIDE_MOVIE_AT + "    c->x[1]=recomp_load64(c,c->x[19] + 88);\n"
                + "c->x[30] = 0x83b7c774ULL; f_809ebaf0(c);\n"
                + patches.WIDE_MOVIE_AT.split("\n", 1)[1] + "}\n")
THUMB_LIFTED = ('#include "a64.h"\n' + patches.WIDE_THUMB_HEAD
                + patches.WIDE_THUMB_AT + "{ uint64_t _t = c->x[8]; c->x[30] = 0x802a4808ULL; A64_ICALL(c, _t); }\n"
                + "    c->x[8]=recomp_load64(c,c->x[8] + 2008);\n"
                + patches.WIDE_THUMB_AT + patches.WIDE_THUMB_NEXT + "\n}\n")

SITES_FIXTURE = r'''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); exit(1); } } while (0)
typedef struct { uint64_t x[32]; uint64_t vreg[32][2]; } Ctx;
static uint8_t mem[0x1000];   /* (the game's memory, at address 0x10000) */
static uint64_t recomp_load64(Ctx *c, uint64_t a) { uint64_t v; (void)c; memcpy(&v, mem + (a - 0x10000), 8); return v; }
static uint64_t recomp_load32(Ctx *c, uint64_t a) { uint32_t v; (void)c; memcpy(&v, mem + (a - 0x10000), 4); return v; }
static void recomp_store32(Ctx *c, uint64_t a, uint64_t v) { const uint32_t w = (uint32_t)v; (void)c; memcpy(mem + (a - 0x10000), &w, 4); }
volatile float hos_wide_ratio, hos_wide_squeeze, hos_wide_margin;
volatile uint32_t hos_wide_keep_mask = 0xf;
static int close_to(float a, float b) { const float d = a - b; return d < 1e-6f && d > -1e-6f; }

static void hud(Ctx *c) {
    @HUD@
}
static void movie(Ctx *c) {
    @MOVIE@
}
static void thumb(Ctx *c) {
    @THUMB@
}

/* the canvas at 0x10400, its screen's vtable 0x1b8 before it; the layout's first projection row in q1, the second in q4 */
static float hud_row(Ctx *c, uint64_t vtable, float m00, float m11) {
    const float row1[4] = {m00, 0.0f, 0.0f, -1.0f}, row4[4] = {0.0f, m11, 0.0f, 1.0f};
    memcpy(mem + 0x400 - 0x1b8, &vtable, 8);
    c->x[0] = 0x10400;
    memcpy(c->vreg[1], row1, 16), memcpy(c->vreg[4], row4, 16);
    hud(c);
    float out[4];
    memcpy(out, c->vreg[1], 16);
    CHECK(close_to(out[3], -1.0f * (out[0] / m00)));   /* (the whole row, by the same factor) */
    return out[0] / m00;
}

int main(void) {
    Ctx c;
    memset(&c, 0, sizeof c);
    const float ui_x = 2.0f / 3840.0f, ui_y = 2.0f / 2160.0f;
    const uint64_t hud_screen = 0x1234, pause = @KEEP1@ULL, wheel = @KEEP0@ULL, map = @KEEP3@ULL, fades = @KEEP2@ULL;

    /* 16:9: nothing changes */
    CHECK(close_to(hud_row(&c, hud_screen, ui_x, ui_y), 1.0f));
    /* 21:9 (3440 x 1440): the HUD's row by 16:9 over the ratio; the kept screens whole */
    hos_wide_ratio = 3440.0f / 1440.0f, hos_wide_squeeze = (16.0f / 9.0f) / hos_wide_ratio, hos_wide_margin = (1.0f - hos_wide_squeeze) / 2.0f;
    CHECK(close_to(hud_row(&c, hud_screen, ui_x, ui_y), hos_wide_squeeze));
    CHECK(close_to(hud_row(&c, pause, ui_x, ui_y), 1.0f) && close_to(hud_row(&c, map, ui_x, ui_y), 1.0f));
    CHECK(close_to(hud_row(&c, wheel, ui_x, ui_y), 1.0f) && close_to(hud_row(&c, fades, ui_x, ui_y), 1.0f));
    /* the panel's Ultrawide menus at Centred: the pause and map menus' bits cleared, the wheel's and the fades' kept */
    hos_wide_keep_mask = 0xf & ~0xa;
    CHECK(close_to(hud_row(&c, pause, ui_x, ui_y), hos_wide_squeeze) && close_to(hud_row(&c, map, ui_x, ui_y), hos_wide_squeeze));
    CHECK(close_to(hud_row(&c, wheel, ui_x, ui_y), 1.0f) && close_to(hud_row(&c, fades, ui_x, ui_y), 1.0f));
    /* another projection (not the UI's full-screen one) is left alone */
    CHECK(close_to(hud_row(&c, hud_screen, 2.0f / 1920.0f, ui_y), 1.0f));

    /* a movie's viewport, min x and max x at x29 - 32 and x29 - 24: each side in by the margin */
    {
        const float a = 0.0f, b = 2560.0f;
        c.x[29] = 0x10800;
        memcpy(mem + 0x800 - 32, &a, 4), memcpy(mem + 0x800 - 24, &b, 4);
        movie(&c);
        float na, nb;
        memcpy(&na, mem + 0x800 - 32, 4), memcpy(&nb, mem + 0x800 - 24, 4);
        CHECK(close_to(na / 2560.0f, hos_wide_margin) && close_to(nb / 2560.0f, 1.0f - hos_wide_margin));
        CHECK(close_to((nb - na) / 2560.0f, hos_wide_squeeze));
    }

    /* the save's picture, SetViewport(0, 0, 543, 306): wider by the ratio over 16:9, centred; any other viewport as it is */
    c.x[1] = 0, c.x[2] = 0, c.x[3] = 543, c.x[4] = 306;
    thumb(&c);
    CHECK((uint32_t)c.x[3] == 730 && (int32_t)(uint32_t)c.x[1] == (543 - 730) / 2 && c.x[2] == 0 && c.x[4] == 306);
    c.x[1] = 0, c.x[2] = 0, c.x[3] = 2560, c.x[4] = 1440;
    thumb(&c);
    CHECK(c.x[1] == 0 && c.x[3] == 2560 && c.x[4] == 1440);
    /* 16:10 (the 2560 x 1600 output): the HUD and movies over the whole width, the save's picture taller instead */
    hos_wide_ratio = 1.6f, hos_wide_squeeze = 1.0f, hos_wide_margin = 0.0f, hos_wide_keep_mask = 0xf;
    CHECK(close_to(hud_row(&c, hud_screen, ui_x, ui_y), 1.0f));
    c.x[1] = 0, c.x[2] = 0, c.x[3] = 543, c.x[4] = 306;
    thumb(&c);
    CHECK(c.x[3] == 543 && (uint32_t)c.x[4] == 340 && (int32_t)(uint32_t)c.x[2] == (306 - 340) / 2);
    return 0;
}
'''


class Sites(unittest.TestCase):
    def test_each_once_after_its_instruction(self):
        hud = patches.patch_wide_hud(HUD_LIFTED)
        self.assertEqual(hud.count(patches.WIDE_HUD_MARK), 1)
        self.assertIn(patches.WIDE_HUD_AT + "    " + patches.WIDE_HUD + "\n    a64_vfpx_mul32(", hud)
        movie = patches.patch_wide_movie(MOVIE_LIFTED)
        self.assertEqual(movie.count(patches.WIDE_MOVIE_MARK), 1)
        # (after the load that follows the first call, not the same load after the second)
        self.assertLess(movie.index(patches.WIDE_MOVIE_MARK), movie.index("0x83b7c774ULL"))
        thumb = patches.patch_wide_thumb(THUMB_LIFTED)
        self.assertEqual(thumb.count(patches.WIDE_THUMB_MARK), 1)
        # (before SetViewport's call, not SetScissor's, which loads its address the same way)
        self.assertLess(thumb.index("0x802a4808ULL"), thumb.index(patches.WIDE_THUMB_MARK))
        self.assertIn(patches.WIDE_THUMB_MARK + "\n" + patches.WIDE_THUMB_NEXT, thumb)
        for fn, text in ((patches.patch_wide_hud, hud), (patches.patch_wide_movie, movie), (patches.patch_wide_thumb, thumb)):
            self.assertEqual(fn(text), text)   # (a lift patched again)

    def test_left_out_where_the_text_differs(self):
        for fn, lifted, at in ((patches.patch_wide_hud, HUD_LIFTED, patches.WIDE_HUD_AT),
                               (patches.patch_wide_movie, MOVIE_LIFTED, "0x83b7c758ULL"),
                               (patches.patch_wide_thumb, THUMB_LIFTED, "0x802a482cULL")):
            self.assertIsNone(fn("void f_1(Ctx *c) {\n}\n"))                 # (not this file)
            self.assertIsNone(fn(lifted.replace(at, at.replace("c->", "d->") if "c->" in at else "0x1ULL")))   # (another version)
        # (the HUD's load twice in the function: which one is not known, none is taken)
        twice = HUD_LIFTED.replace(patches.WIDE_HUD_AT, patches.WIDE_HUD_AT * 2)
        self.assertIsNone(patches.patch_wide_hud(twice))

    def test_among_the_panels_hooks(self):
        names = [name for name, _, _ in patches.PANEL_HOOKS]
        self.assertEqual(names[3:6], ["ultrawide HUD", "ultrawide movies", "ultrawide save picture"])   # (then the render distance: test_0451_render_distance.py)
        text, held = patches.patch_panel_hooks(HUD_LIFTED)
        self.assertEqual(held, ["ultrawide HUD"])
        self.assertEqual(patches.patch_panel_hooks(text), (text, held))

    def test_hookshots_texts_and_credit(self):
        # (the three texts as Hookshot v2.1.0 wrote them: next/scripts/port_r13_wide.py checks them against its file when it
        # copies; here their fingerprints, so a later hand edit shows)
        digest = lambda text: hashlib.sha256(text.encode()).hexdigest()[:16]
        self.assertEqual([digest(patches.WIDE_HUD), digest(patches.WIDE_MOVIE), digest(patches.WIDE_THUMB)], WIDE_DIGESTS)
        text = source("nx2/oot_patches.py")
        self.assertIn("Copyright (c) 2026 Ivan0xFF", text)
        self.assertIn("Hookshot v2.1.0's nx2/oot_wide.py, commit 8ef84611, GPL-3.0", text)

    def test_what_each_does(self):
        fixture = SITES_FIXTURE.replace("@HUD@", patches.WIDE_HUD).replace("@MOVIE@", patches.WIDE_MOVIE)
        fixture = fixture.replace("@THUMB@", patches.WIDE_THUMB)
        for k, vtable in enumerate(patches.WIDE_KEEP_VTABLES):
            fixture = fixture.replace("@KEEP%d@" % k, "0x%x" % vtable)
        compile_and_run(self, {"t.c": fixture}, ["t.c"], ["-lm"])


WIDE_DIGESTS = ["b67cfe1b74c817f2", "dc65a5ad66849042", "7c8ceded58282762"]


class ByUpdate(unittest.TestCase):
    def test_an_update_adds_them_to_a_work_lifted_before(self):
        sys.path.insert(0, str(ROOT / "nx2"))
        try:
            module = load("upgrade_output_r13_wide", "nx2/upgrade_output.py")
        except Exception as error:   # (nx2/build.py wants the project's toolchain layout)
            self.skipTest("nx2/upgrade_output.py not importable here: %s" % error)
        with tempfile.TemporaryDirectory() as tmp:
            gen = Path(tmp)
            (gen / "code_017.c").write_bytes(HUD_LIFTED.encode())
            (gen / "code_176.c").write_bytes(MOVIE_LIFTED.replace("\n", "\r\n").encode())
            (gen / "code_hot_4.c").write_bytes(THUMB_LIFTED.encode())
            edits, held = module.hook_edits(gen, {})
            self.assertEqual(held, {"ultrawide HUD", "ultrawide movies", "ultrawide save picture"})
            self.assertEqual(sorted(p.name for p in edits), ["code_017.c", "code_176.c", "code_hot_4.c"])
            crlf = edits[gen / "code_176.c"]
            self.assertIn(patches.WIDE_MOVIE_MARK.encode(), crlf)
            self.assertNotIn(b"\n", crlf.replace(b"\r\n", b""))   # (every line end still CRLF)
            for path, data in edits.items():
                path.write_bytes(data)
            self.assertEqual(module.hook_edits(gen, {}), ({}, held))

    def test_the_stamp_was_renamed_so_a_work_is_looked_at_again(self):
        self.assertIn('HOOKS_STAMP = "akyno-panel-hooks-r13-v5"', source("nx2/upgrade_output.py"))
        self.assertIn('HOOKS_STAMP = "akyno-panel-hooks-r13-v5"', source("akynoleyend/maintenance.py"))


class HostAndRenderer(unittest.TestCase):
    def test_the_host_gives_the_sites_their_numbers(self):
        main = source("host/hos_main.c")
        self.assertIn("volatile float hos_wide_ratio, hos_wide_squeeze, hos_wide_margin;", main)
        self.assertIn("volatile uint32_t hos_wide_keep_mask = 0xf;", main)
        boot = main[main.index('hos_log("boot: aspect ratio %.4f in place of %.4f", want, was);'):]
        boot = boot[:boot.index("} else if (want > 1.0f)")]
        self.assertIn("if (want > 16.0f / 9.0f || hos_output_mode() == 5) {", boot)
        self.assertIn("const float squeeze = want > 16.0f / 9.0f ? (16.0f / 9.0f) / want : 1.0f;", boot)
        self.assertIn("hos_wide_margin = (1.0f - squeeze) / 2.0f;", boot)

    def test_the_row_reaches_the_game_without_vk_api(self):
        backend, vi, framegen = source("host/rx_backend.c"), source("host/nn_vi.c"), source("gpu/vk/vk_framegen.cpp")
        self.assertIn('GetProcAddress(vk_module, "akyno_wide_menus")', backend)
        self.assertIn("const uint32_t mask = ask ? ask(margin) : 0xfu;", backend)
        step = vi[vi.index("static void realtime_step("):]
        self.assertLess(step.index("hos_wide_keep_mask = mask;"), step.index("if (!mod) return;"))
        self.assertIn("if (hos_wide_margin > 0.0f) {", step)
        self.assertIn('extern "C" __declspec(dllexport) uint32_t akyno_wide_menus(float margin) {', framegen)
        self.assertIn("return mkwvk::opts.wide_menus ? 0xfu & ~0xau : 0xfu;", framegen)
        self.assertNotIn("wide_menus", source("gpu/vk/vk_api.h"))
        from akynoleyend.build_support import shader_cache_stamp
        self.assertEqual(shader_cache_stamp(ROOT / "gpu/vk"), "4cdbb0029868040b")

    def test_row_world_and_sides(self):
        menu, header = source("gpu/vk/vk_menu.cpp"), source("gpu/vk/vk_menu.h")
        self.assertIn("int wide_menus = 1;", header)
        self.assertIn('{"Ultrawide menus", "Menus em ultrawide", &opts.wide_menus, 0, 2, 1, tx_wide_menus,', menu)
        self.assertRegex(menu, r"video_rows\[\] = \{[^}]*Ultrawide, WideMenus,")
        self.assertNotIn("WideMenus", re.search(r"restart_rows\[\] = \{([^}]*)\}", menu).group(1))   # (at once)
        draw = source("gpu/vk/vk_draw.cpp")
        self.assertIn("if (cp->key == 0x1a7482c0ec9991eaULL) world_drawn_at.store(presents_now, std::memory_order_relaxed);", draw)
        self.assertIn("if (cp->key == 0x02ff9920c2571cc2ULL) wheel_drawn_at.store(presents_now, std::memory_order_relaxed);", draw)
        self.assertLess(draw.index("world_drawn_at.store("), draw.index("if (skip_live(cp->key)) return;"))
        framegen = source("gpu/vk/vk_framegen.cpp")
        sides = framegen[framegen.index("WideSides wide_sides() {"):framegen.index("void wide_sides_tick()")]
        self.assertIn("if (opts.wide_menus && margin > 0.0f && no_world) w.x0 = margin, w.side = std::clamp(opts.wide_menus, 1, 2);", sides)
        made = framegen[framegen.index("VkImage framegen_sides("):framegen.index("VkImageView framegen_scaled_view(")]
        self.assertIn("make_pipe(sides.pipe, WIDE_SIDES_COMP_SPV, sizeof WIDE_SIDES_COMP_SPV, {S, I, S}, 20)", made)
        self.assertIn("pc{0, 0.0f, wide.x0, 1.0f - wide.x0, wide.side};", made)
        replay = source("gpu/vk/vk_replay.cpp")
        present = replay[replay.index("void present_image("):]
        self.assertLess(present.index("framegen_scale(f.cmd, view, src,"), present.index("framegen_sides(f.cmd, view, src, sw, sh, crop,"))
        self.assertLess(present.index("if (sided) scaled = sided;"), present.index("const VkImage hdr_image"))
        self.assertIn("wide_sides_tick();", replay[replay.index("void do_present("):replay.index("void present_image(")])

    def test_the_sides_shader_is_hookshots(self):
        shaders = ROOT / "gpu/vk/shaders"
        comp = (shaders / "wide_sides.comp").read_bytes()
        header = (shaders / "wide_sides_comp_spv.h").read_bytes()
        self.assertEqual(hashlib.sha256(comp).hexdigest(), "8fa651e772e5095ebdd47bd844fd2a637ccae7ff9e851d2235751f44bb09367c")
        self.assertIn(b"// fg_scale.comp sha256 8fa651e772e5095ebdd47bd844fd2a637ccae7ff9e851d2235751f44bb09367c", header)
        self.assertIn(b"const uint32_t WIDE_SIDES_COMP_SPV[] = {\n\t0x07230203,", header)
        self.assertIn(b"layout(push_constant) uniform P { int mode; float sharp; float x0; float x1; int side; } pc;", comp)


if __name__ == "__main__":
    unittest.main()
