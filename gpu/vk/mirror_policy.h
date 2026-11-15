// Memory policy adapted from the observed 12 GiB pressure case. No game data.
#pragma once
#include <algorithm>
#include <cstdint>

namespace mkwvk {
inline uint64_t default_mirror_budget(uint64_t vram) {
    constexpr uint64_t gib = 1ull << 30, tolerance = 512ull << 20;
    if (!vram) return 3 * gib;
    if (vram <= 6 * gib + tolerance) return vram / 8;
    // Keep the 8 GiB policy: that class has also reported PCIe stalls with small mirrors.
    // The 12 GiB class competes with a texture cache of up to 6 GiB: leave it room.
    if (vram >= 11 * gib && vram <= 12 * gib + tolerance) return gib;
    return std::min<uint64_t>(vram / 4, 3 * gib);
}

inline bool idle_mirror_can_retire(uint64_t idle_epochs, uint64_t last_value, uint64_t completed) {
    return idle_epochs > 600 && last_value <= completed;
}

inline constexpr uint64_t kMirrorInheritEpochs = 600;
inline constexpr uint64_t kMirrorLongIdleEpochs = 6000;
inline constexpr uint64_t kMirrorPressureTrimBytes = 128ull << 20;
} // namespace mkwvk
