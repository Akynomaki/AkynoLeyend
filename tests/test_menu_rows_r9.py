"""r9: the F1 panel's rows taken from Hookshot v2.1.0's menu. The rows' arithmetic runs natively; the wiring is read from
the sources. No game or GPU: none of this says the rows were tried in the game."""
import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class RowArithmetic(unittest.TestCase):
    def test_native(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from tests.native_tools import native_cxx
        cxx = native_cxx()
        if not cxx:
            self.skipTest("no native C++ compiler")
        with tempfile.TemporaryDirectory(prefix="menu-rows-") as tmp:
            exe = Path(tmp) / "menu-rows.exe"
            subprocess.run([cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", str(ROOT / "tests/native/menu_rows_r9.cpp"),
                            "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


class Wiring(unittest.TestCase):
    def test_every_row_is_saved_under_the_key_its_reader_uses(self):
        menu = source("gpu/vk/vk_menu.cpp")
        names = re.findall(r'^    \{"([A-Za-z ]+)", "[^"]+", &opts\.', menu, re.M)
        keys = {name.lower().replace(" ", "_") for name in names}
        for key in ("quality_preset", "gpu_device", "frame_rate_cap", "anisotropic_filtering", "robust_buffers", "volume",
                    "mute_in_background", "menu_size", "controller_in_background", "invert_mouse_vertical",
                    "invert_camera_x", "invert_camera_y", "stick_dead_zone", "rumble_strength"):
            self.assertIn(key, keys)
            self.assertLess(len(key), 32)   # (ini_key's buffer)
        # (the rows read before the panel loads the file, by the same keys)
        self.assertIn('boot_option("gpu_device", 0)', source("gpu/vk/vk_main.cpp"))
        self.assertIn('boot_option("robust_buffers", 0)', source("gpu/vk/vk_main.cpp"))
        self.assertIn('boot_option("anisotropic_filtering", 0)', source("gpu/vk/vk_draw.cpp"))
        self.assertIn('boot_option("quality_preset", 0)', source("gpu/vk/vk_texture.cpp"))
        self.assertIn('boot_option("quality_preset", 0)', source("gpu/vk/vk_memory.cpp"))
        self.assertIn('hos_ini_option("frame_rate_cap", 0)', source("host/nn_vi.c"))

    def test_rows_and_their_enum_stay_in_step(self):
        menu = source("gpu/vk/vk_menu.cpp")
        self.assertIn("static_assert(std::size(rows) == SettingCount);", menu)
        enum = re.search(r"enum Setting \{([^}]+)\}", menu).group(1)
        order = [name.strip() for name in enum.split(",") if name.strip()]
        self.assertEqual(order[:10], ["Fullscreen", "Framegen", "Pacing", "Resolution", "Output", "Sharpness", "Speed",
                                      "Handheld", "Ultrawide", "Fps"])   # (the r8 rows keep their places)
        self.assertEqual(order[-1], "SettingCount")
        for page in ("video_rows", "audio_rows", "game_rows", "pad_rows", "restart_rows"):
            listed = re.search(r"constexpr Setting %s\[\] = \{([^}]+)\}" % page, menu).group(1)
            for name in listed.split(","):
                self.assertIn(name.strip(), order)

    def test_defaults_leave_the_game_as_it_was(self):
        header = source("gpu/vk/vk_menu.h")
        for line in ("int preset = 0;", "int gpu_device = 0;", "int fps_cap = 0;", "int anisotropy = 0;", "int robust = 0;",
                     "int volume = 100;", "int mute_background = 0;", "int menu_size = 2;", "int pad_background = 0;",
                     "int mouse_invert = 0;", "int stick_dead_zone = 0;", "int rumble = 100;"):
            self.assertIn(line, header)

    def test_the_host_asks_by_ids_clear_of_the_jitter(self):
        ids = source("gpu/vk/menu_option_ids.h")
        self.assertIn("AKYNO_OPT_PAD_BACKGROUND = 64", ids)
        replay = source("gpu/vk/vk_replay.cpp")
        for name in ("PAD_BACKGROUND", "MOUSE_INVERT", "RUMBLE", "STICK_DEAD_ZONE", "INVERT_CAM_X", "INVERT_CAM_Y", "VOLUME",
                     "MUTE_BACKGROUND"):
            self.assertIn("case AKYNO_OPT_%s: return opts." % name, replay)
        self.assertIn("rx_option(AKYNO_OPT_VOLUME, 100)", source("host/nn_audio.c"))
        self.assertIn("rx_option(AKYNO_OPT_STICK_DEAD_ZONE, 0)", source("host/nn_hid.c"))
        self.assertIn("rx_option(AKYNO_OPT_RUMBLE, 100)", source("host/pad_sdl.c"))
        # (the renderer's interface is the shader stamp's: these rows do not touch it)
        self.assertNotIn("AKYNO_OPT_", source("gpu/vk/vk_api.h"))
        self.assertIn("#define MKWVK_API_VERSION 2", source("gpu/vk/vk_api.h"))

    def test_the_cap_waits_for_the_step_hook(self):
        vi = source("host/nn_vi.c")
        gate = vi[vi.index("static int fps_max(void) {"):]
        gate = gate[:gate.index("\n}\n")]
        self.assertIn("if (asked <= 60) return 60;", gate)
        self.assertIn("if (!hos_step_probe) return 60;", gate)
        self.assertIn("1000000000LL / fps_max() * present_interval", vi)
        self.assertIn("period = 1000000000LL / fps_max();", vi)
        self.assertNotIn("1000000000LL / 60 * present_interval", vi)


class StepHook(unittest.TestCase):
    """nx2/oot_patches.py: both divides take the frame's time, or neither does."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location("oot_patches_r9", ROOT / "nx2/oot_patches.py")
        self.patches = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.patches)

    def lifted(self, register, name):
        return ('#include "a64.h"\nvoid %s(Ctx *__restrict A64_NOESC c) {\n    uint64_t _a=1,_b=2,_v;\n'
                "    _v=a64_fpx_div32_div32(c,_a,_b);\n    a64_vset64(c->vreg[%d],_v);}\n}\n\nvoid f_0(Ctx *c) {\n}\n" % (name, register))

    def test_both_sites_are_hooked_once_and_undone_whole(self):
        p = self.patches
        first, second = self.lifted(8, "f_80706be0"), self.lifted(0, "f_83b6ea90")
        a, done_a = p.patch_frame_seconds(first)
        b, done_b = p.patch_frame_seconds(second)
        self.assertEqual((done_a, done_b), (1, 1))
        self.assertIn("hos_step_probe = c->x[19];", a)
        self.assertNotIn("hos_step_probe = c->x[19];", b)
        for text in (a, b):
            self.assertEqual(text.count(p.STEP_MARK), 1)
            self.assertIn(p.STEP_DECL, text)
            self.assertEqual(p.patch_frame_seconds(text), (text, 0))   # (a second run changes nothing)
        self.assertEqual(p.unpatch_frame_seconds(a), first)
        self.assertEqual(p.unpatch_frame_seconds(b), second)

    def test_other_code_is_left_alone(self):
        p = self.patches
        other = self.lifted(3, "f_80706be0")                       # (another register: another game version)
        self.assertEqual(p.patch_frame_seconds(other), (other, 0))
        elsewhere = self.lifted(8, "f_11111111")
        self.assertEqual(p.patch_frame_seconds(elsewhere), (elsewhere, 0))


if __name__ == "__main__":
    unittest.main()
