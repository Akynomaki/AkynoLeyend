"""r13k: an integrated GPU's video memory is the PC's RAM. From an Intel Graphics session (Core Ultra 9 275HX, 32 GB, 12/11/2026):
a heap of 17.6 GB taken as a large card (fine ASTC decoded as RGBA8, 1944 MB of it; 128 MB image blocks, 971 MB of holes), the
process at 25.8 GB private with 9 GB free at the start (another emulator held 26 GB), the system paging. The rule is compiled and
run, its use read from the sources, the launcher's notice called. No game or GPU: none of this says the stutter is gone."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from native_tools import native_cxx  # noqa: E402
from akynoleyend import hardware  # noqa: E402

GIB = 1 << 30

POLICY = r'''
#include <cassert>
#include "vram_policy.h"
using namespace mkwvk;
int main() {
    constexpr uint64_t M = 1ull << 20, G = 1ull << 30;
    // (the Intel session: a 17579 MB heap, integrated: the small class; a card: as it is)
    assert(vram_class_bytes(17579 * M, true) == 4 * G);
    assert(vram_class_bytes(2 * G, true) == 2 * G);
    assert(vram_class_bytes(17579 * M, false) == 17579 * M);
    assert(vram_class_bytes(17579 * M, true, true) == 17579 * M);   // (RX_VK_IGPU_AS_LARGE)
    assert(vram_small(vram_class_bytes(17579 * M, true)) && !vram_small(vram_class_bytes(16 * G, false)));
    // (r13l: fine ASTC on an integrated GPU stays RGBA8 below 64 MB; a small card keeps its 2 MB)
    assert(astc_bc_fine_bytes(vram_class_bytes(17579 * M, true), true) == 64 * M);
    assert(astc_bc_fine_bytes(vram_class_bytes(2 * G, true), true) == 64 * M);
    assert(astc_bc_fine_bytes(8 * G, false) == 2 * M && astc_bc_fine_bytes(8 * G) == 2 * M);
    assert(image_block_bytes(vram_class_bytes(17579 * M, true)) == 64 * M);
    // (an NVIDIA or AMD card keeps its figures: 12 GB and 16 GB large)
    assert(astc_bc_fine_bytes(vram_class_bytes(12 * G, false)) == 64 * M);
    assert(image_block_bytes(vram_class_bytes(16 * G, false)) == 128 * M);
    return 0;
}
'''


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Policy(unittest.TestCase):
    def test_policy_compiled_and_run(self):
        compiler = native_cxx()
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "check.cpp").write_text(POLICY, encoding="utf-8")
            binary = path / ("check.exe" if os.name == "nt" else "check")
            flags = ["-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-I" + str(ROOT / "gpu/vk")]
            if os.name == "nt":
                flags.append("-static")
            built = subprocess.run([compiler, *flags, str(path / "check.cpp"), "-o", str(binary)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


class Renderer(unittest.TestCase):
    def test_the_heap_seen_is_the_class(self):
        vma = source("gpu/vk/vk_vma.cpp")
        body = vma[vma.index("uint64_t device_heap_bytes() {"):vma.index("uint64_t image_block_size()")]
        self.assertIn("dev.props.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU", body)
        self.assertIn("vram_class_bytes(vram, integrated, as_large)", body)
        self.assertIn('getenv("RX_VK_IGPU_AS_LARGE")', body)
        self.assertIn("return seen;", body)
        # (its two users: the image blocks and the fine ASTC line)
        self.assertIn("image_block_bytes(device_heap_bytes())", vma)
        self.assertIn("astc_bc_fine_bytes(device_heap_bytes(), device_integrated())", source("gpu/vk/vk_texture.cpp"))
        self.assertIn("return dev.props.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU;", vma)

    def test_not_in_the_shader_fingerprint(self):
        # (the shader cache's stamp is kept: none of these files is hashed into it)
        from akynoleyend.build_support import shader_source_identity
        import inspect
        text = inspect.getsource(shader_source_identity)
        for name in ("vk_vma.cpp", "vram_policy.h", "vk_texture.cpp"):
            self.assertNotIn(name, text)


class Launcher(unittest.TestCase):
    machine = {"cpu": "test", "logical_cpus": 24, "ram_total": 32 * GIB, "ram_available": 9 * GIB,
               "commit_available": 22 * GIB, "system": "Windows"}

    def test_short_of_ram_names_the_programs(self):
        line = hardware.play_ram_notice(self.machine, [("hookshot.exe", 26 * GIB)])
        self.assertIn("9.0 GB de RAM livres de 32 GB", line)
        self.assertIn("hookshot.exe (26.0 GB)", line)
        self.assertIn("integrada", line)

    def test_enough_ram_says_nothing(self):
        self.assertEqual(hardware.play_ram_notice(dict(self.machine, ram_available=12 * GIB), [("x.exe", 3 * GIB)]), "")
        self.assertEqual(hardware.play_ram_notice(dict(self.machine, ram_total=0), []), "")

    def test_without_programs_found_still_warns(self):
        line = hardware.play_ram_notice(self.machine, [])
        self.assertTrue(line.startswith("Aviso:"))
        self.assertNotIn("Programas", line)

    def test_process_list_is_safe(self):
        found = hardware.heavy_processes(min_bytes=1 << 62)
        self.assertEqual(found, [])
        with patch("akynoleyend.hardware.os.name", "posix"):
            self.assertEqual(hardware.heavy_processes(), [])

    def test_wired_into_launch_after_the_preparation_notice(self):
        launch = source("akynoleyend/launch.py")
        self.assertLess(launch.index("notice = low_ram_notice(machine, preparing=preparing)"),
                        launch.index("notice = play_ram_notice(machine, heavy)"))
        self.assertIn('elif cache_mode != "preparacao" and machine.get("ram_total") and machine["ram_available"] < PLAY_RAM_FREE:',
                      launch)
        self.assertIn('metadata["heavy_processes"]', launch)


if __name__ == "__main__":
    unittest.main()
