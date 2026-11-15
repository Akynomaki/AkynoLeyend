/* How full VRAM really is, for the rules that give memory back near the driver's limit (vk_memory.cpp's write-back shadows).
   No Vulkan here. tests/test_vram_pressure.py */
#pragma once

#include <algorithm>
#include <cstdint>

namespace mkwvk::vram_pressure {

/// What the process really holds: the driver's count less the free space inside VMA's blocks. A destroyed image's or
/// buffer's memory stays in its block, and the driver counts the block whole until VMA frees it
inline uint64_t allocated(uint64_t used, uint64_t block_free) {
    return used - std::min(used, block_free);
}

/// Drop shadows past 95% actual use or 102% of the driver budget. Each 2 MiB shadow can share a block with
/// other allocations, so freeing a shadow can leave the driver's count unchanged.
inline bool shadows_go(uint64_t used, uint64_t allowed, uint64_t block_free) {
    if (!allowed) return false;
    return allocated(used, block_free) > allowed / 100 * 95 || used > allowed + allowed / 100 * 2;
}

/// Permit allocator growth below the pressure lines of 90% actual and 97% reported use.
inline bool shadow_fits(uint64_t n, uint64_t used, uint64_t allowed, uint64_t block_free) {
    if (!allowed) return true;
    return allocated(used, block_free) + n <= allowed / 100 * 90 && used + n <= allowed / 100 * 97;
}

/// Only reuse compatible existing memory. The allocator must forbid new Vulkan memory blocks on this path.
inline bool shadow_reuse_fits(uint64_t n, uint64_t used, uint64_t allowed, uint64_t block_free) {
    return allowed && n <= block_free && used <= allowed + allowed / 100 * 2 &&
           allocated(used, block_free) + n <= allowed / 100 * 90;
}

} // namespace mkwvk::vram_pressure
