"""r13e: the VRAM control (gpu/vk/vram_policy.h and where the renderer uses it). From an RTX 3060 Ti session (8 GB, 16 GB of
RAM): 8003 MB used of 7090 allowed, 1.4-2.9 GB of holes in VMA's blocks, textures over their budget, 21 GB private. The policy
is compiled and run; the renderer's use of it is read from the sources. No game or GPU: none of this says the stutter is gone."""
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

POLICY = r'''
#include <cassert>
#include "vram_policy.h"
using namespace mkwvk;
int main() {
    constexpr uint64_t M = 1ull << 20, G = 1ull << 30;
    // (the session: 7090 MB allowed)
    assert(vram_level(1524 * M, 7256 * M) == VRAM_NORMAL);
    assert(vram_level(6500 * M, 7090 * M) == VRAM_PRESSED);
    assert(vram_level(6982 * M, 7082 * M) == VRAM_CRITICAL);
    assert(vram_level(8003 * M, 7090 * M) == VRAM_OVER);
    assert(vram_level(8003 * M, 0) == VRAM_NORMAL);   // (no budget known)
    // (the 8 GB class, a heap reported a little over 8 GiB too; 12 GB not)
    assert(vram_small(6 * G) && vram_small(8 * G) && vram_small(8 * G + 256 * M) && !vram_small(12 * G) && !vram_small(0));
    assert(image_block_bytes(8 * G) == 64 * M && image_block_bytes(12 * G) == 128 * M && image_block_bytes(0) == 128 * M);
    assert(astc_bc_fine_bytes(8 * G) == 2 * M && astc_bc_fine_bytes(16 * G) == 64 * M);
    // (60 presents normally, 8 from critical on; a smaller configured figure stays)
    assert(evict_min_unused(VRAM_PRESSED, 60) == 60 && evict_min_unused(VRAM_CRITICAL, 60) == 8);
    assert(evict_min_unused(VRAM_OVER, 60) == 8 && evict_min_unused(VRAM_OVER, 4) == 4);
    assert(!vram_compact_wanted(VRAM_PRESSED, 2 * G) && !vram_compact_wanted(VRAM_OVER, 200 * M));
    assert(vram_compact_wanted(VRAM_OVER, 1465 * M) && vram_compact_wanted(VRAM_CRITICAL, 925 * M));
    // (blocks: only those whose every byte may go, fewest bytes first, until the need is met)
    std::vector<BlockUse> b = {
        {40 * M, 40 * M},   // 0: may go, 40 MB in it
        {10 * M, 10 * M},   // 1: may go, 10 MB: first
        {60 * M, 59 * M},   // 2: one image that stays: never
        {0, 0},             // 3: nothing in it (VMA frees it itself)
        {30 * M, 30 * M},   // 4: may go, 30 MB
    };
    auto pick = blocks_to_empty(b, 64 * M, 100 * M);
    assert((pick == std::vector<size_t>{1, 4}));
    pick = blocks_to_empty(b, 64 * M, 1 * G);
    assert((pick == std::vector<size_t>{1, 4, 0}));
    assert(blocks_to_empty(b, 64 * M, 0).empty());
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
    def test_the_pressure_is_found_and_logged_where_the_budget_is(self):
        texture = source("gpu/vk/vk_texture.cpp")
        frame = texture[texture.index("void texture_frame(uint64_t completed) {"):]
        self.assertIn("const VramLevel level = known ? vram_level_held((VramLevel)vram_pressure_level.load(), used, allowed) : VRAM_NORMAL;", frame)
        self.assertLess(frame.index("const bool known = vram_usage(&used, &allowed, &block_free);"),
                        frame.index("const VramLevel level"))
        self.assertIn('logf("vk: VRAM pressure %s:', frame)

    def test_compaction_takes_only_what_guest_memory_makes_again(self):
        texture = source("gpu/vk/vk_texture.cpp")
        frame = texture[texture.index("void texture_frame(uint64_t completed) {"):]
        compact = frame[frame.index("static const bool no_compact"):frame.index("const bool sweep = total_bytes <= budget;")]
        for rule in ("tex->gpu_written", "tex->sparse", "tex->pool_eligible", "tex->last_value > completed",
                     "frame_no - tex->last_frame < 8"):
            self.assertIn(rule, compact)
        self.assertIn("vram_compact_wanted(level, block_free)", compact)
        self.assertIn("frame_no - compacted_at >= 60", compact)
        self.assertIn("blocks_to_empty(blocks, image_block_size(), need)", compact)
        self.assertIn("const uint64_t target = allowed / 100 * 90;", compact)
        # (gone as the eviction makes them go: after the GPU is done, out of the address map)
        self.assertIn("destroy_later(*tex);", compact)
        self.assertIn("forget_gpu(tex);", compact)
        self.assertIn('getenv("RX_VK_NO_COMPACT")', compact)

    def test_eviction_from_critical_on(self):
        texture = source("gpu/vk/vk_texture.cpp")
        self.assertIn("evict_min_unused(commit_pressure_now() ? VRAM_CRITICAL : level, min_unused);", texture)
        self.assertIn("frame_no - last < (sweep ? std::max<uint64_t>(120, min_unused) : unused_min)) break;", texture)

    def test_blocks_counted_where_images_are_made_and_destroyed(self):
        vma = source("gpu/vk/vk_vma.cpp")
        make = vma[vma.index("bool create_image("):vma.index("void destroy_image(")]
        gone = vma[vma.index("void destroy_image("):vma.index("bool create_buffer(")]
        self.assertIn("block_allocated[block] += info.size;", make)
        self.assertIn("pool_allocs.erase(it);", gone)
        self.assertLess(gone.index("pool_allocs.erase(it);"), gone.index("vmaDestroyImage("))
        self.assertIn("kImageBlock = image_block_bytes(device_heap_bytes());", vma)
        self.assertIn('getenv("RX_VK_IMAGE_BLOCK_MB")', vma)
        self.assertIn('logf("vk: image pool: %zu blocks', vma)

    def test_fine_astc_as_bc3_on_small_cards(self):
        texture = source("gpu/vk/vk_texture.cpp")
        # (r13l: with whether the GPU is integrated, test_r13k_igpu_memory.py)
        self.assertIn("astc_bc_fine_bytes(device_heap_bytes(), device_integrated())", texture)
        self.assertIn("const uint64_t min_bytes = bw * bh >= 36 ? low : fine;", texture)

    def test_no_new_mirror_over_the_drivers_budget(self):
        memory = source("gpu/vk/vk_memory.cpp")
        make = memory[memory.index("bool mirror_make(Pool& pool) {"):]
        make = make[:make.index("create_device_buffer(")]
        self.assertIn("vram_level_now() >= VRAM_OVER", make)
        # (and at 90% only with RX_VK_MIRROR_TIGHT, as before: 8 GB cards sit there)
        self.assertIn("tight_rule && vram_usage(&used, &allowed)", make)

    def test_an_installed_r13d_is_updated(self):
        from akynoleyend.coherence import compatible_previous_host
        r13d = "7f647493b97bb4a1ee7557da61b06a5e28ed50ae1220872c1b7fd4f7da2e4131"
        self.assertIn('"%s"' % r13d, source("akynoleyend/coherence.py"))
        self.assertTrue(compatible_previous_host({
            "version": "0.4.3-test.4", "source_sha256": r13d,
            "host_revision": "directory304-early-texels-regmap759-output849-v2",
            "game_build_id": "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348000000000000000000000000"}))

    def test_shader_identity_untouched(self):
        # (none of this is in the translator's identity: the shader stamp and the caches stay)
        from akynoleyend.build_support import shader_cache_stamp
        self.assertEqual(shader_cache_stamp(ROOT / "gpu/vk"), "4cdbb0029868040b")


if __name__ == "__main__":
    unittest.main()
