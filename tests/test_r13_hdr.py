"""r13: Hookshot v2.1.0's HDR (commit 8ef84611): the shader as copied, the panel's pixels for an HDR10 image compiled alone
(gpu/vk/hdr10_pixels.h), and where the renderer and the host take the rows. No game, GPU or display: none of this says HDR was
seen on an HDR screen."""
import hashlib
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_r13_text_mouse import compile_and_run, source  # noqa: E402

PIXELS_FIXTURE = r'''#include <stdio.h>
#include <stdlib.h>
#include "hdr10_pixels.h"
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); exit(1); } } while (0)
static int close_to(uint32_t a, uint32_t b) { return a > b ? a - b <= 1 : b - a <= 1; }
int main(void) {
    /* (SMPTE ST 2084: 100 nits is 0.508 of the signal, 203 is 0.581, 1000 is 0.752, 10000 is all of it) */
    CHECK(close_to(akyno_hdr10_code(1.0f, 100.0f), 520));
    CHECK(close_to(akyno_hdr10_code(1.0f, 203.0f), 594));
    CHECK(close_to(akyno_hdr10_code(1.0f, 1000.0f), 769));
    CHECK(akyno_hdr10_code(1.0f, 10000.0f) == 1023);
    CHECK(akyno_hdr10_code(4.0f, 10000.0f) == 1023);
    CHECK(akyno_hdr10_code(-1.0f, 203.0f) == 0);
    /* black stays black (the FPS counter's key), opaque */
    CHECK(akyno_hdr10_pixel(0, 0, 0, 203.0f, 1) == 3u << 30);
    CHECK(akyno_hdr10_pixel(0, 0, 0, 203.0f, 0) == 3u << 30);
    /* white stays neutral, at the paper white */
    const uint32_t w = akyno_hdr10_pixel(255, 255, 255, 203.0f, 1);
    CHECK(close_to(w & 1023, 594) && close_to(w >> 10 & 1023, 594) && close_to(w >> 20 & 1023, 594) && w >> 30 == 3);
    /* a brighter paper white is a higher code */
    CHECK((akyno_hdr10_pixel(255, 255, 255, 400.0f, 1) & 1023) > (w & 1023));
    /* sRGB's red in Rec. 2020: mostly red, some green, a little blue; the word's order follows the swapchain's format */
    const uint32_t red_low = akyno_hdr10_pixel(255, 0, 0, 203.0f, 1), blue_low = akyno_hdr10_pixel(255, 0, 0, 203.0f, 0);
    const uint32_t r = red_low & 1023, g = red_low >> 10 & 1023, b = red_low >> 20 & 1023;
    CHECK(r > g && g > b && b > 0);
    CHECK(r == akyno_hdr10_code(0.6274f, 203.0f) && g == akyno_hdr10_code(0.0691f, 203.0f) && b == akyno_hdr10_code(0.0164f, 203.0f));
    CHECK((blue_low >> 20 & 1023) == r && (blue_low >> 10 & 1023) == g && (blue_low & 1023) == b);
    /* mid grey: sRGB 128 is 0.216 linear */
    CHECK(close_to(akyno_hdr10_pixel(128, 128, 128, 203.0f, 1) & 1023, akyno_hdr10_code(0.2158f, 203.0f)));
    /* the rows' limits */
    CHECK(akyno_hdr_white(0) == 80 && akyno_hdr_white(200) == 200 && akyno_hdr_white(9999) == 500);
    CHECK(akyno_hdr_peak(0) == 400 && akyno_hdr_peak(1000) == 1000 && akyno_hdr_peak(99999) == 10000);
    return 0;
}
'''


