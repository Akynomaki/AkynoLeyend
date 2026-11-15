"""r12: Hookshot v2.1.0's SDL host (controllers, motion, the microphone's input streams) in the base, adapted only to the
F1 panel's option numbers; the import stubs made again by the lift's own generator when host/ gains HLE functions. From
the sources: no game, controller or microphone here."""
import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT.parent / "hookshot" / "Hookshot-v2.1.0"


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class CopiedAsTheyAre(unittest.TestCase):
    def test_modules_match_hookshot_210(self):
        if not HOOK.is_dir():
            self.skipTest("the Hookshot v2.1.0 reference is not beside this tree")
        for name in ("hos_sdl.c", "hos_sdl.h", "hos_motion.h", "hd_rumble.h"):
            self.assertEqual((ROOT / "host" / name).read_bytes(), (HOOK / "host" / name).read_bytes(), name)
        ours = (ROOT / "host/nn_audio_in.c").read_text(encoding="utf-8")
        theirs = (HOOK / "host/nn_audio_in.c").read_text(encoding="utf-8")
        self.assertTrue(ours.replace('#include "../gpu/vk/menu_option_ids.h"   /* (AkynoLeyend r12: AKYNO_OPT_MIC, '
                                     'hos_mic_follow_panel at the end) */\n', "").startswith(theirs))

    def test_pad_sdl_only_adapted(self):
        pad = source("host/pad_sdl.c")
        self.assertNotIn("rx_option(HOS_OPT_", pad)   # (Hookshot's comments still name its options)
        for name in ("GYRO", "GYRO_DEADZONE", "GYRO_SENS_X", "GYRO_SENS_Y", "GYRO_INV_X", "GYRO_INV_Y", "RUMBLE",
                     "INVERT_CAM_X", "INVERT_CAM_Y", "STICK_DEAD_ZONE"):
            self.assertIn("AKYNO_OPT_%s" % name, pad)
        self.assertNotIn("rx_option(9,", pad)
        self.assertNotIn("rx_option(16,", pad)
        self.assertIn("akyno_stick_axis(v, zone)", pad)
        self.assertNotIn("AKYNO_OPT_", source("gpu/vk/vk_api.h"))   # (the renderer's interface as it was)


class Motion(unittest.TestCase):
    def test_six_axis_states_come_from_the_pad(self):
        hid = source("host/nn_hid.c")
        self.assertIn('#include "hos_motion.h"', hid)
        self.assertIn("hos_sdl_motion_history(h, count)", hid)
        self.assertIn("RET(asked < 3 ? 3 : asked);", hid)   # (OoT runs its motion path only with three handles)
        self.assertIn("hos_sdl_rumble_hd(dev, v);", hid)    # (HD rumble pads get the game's value)

    def test_rows_and_ids(self):
        ids = source("gpu/vk/menu_option_ids.h")
        order = re.findall(r"AKYNO_OPT_(\w+)", ids[ids.index("enum {"):ids.index("};")])
        self.assertEqual(order[:8], ["PAD_BACKGROUND", "MOUSE_INVERT", "RUMBLE", "STICK_DEAD_ZONE", "INVERT_CAM_X",
                                     "INVERT_CAM_Y", "VOLUME", "MUTE_BACKGROUND"])   # (the r9 numbers kept)
        # (r13 appends its own after MIC: tests/test_r13_text_mouse.py, test_r13_hdr.py)
        self.assertEqual(order[8:16], ["MOUSE_SENS", "GYRO", "GYRO_SENS_X", "GYRO_SENS_Y", "GYRO_INV_X", "GYRO_INV_Y",
                                       "GYRO_DEADZONE", "MIC"])
        replay = source("gpu/vk/vk_replay.cpp")
        for name in order:
            self.assertIn("case AKYNO_OPT_%s:" % name, replay)
        menu = source("gpu/vk/vk_menu.cpp")
        pad = re.search(r"constexpr Setting pad_rows\[\] = \{([^}]+)\}", menu).group(1)
        for row in ("Gyro", "GyroSensX", "GyroSensY", "GyroInvX", "GyroInvY", "GyroDeadZone"):
            self.assertIn(row, pad)
        self.assertIn("Mic", re.search(r"constexpr Setting audio_rows\[\] = \{([^}]+)\}", menu).group(1))
        header = source("gpu/vk/vk_menu.h")
        for line in ("int gyro = 1;", "int gyro_sens_x = 100, gyro_sens_y = 100;", "int gyro_deadzone = 1;", "int mic = 1;"):
            self.assertIn(line, header)


class Microphone(unittest.TestCase):
    def test_panel_row_reaches_the_streams(self):
        follow = source("host/nn_audio_in.c")
        self.assertIn("rx_option(AKYNO_OPT_MIC, 1)", follow)
        self.assertIn("hos_mic_select(want, \"\", -1);", follow)
        self.assertIn("hos_mic_follow_panel();", source("host/nn_audio.c"))
        self.assertIn("static inline void *hos_guest_range(uint64_t a, uint64_t n)", source("host/hos.h"))


class StubsMadeAgain(unittest.TestCase):
    def test_generator_split_and_update_path(self):
        standalone = source("nx2/standalone.py")
        self.assertIn("def stubs_text(meta, host=HOST):", standalone)
        self.assertIn("text, count = stubs_text(meta)", standalone)
        upgrade = source("nx2/upgrade_output.py")
        self.assertIn("edits, _ = stub_edits(work, edits)", upgrade)
        self.assertIn('work / "sa/image/image.json"', upgrade)
        # (r13: or the panel hooks' stamp missing, on the next line)
        self.assertIn("(not (gen / STEP_STAMP).is_file() or host_implements_stubbed(work)\n", source("akynoleyend/maintenance.py"))

    def test_stale_check_sees_a_host_definition(self):
        import sys
        import tempfile
        sys.path.insert(0, str(ROOT))
        from akynoleyend.maintenance import host_implements_stubbed
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "sa/gen").mkdir(parents=True)
            stubs = work / "sa/gen/a64_stubs.c"
            stubs.write_text("void imp__ZN2nn5audio15ReadInputStreamEPNS0_15InputStreamTypeEPvi(Ctx *A64_NOESC c) { }\n")
            self.assertTrue(host_implements_stubbed(work))   # (host/nn_audio_in.c defines it now)
            stubs.write_text("void imp__ZN2nn3foo3barEv(Ctx *A64_NOESC c) { }\n")
            self.assertFalse(host_implements_stubbed(work))
            stubs.unlink()
            self.assertFalse(host_implements_stubbed(work))


class SdlShipped(unittest.TestCase):
    def test_dlls_beside_the_game(self):
        for name in ("SDL2.dll", "SDL3.dll"):
            dll = ROOT / "third_party/sdl2" / name
            self.assertTrue(dll.is_file(), name)
            self.assertEqual(dll.read_bytes()[:2], b"MZ")
        version = source("third_party/sdl2/VERSION.txt")
        self.assertIn("sdl2-compat 2.32.74", version)
        self.assertIn("SDL 3.4.20", version)
        self.assertIn('for sdl_name in ("SDL2.dll", "SDL3.dll"):', source("nx2/build.py"))
        self.assertIn('"SDL2.dll", "SDL3.dll"', source("akynoleyend/build.py"))
        self.assertIn('"SDL3.dll"', source("akynoleyend/maintenance.py"))


if __name__ == "__main__":
    unittest.main()
