// (AkynoLeyend r13h) NVN's running samples-passed count, as vk_occlusion.cpp takes its entries in stream order. No Vulkan
// here: tests/test_r13h_occlusion.py compiles and runs it.
#pragma once

#include <cstdint>

namespace mkwvk {

struct OcclusionRunning {
    uint64_t count = 0;   // (samples since the last reset)
    bool lost = false;    // (a draw since then went uncounted: the count is at least 1)
};

/// One entry: the samples of its queries added (lost: one of them, or a draw, went uncounted), then a reset zeroes the
/// count, or a report takes it. What a report writes: the count, at least 1 when anything went uncounted (a 0 culls what
/// the query tested, so an unknown count must not be 0). A reset returns 0.
inline uint64_t occlusion_fold(OcclusionRunning& r, uint64_t samples, bool lost, bool reset) {
    r.count += samples;
    r.lost = r.lost || lost;
    if (reset) {
        r = OcclusionRunning{};
        return 0;
    }
    return r.count ? r.count : r.lost ? 1 : 0;
}

} // namespace mkwvk