class Shader(unittest.TestCase):
    def test_hookshots_files_as_they_are(self):
        shaders = ROOT / "gpu/vk/shaders"
        comp = (shaders / "hdr_encode.comp").read_bytes()
        header = (shaders / "hdr_encode_comp_spv.h").read_bytes()
        self.assertEqual(hashlib.sha256(comp).hexdigest(), "5079b8f41159e043bd7ed40c3dc235d1c1506107d0f1e3e56bad07f97f8e9a88")
        self.assertEqual(hashlib.sha256(header).hexdigest(), "358508624cc8f6692785144ee066ddca3f69d7ecd1de2a11a1a70603068163ac")
        # (the header names the source it was compiled from)
        self.assertIn(hashlib.sha256(comp).hexdigest().encode(), header)
        self.assertIn(b"const uint32_t HDR_ENCODE_COMP_SPV[] = {\n\t0x07230203,", header)

    def test_the_panels_pixels_use_the_shaders_numbers(self):
        comp, pixels = source("gpu/vk/shaders/hdr_encode.comp"), source("gpu/vk/hdr10_pixels.h")
        matrix = re.search(r"mat3\(([^)]*)\)", comp).group(1)
        m = [float(v) for v in matrix.split(",")]   # (GLSL: columns)
        for row in range(3):
            self.assertIn("%.4ff * lr + %.4ff * lg + %.4ff * lb" % (m[row], m[3 + row], m[6 + row]), pixels)
        for constant in ("0.1593017578125", "78.84375", "0.8359375", "18.8515625", "18.6875"):
            self.assertIn(constant, comp)
            self.assertIn(constant + "f", pixels)


class PanelPixels(unittest.TestCase):
    def test_encoded_as_hdr10(self):
        compile_and_run(self, {"hdr10_pixels.h": source("gpu/vk/hdr10_pixels.h"), "t.c": PIXELS_FIXTURE}, ["t.c"], ["-lm"])

    def test_the_panel_draws_them_and_draws_again_when_the_image_changes(self):
        menu = source("gpu/vk/vk_menu.cpp")
        draw = menu[menu.index("void gdi_draw("):menu.index("int cur_scale = 1;")]
        self.assertIn("if (dev.hdr) {", draw)
        self.assertIn("akyno_hdr10_pixel(p[2], p[1], p[0], (float)white, red_low)", draw)
        self.assertIn("dev.swap_format == VK_FORMAT_A2B10G10R10_UNORM_PACK32", draw)
        # (the counter's key is looked for in the 8-bit pixels, before they are encoded)
        self.assertLess(draw.index("out.runs.push_back(c);"), draw.index("if (dev.hdr) {"))
        tick = menu[menu.index("void menu_tick() {"):]
        self.assertIn("if (pixels_now != pixels_were) {", tick)
        self.assertIn("fps_bmp.w = fps_bmp.h = 0;", tick)


