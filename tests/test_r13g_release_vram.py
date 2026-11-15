"""r13g: a finalize marks only the image of the texture object it finalizes, not a newer object's at the same storage (the
game initializes the next before it finalizes the previous: 37-72 uploads a session over images just drawn, flickering
targets and shadow map on the RTX 3060 Ti, 12/11/2026); the VRAM pressure level held with a margin; every ASTC but the
smallest kept as BC3 on cards of 8 GB. Policy compiled and run, the rest from the sources; no game or GPU."""
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

HELD = r'''
#include <cassert>
#include "vram_policy.h"
using namespace mkwvk;
int main() {
    constexpr uint64_t M = 1ull << 20;
    const uint64_t allowed = 7121 * M;
    // (up at once)
    assert(vram_level_held(VRAM_NORMAL, 7122 * M, allowed) == VRAM_OVER);
    assert(vram_level_held(VRAM_PRESSED, 7000 * M, allowed) == VRAM_CRITICAL);
    // (the session's flapping: 7122 of 7121-7146 allowed, over and critical by turns, is held over)
    assert(vram_level_held(VRAM_OVER, 7122 * M, 7146 * M) == VRAM_OVER);
    assert(vram_level_held(VRAM_OVER, 7106 * M, 7137 * M) == VRAM_OVER);
    // (down 2% under the line: 98%, 95%, 88%)
    assert(vram_level_held(VRAM_OVER, allowed / 100 * 98, allowed) == VRAM_CRITICAL);
    assert(vram_level_held(VRAM_CRITICAL, allowed / 100 * 96, allowed) == VRAM_CRITICAL);
    assert(vram_level_held(VRAM_CRITICAL, allowed / 100 * 95, allowed) == VRAM_PRESSED);
    assert(vram_level_held(VRAM_PRESSED, allowed / 100 * 89, allowed) == VRAM_PRESSED);
    assert(vram_level_held(VRAM_PRESSED, allowed / 100 * 88, allowed) == VRAM_NORMAL);
    assert(vram_level_held(VRAM_OVER, 1000 * M, 0) == VRAM_NORMAL);   // (no budget known)
    // (every ASTC but the smallest as BC3 on 8 GB cards, the coarser blocks' own 2 MB line)
    assert(astc_bc_fine_bytes(8ull << 30) == 2 * M && astc_bc_fine_bytes(16ull << 30) == 64 * M);
    return 0;
}
'''


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Held(unittest.TestCase):
    def test_policy_compiled_and_run(self):
        compiler = native_cxx()
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "check.cpp").write_text(HELD, encoding="utf-8")
            binary = path / ("check.exe" if os.name == "nt" else "check")
            flags = ["-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-I" + str(ROOT / "gpu/vk")]
            if os.name == "nt":
                flags.append("-static")
            built = subprocess.run([compiler, *flags, str(path / "check.cpp"), "-o", str(binary)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_the_held_level_is_the_one_used(self):
        texture = source("gpu/vk/vk_texture.cpp")
        self.assertIn("vram_level_held((VramLevel)vram_pressure_level.load(), used, allowed)", texture)


class ReleaseBySerial(unittest.TestCase):
    def test_initializations_are_noted_as_they_come(self):
        replay = source("gpu/vk/vk_replay.cpp")
        made = replay[replay.index("void texture_created_of(const nvn_tex* t) {"):]
        made = made[:made.index("\n}\n")]
        self.assertIn("texture_initialized(t);", made)
        texture = source("gpu/vk/vk_texture.cpp")
        init = texture[texture.index("void texture_initialized(const nvn_tex* t) {"):]
        init = init[:init.index("\n}\n")]
        self.assertIn("std::lock_guard lk(newest_mu);", init)
        self.assertIn("if (t->serial > e.first) e = {t->serial, t->d};", init)   # (the newest only)

    def test_a_finalize_leaves_a_newer_objects_image(self):
        texture = source("gpu/vk/vk_texture.cpp")
        rel = texture[texture.index("void texture_released(const nvn_tex* t) {"):]
        rel = rel[:rel.index("\n}\n")]
        self.assertIn("if (n->second.first > t->serial) newer = true, newer_d = n->second.second;", rel)
        self.assertIn("else newest_init.erase(n);", rel)
        self.assertIn("if (newer && same_shape(it->second->d, newer_d))", rel)
        self.assertLess(rel.index("same_shape(it->second->d, newer_d)"), rel.index("it->second->released = true"))
        self.assertIn('getenv("RX_VK_RELEASE_BY_ADDRESS")', rel)
        # (the registrations were finalized by serial already: vk_bank.cpp, unchanged)
        self.assertIn("auto it = regs_by_serial.find(serial);", source("gpu/vk/vk_bank.cpp"))

    def test_serials_only_grow(self):
        host = source("host/nvn_native.c")
        self.assertIn("static uint64_t new_serial(void) { return (uint64_t)InterlockedIncrement64(&serials); }", host)


if __name__ == "__main__":
    unittest.main()
