"""Exercise the renderer's retirement loop with completed and in-flight images."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.native_tools import native_cxx


ROOT = Path(__file__).resolve().parents[1]
GPU = ROOT / "gpu" / "vk"


class TextureRetirement(unittest.TestCase):
    def test_bounded_queue_preserves_gpu_lifetimes_and_pool_reuse(self):
        compiler = native_cxx()
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        renderer = (GPU / "vk_texture.cpp").read_text(encoding="utf-8")
        start = renderer.index("void reap_textures(uint64_t completed) {")
        end = renderer.index("void texture_frame(uint64_t completed)", start)
        tested_loop = renderer[start:end]
        fixture = r'''
#include "vram_policy.h"
#include <cassert>
#include <deque>
#include <map>
#include <vector>

using namespace mkwvk;
using VkDeviceMemory = uint64_t;
struct Dead {
    uint64_t value, image, allocation, bytes;
    bool pool_eligible;
    std::map<int, uint64_t> view_map;
    std::vector<VkDeviceMemory> memory;
};
struct { int device; } dev;
std::deque<Dead> dead;
uint64_t dead_bytes = 0;
VramLevel level = VRAM_NORMAL;
bool commit = false;
std::vector<uint64_t> freed, views, sparse, pooled;
VramLevel vram_level_now() { return level; }
bool commit_pressure_now() { return commit; }
bool target_put(Dead& entry) {
    assert(entry.pool_eligible);
    pooled.push_back(entry.image);
    entry.view_map.clear();
    return true;
}
void vkDestroyImageView(int, uint64_t view, void*) { views.push_back(view); }
void destroy_image(uint64_t image, uint64_t allocation) {
    assert(allocation == image);
    freed.push_back(image);
}
void vkFreeMemory(int, VkDeviceMemory memory, void*) { sparse.push_back(memory); }

void enqueue(uint64_t image, uint64_t value, uint64_t bytes, bool eligible = false) {
    dead.push_back({value, image, image, bytes, eligible, {{0, image * 2}, {1, 0}}, {}});
    dead_bytes += bytes;
}
''' + tested_loop + r'''
int main() {
    constexpr uint64_t mib = 1ull << 20;
    enqueue(1000, 42, mib);
    for (uint64_t i = 1; i <= 40; ++i) enqueue(i, 4, mib);
    enqueue(1001, 4, mib, true);
    dead[24].memory = {7};
    reap_textures(4);
    assert(freed.size() == 24 && freed.front() == 1 && freed.back() == 24);
    assert(views.size() == 24 && views.back() == 48);
    assert(sparse == std::vector<VkDeviceMemory>{7});
    assert(pooled == std::vector<uint64_t>{1001});
    assert(dead.size() == 17 && dead.front().image == 1000 && dead[1].image == 25);
    assert(dead_bytes == 17 * mib);
    reap_textures(41);
    assert(freed.size() == 40 && dead.front().image == 1000 && dead_bytes == mib);
    reap_textures(42);
    assert(freed.back() == 1000 && dead.empty() && !dead_bytes);

    for (uint64_t i = 1; i <= 80; ++i) enqueue(i, 5, 4 * mib);
    reap_textures(5);
    assert(dead.size() == 32 && dead_bytes == 128 * mib);
    commit = true;
    enqueue(1000, 7, mib);
    reap_textures(6);
    assert(dead.size() == 1 && dead.front().image == 1000 && dead_bytes == mib);
    commit = false;
    level = VRAM_CRITICAL;
    for (uint64_t i = 1; i <= 50; ++i) enqueue(i, 7, mib);
    reap_textures(7);
    assert(dead.empty() && !dead_bytes);

    level = VRAM_NORMAL;
    for (uint64_t i = 1; i <= 240; ++i) enqueue(i, 7, 1024);
    reap_textures(7);
    assert(dead.size() == 192 && dead.front().image == 49);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "retirement.cpp"
            binary = folder / ("retirement.exe" if os.name == "nt" else "retirement")
            source.write_text(fixture, encoding="utf-8")
            flags = ["-std=c++20", "-Wall", "-Wextra", "-Werror"]
            if os.name == "nt":
                flags.append("-static")
            built = subprocess.run([compiler, *flags, "-I", str(GPU), str(source), "-o", str(binary)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