class Renderer(unittest.TestCase):
    def test_rows_and_ids(self):
        menu, ids = source("gpu/vk/vk_menu.cpp"), source("gpu/vk/menu_option_ids.h")
        header = source("gpu/vk/vk_menu.h")
        for field in ("int hdr = 0;", "int hdr_white = 200;", "int hdr_peak = 1000;"):
            self.assertIn(field, header)
        self.assertIn('{"HDR", "HDR", &opts.hdr, 0, 2, 1, tx_hdr,', menu)
        self.assertIn('{"HDR paper white", "HDR: branco de papel", &opts.hdr_white, 80, 400, 10, tx_nits,', menu)
        self.assertIn('{"HDR peak brightness", "HDR: brilho de pico", &opts.hdr_peak, 400, 4000, 100, tx_nits,', menu)
        self.assertRegex(menu, r"video_rows\[\] = \{[^}]*Pacing, Hdr, HdrWhite, HdrPeak,")
        restart = re.search(r"restart_rows\[\] = \{([^}]*)\}", menu).group(1)
        self.assertNotIn("Hdr", restart)   # (at once: the swapchain is made again)
        order = re.findall(r"\b(AKYNO_OPT_\w+)", re.search(r"enum \{(.*?)\};", ids, re.S).group(1))
        self.assertEqual(order[20:23], ["AKYNO_OPT_HDR_NATIVE", "AKYNO_OPT_HDR_PEAK", "AKYNO_OPT_HDR_WHITE"])   # (84 to 86; then the render distance, test_0451_render_distance.py)
        replay = source("gpu/vk/vk_replay.cpp")
        self.assertIn("case AKYNO_OPT_HDR_NATIVE: return dev.hdr && opts.hdr == 2;", replay)
        self.assertIn("case AKYNO_OPT_HDR_PEAK: return akyno_hdr_peak(opts.hdr_peak);", replay)
        self.assertIn("case AKYNO_OPT_HDR_WHITE: return akyno_hdr_white(opts.hdr_white);", replay)

    def test_surface_only_when_asked_and_listed(self):
        main = source("gpu/vk/vk_main.cpp")
        self.assertIn("ext_list.push_back(VK_EXT_SWAPCHAIN_COLOR_SPACE_EXTENSION_NAME), dev.swapchain_colorspace = true;", main)
        swap = main[main.index("bool create_swapchain("):]
        sdr, asked = swap.index("f.format == VK_FORMAT_R8G8B8A8_UNORM) fmt = f;"), swap.index("if (opts.hdr) {")
        self.assertLess(sdr, swap.index("dev.hdr = false;"))
        self.assertLess(swap.index("dev.hdr = false;"), asked)
        chosen = swap[asked:swap.index("static int told")]
        self.assertIn("f.colorSpace == VK_COLOR_SPACE_HDR10_ST2084_EXT", chosen)
        self.assertIn("fmt = f, dev.hdr = true;", chosen)

    def test_present_expands_sdr_and_leaves_native_alone(self):
        replay = source("gpu/vk/vk_replay.cpp")
        present = replay[replay.index("void present_image("):]
        present = present[:present.index("menu_record(")]
        self.assertIn("if (hdr_was >= 0 && hdr_was != opts.hdr) {", present)
        hdr, scaled = present.index("if (hdr_image) {"), present.index("} else if (scaled)")
        self.assertLess(hdr, scaled)
        self.assertIn("const bool hdr_pass = dev.hdr ? !present_native_pq.load(std::memory_order_relaxed) : hdr_preview && opts.hdr == 1;", present)
        self.assertIn("const VkImage hdr_image = hdr_pass && src && view", present)
        self.assertIn("framegen_hdr(f.cmd, framegen_scaled_view(scaled), target.width, target.height, nullptr,", present)
        self.assertIn("framegen_hdr(f.cmd, view, sw, sh, crop, target.width, target.height)", present)
        # (the flag is defined before the function that sets it)
        self.assertLess(replay.index("std::atomic<bool> present_native_pq{false};"), replay.index("void do_present("))
        self.assertIn("tex && dev.hdr && opts.hdr == 2 && tex->format == VK_FORMAT_A2B10G10R10_UNORM_PACK32", replay)
        framegen = source("gpu/vk/vk_framegen.cpp")
        made = framegen[framegen.index("VkImage framegen_hdr("):]
        self.assertIn("make_pipe(hdr.pipe, HDR_ENCODE_COMP_SPV, sizeof HDR_ENCODE_COMP_SPV, {S, I}, 32)", made)
        self.assertIn("VK_FORMAT_A2B10G10R10_UNORM_PACK32, VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT", made)
        # (the filter's output is read through a sampler by the pass)
        self.assertIn("VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT)) return VK_NULL_HANDLE;",
                      framegen)

    def test_shader_translation_sources_untouched(self):
        # (the HDR pass is a present-time shader of the renderer's own: nothing the shader cache's stamp is made of)
        from akynoleyend.build_support import shader_cache_stamp
        self.assertEqual(shader_cache_stamp(ROOT / "gpu/vk"), "4cdbb0029868040b")


class Host(unittest.TestCase):
    def test_the_game_is_told_hdr_only_at_native(self):
        vi = source("host/nn_vi.c")
        self.assertLess(vi.index("int rx_option(int id, int otherwise);"), vi.index("QueryDisplayHdrStatusEPb"))
        status = vi[vi.index("HLE(_ZN2nn2vi21QueryDisplayHdrStatusEPb"):vi.index("HLE(_ZN2nn2vi25QueryDisplayHdrPaperWhite")]
        self.assertIn("const int native = rx_option(AKYNO_OPT_HDR_NATIVE, 0);", status)
        self.assertIn("*(uint8_t *)GP(ARG(0)) = native ? 1 : 0;", status)
        self.assertIn("native ? (uint16_t)rx_option(AKYNO_OPT_HDR_PEAK, 1000) : 0;", status)
        self.assertIn("rx_option(AKYNO_OPT_HDR_NATIVE, 0) ? (uint16_t)rx_option(AKYNO_OPT_HDR_WHITE, 203) : 203;", vi)


if __name__ == "__main__":
    unittest.main()
