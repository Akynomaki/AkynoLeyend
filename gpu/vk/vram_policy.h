// (AkynoLeyend r13e) VRAM pressure: what the renderer does as the process nears what the driver allows it
// (VK_EXT_memory_budget). Measured on an RTX 3060 Ti (8 GB, 16 GB of RAM, 12/11/2026): 8003 MB used of 7090 allowed, 1.4 to
// 2.9 GB of it free inside VMA's blocks, textures at 2.8-3.3 GB against a budget of 0.8-1.6 GB. The driver moved the excess to
// system memory and charged the process's commit for it (21 GB private on a 16 GB PC): submissions and uploads of 0.5-4 s.
// Evicting textures only made holes in the blocks, which the driver still counted. No game data.
#pragma once
#include <algorithm>
#include <cstdint>
#include <vector>

namespace mkwvk {

enum VramLevel { VRAM_NORMAL, VRAM_PRESSED, VRAM_CRITICAL, VRAM_OVER };

/// The pressure from the driver's own count: 90% pressed, 97% critical (where the budget already shrank by the excess),
/// past what it allows over (it pages the process's VRAM out). Unknown: normal.
inline VramLevel vram_level(uint64_t used, uint64_t allowed) {
    if (!allowed) return VRAM_NORMAL;
    if (used > allowed) return VRAM_OVER;
    if (used > allowed / 100 * 97) return VRAM_CRITICAL;
    if (used > allowed / 100 * 90) return VRAM_PRESSED;
    return VRAM_NORMAL;
}

/// (AkynoLeyend r13g) The level held: up at once, down only 2% under the line of the level held (98%, 95%, 88%). Without it
/// the level went between critical and over every few frames at 7.1 GB, dozens of lines of log a minute.
inline VramLevel vram_level_held(VramLevel held, uint64_t used, uint64_t allowed) {
    const VramLevel now = vram_level(used, allowed);
    if (now >= held || !allowed) return now;
    const uint64_t line = held == VRAM_OVER ? allowed / 100 * 98 : held == VRAM_CRITICAL ? allowed / 100 * 95 : allowed / 100 * 88;
    return used > line ? held : now;
}

/// The 8 GB class and below (6 GB laptops, 8 GB desktop cards), with room for a heap reported a little over 8 GiB.
inline bool vram_small(uint64_t vram) {
    return vram && vram <= (8ull << 30) + (512ull << 20);
}

/// (AkynoLeyend r13k) The VRAM the rules above see: the largest device-local heap, and on an integrated GPU at most 4 GiB, the small
/// class. An integrated GPU's "VRAM" is the PC's RAM: Intel Graphics (Core Ultra 9 275HX, 32 GB) reported a heap of 17.6 GB, so it
/// was taken as a large card: fine ASTC decoded as RGBA8 (1944 MB of decoded ASTC in Kokiri, four times BC3), 128 MB image blocks
/// (971 MB of holes in 4736), and the process at 25.8 GB private with 9 GB of RAM free at the start: the system paged, uploads of
/// 224 KB took 431 ms, submits up to 2 s. Shared memory has the bandwidth of the RAM, which BC3 also spares.
/// RX_VK_IGPU_AS_LARGE=1: the heap as it is, as before.
inline uint64_t vram_class_bytes(uint64_t heap, bool integrated, bool as_large = false) {
    return integrated && !as_large ? std::min<uint64_t>(heap, 4ull << 30) : heap;
}

/// The image pool's block size: 64 MB on small cards (a block stays the driver's while one image is left in it, and 128 MB
/// blocks held 1.4-2.9 GB of holes on the 3060 Ti), 128 MB above.
inline uint64_t image_block_bytes(uint64_t vram) {
    return (vram_small(vram) ? 64ull : 128ull) << 20;
}

/// The size (as RGBA8) from which ASTC of fine blocks (4 x 4, 5 x 5: UI, characters) is kept as BC3: 64 MB, and on small
/// cards 2 MB, the coarser blocks' own line (r13e had 8 MB): decoded ASTC took 1.3-1.85 GB as RGBA8 there, and BC3 is a
/// quarter of that. (r13g: all but the smallest, as the other Ocarina port keeps its textures compressed below 20 GiB of
/// VRAM, since Windows counts video memory against the commit limit)
/// (AkynoLeyend r13l) Not on an integrated GPU: there it stays at 64 MB whatever the class. Intel Graphics (275HX, driver
/// 101.9150) with fine ASTC as BC3 from 2 MB: 163 textures (225 MB) counted as GPU-written and kept, against 30-35 without it, and
/// Kokiri turned to black silhouettes some 15 s into the game (Link, ferns, ground; the user's video and a run here); with the
/// same 64 MB blocks and fine ASTC as RGBA8 it did not. The 3 of 6 code-70 device losses seen with r13k were all with it.
inline uint64_t astc_bc_fine_bytes(uint64_t vram, bool integrated = false) {
    return (!integrated && vram_small(vram) ? 2ull : 64ull) << 20;
}

/// Presents a texture goes unused before it may go: the configured figure (RX_VK_EVICT_MIN_UNUSED, 60), 8 from critical on.
inline uint64_t evict_min_unused(VramLevel level, uint64_t configured) {
    return level >= VRAM_CRITICAL ? std::min<uint64_t>(configured, 8) : configured;
}

/// (AkynoLeyend r13i, Hookshot PR 2826) What the eviction pass lets the textures go down to (`total` bytes of them). size_budget:
/// the budget as a size (the card's default, RX_VK_VRAM_MB or the Quality preset's); budget: what the 90% rule, the driver's
/// limit (97%) and the commit rule made of it, never more. Those rules are not sizes: each is "what the textures hold less the
/// excess over a line", crossed again whenever anything grows. Cut to 7/8 of it, a few MB over the line took an eighth of the
/// cache: Castle Town Market on an RTX 3060 Ti went 2.95 -> 2.5 -> 2.95 GB every few seconds, the textures on screen again
/// within the camera's turn, made again (this PC's log: "504 textures retired (2080 left, 2562 MB)" after 2936 MB). So for
/// them what goes is the excess and `slack` (64 MB) more, so that not every pass is one; the size still asks for its 7/8.
/// UINT64_MAX: nothing. excess_only false (RX_VK_EVICT_EXCESS=0): budget's 7/8, as before.
inline constexpr uint64_t kEvictExcessSlack = 64ull << 20;
inline uint64_t evict_target(uint64_t total, uint64_t size_budget, uint64_t budget, bool excess_only = true,
                             uint64_t slack = kEvictExcessSlack) {
    if (!excess_only || budget >= size_budget) return budget / 8 * 7;
    uint64_t to = total > size_budget ? size_budget / 8 * 7 : UINT64_MAX;
    if (total > budget) to = std::min(to, budget - std::min(budget, slack));
    return to;
}

/// Whether the blocks are worth compacting: critical or over, with more than `slack` (256 MB) free inside them.
inline bool vram_compact_wanted(VramLevel level, uint64_t block_free, uint64_t slack = 256ull << 20) {
    return level >= VRAM_CRITICAL && block_free > slack;
}

/// One block of the image pool: what is allocated in it, and how much of that the textures that may go hold.
struct BlockUse {
    uint64_t allocated = 0, evictable = 0;
};

/// The blocks to empty, fewest allocated bytes first: only those whose every allocation may go (any other one keeps the
/// block the driver's), until `need` bytes of blocks are given back. Indices into blocks.
inline std::vector<size_t> blocks_to_empty(const std::vector<BlockUse>& blocks, uint64_t block_bytes, uint64_t need) {
    std::vector<size_t> order;
    for (size_t i = 0; i < blocks.size(); i++)
        if (blocks[i].allocated && blocks[i].evictable >= blocks[i].allocated) order.push_back(i);
    std::stable_sort(order.begin(), order.end(),
                     [&](size_t a, size_t b) { return blocks[a].allocated < blocks[b].allocated; });
    std::vector<size_t> out;
    uint64_t freed = 0;
    for (size_t i : order) {
        if (freed >= need) break;
        out.push_back(i);
        freed += block_bytes;
    }
    return out;
}

} // namespace mkwvk
