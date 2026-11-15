"""r11: the GTX 1650's coloured noise (a left-out network's RGB9E5 input blitted as R11G11B10F) and the latency rows taken
from Hookshot v2.1.0 (commit 8ef84611049f4fc31835a0b12793cf074ed49c3c). Read from the sources; no game or GPU here: the runs
on the RTX 5070 Ti are in docs/origem.md."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Rgb9e5Stub(unittest.TestCase):
    def setUp(self):
        self.draw = source("gpu/vk/vk_draw.cpp")
        body = self.draw[self.draw.index("bool upscale_stub(VkCommandBuffer cmd"):]
        self.stub = body[:body.index("\n}\n")]

    def test_rgb9e5_input_is_not_blitted(self):
        # (the RGB9E5 branch comes before the blit, which read the 9E5 words as 11/11/10 floats)
        at = self.stub.index("in.d.format == NVN_FORMAT_RGB9E5F && dst->format == VK_FORMAT_B10G11R11_UFLOAT_PACK32")
        self.assertLess(at, self.stub.index("vkCmdBlitImage("))
        self.assertIn("rgb9e5_upscale(cmd, in_h, out_h, dst)", self.stub)

    def test_input_sampled_through_its_own_view_and_squared(self):
        helper = self.draw[self.draw.index("bool rgb9e5_upscale("):self.draw.index("bool upscale_stub(")]
        self.assertIn("texture_view_of(in_h, VK_IMAGE_VIEW_TYPE_2D, ViewUse::Sample, VK_FORMAT_UNDEFINED", helper)
        self.assertIn("TAAU_UPSCALE_COMP_SPV", helper)     # (shaders/taau_upscale.comp: s * s)
        self.assertIn("0u};", helper)                       # (valid = 0: no history bound)
        self.assertIn("RX_VK_NO_9E5_STUB", helper)
        self.assertIn("vec3 c = s * s;", source("gpu/vk/shaders/taau_upscale.comp"))


class LatencyRows(unittest.TestCase):
    def test_modules_copied_from_hookshot(self):
        for name in ("vk_reflex.h", "vk_reflex.cpp", "vk_antilag.h", "vk_antilag.cpp"):
            self.assertTrue((ROOT / "gpu/vk" / name).is_file(), name)
        self.assertIn("VK_NV_LOW_LATENCY_2_EXTENSION_NAME", source("gpu/vk/vk_reflex.cpp"))
        self.assertIn("VK_AMD_ANTI_LAG_EXTENSION_NAME", source("gpu/vk/vk_antilag.cpp"))

    def test_device_and_swapchain_wiring(self):
        main = source("gpu/vk/vk_main.cpp")
        for call in ("reflex_device_extensions(want, exts);", "antilag_device_extensions(want, exts);",
                     "reflex_device_features(tail);", "antilag_device_features(tail);", "reflex_device_created();",
                     "antilag_device_created();", "reflex_swapchain_info(ci);", "reflex_swapchain_destroyed();",
                     "reflex_swapchain_created(sc);"):
            self.assertIn(call, main)
        # (features chained before they are queried; the old swapchain released before it is destroyed)
        self.assertLess(main.index("reflex_device_features(tail);"), main.index("vkGetPhysicalDeviceFeatures2(dev.physical, &f);"))
        self.assertLess(main.index("reflex_swapchain_destroyed();"), main.index("vkDestroySwapchainKHR(dev.device, dev.swapchain"))

    def test_present_wiring(self):
        replay = source("gpu/vk/vk_replay.cpp")
        present = replay[replay.index("void present_image("):]
        present = present[:present.index("\n}\n")]
        order = [present.index(x) for x in ("reflex_submit_ends();", "reflex_present_id(nullptr);", "antilag_present();",
                                            "vkQueuePresentKHR(dev.queue, &pi);", "reflex_presented();")]
        self.assertEqual(order, sorted(order))
        self.assertIn("reflex_swapchain_stale()", present)
        do_present = replay[replay.index("void do_present("):]
        self.assertIn("reflex_present_begins();", do_present[:600])
        self.assertIn("reflex_sleep(); antilag_input();", do_present[:600])

    def test_rows_and_defaults(self):
        menu = source("gpu/vk/vk_menu.cpp")
        names = re.findall(r'^    \{"([A-Za-z0-9 -]+)", "[^"]+", &opts\.', menu, re.M)
        self.assertIn("NVIDIA Reflex", names)
        self.assertIn("AMD Anti-Lag 2", names)
        video = re.search(r"constexpr Setting video_rows\[\] = \{([^}]+)\}", menu).group(1)
        self.assertIn("Reflex", video)
        self.assertIn("AntiLag", video)
        self.assertIn("Indisponível nesta placa", menu)
        header = source("gpu/vk/vk_menu.h")
        self.assertIn("int reflex = 0;", header)
        self.assertIn("int antilag = 0;", header)
        self.assertNotIn("reflex", source("gpu/vk/vk_api.h"))   # (the renderer's interface and the shader stamp unchanged)


if __name__ == "__main__":
    unittest.main()
