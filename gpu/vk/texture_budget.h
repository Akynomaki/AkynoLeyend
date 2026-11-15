// Texture headroom, adapted from Hookshot v2.0.12 (GPL-3.0).
#pragma once
#include <algorithm>
#include <cstdint>
namespace mkwvk {
inline constexpr uint64_t kCommitReserve = 3072ull << 20;

inline bool commit_pressure_held(bool held, uint64_t commit_free) {
    return commit_free < kCommitReserve + (held ? 1024ull << 20 : 0);
}

inline uint64_t default_texture_budget(bool known, uint64_t allowed, bool integrated) {
    constexpr uint64_t mib = 1ull << 20;
    if (!known || !allowed) return integrated ? 2560 * mib : 4096 * mib;
    // Driver budgets vary with other applications. Keep room for targets,
    // mirrors and vertex/storage buffers on the 6–8 GB class.
    const uint64_t percent = allowed <= 8704 * mib ? 45 : 70;
    const uint64_t cap = integrated ? 2560 * mib : 6144 * mib;
    return std::min(allowed / 100 * percent, cap);
}
// (AkynoLeyend r8) Windows charges the process's commit for the video memory it allocates (measured on an RTX in
// Kokiri: about 9 GB committed and never touched beside 10 GB of VRAM in use), so on a PC short of commit (RAM plus
// page file) the textures end the run long before the VRAM is full. While the system has less than `reserve` of
// commit free, the texture budget is what the textures hold now less the shortfall, as near the driver's VRAM
// limit; never under `floor`, below which the scene evicts what it draws.
inline uint64_t commit_limited_budget(uint64_t budget, uint64_t textures, uint64_t commit_free,
                                      uint64_t reserve = kCommitReserve, uint64_t floor = 768ull << 20) {
    if (commit_free >= reserve) return budget;
    const uint64_t over = reserve - commit_free;
    return std::min(budget, std::max(textures > over ? textures - over : 0, std::min(budget, floor)));
}
}
