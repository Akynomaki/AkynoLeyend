// Adapted from Hookshot v2.0.14 (GPL-3.0); whole-word runs only.
#pragma once
#include <algorithm>
#include <cstdint>
namespace mkwvk {
inline uint64_t writeback_region_base(uint64_t at, uint64_t region_size) {
    return at - at % region_size;
}

// Split a valid pool-relative span at fixed-size region boundaries. The
// command still uses the original offsets for the mirror and guest buffers.
template <class F> void split_writeback_regions(uint64_t at, uint64_t size, uint64_t region_size, F&& emit) {
    while (size) {
        const uint64_t region = writeback_region_base(at, region_size);
        const uint64_t bytes = std::min(size, region_size - (at - region));
        emit(region, at, bytes);
        at += bytes;
        size -= bytes;
    }
}

template <class F> void wbd_split(uint64_t at, uint64_t size, F&& emit) {
    const uint64_t end = at + size;
    const uint64_t body = std::min<uint64_t>(end, (at + 15) & ~(uint64_t)15), body_end = std::max<uint64_t>(body, end & ~(uint64_t)15);
    if (body > at) emit(at, body - at, false);
    for (uint64_t a = body; a < body_end;) {
        const uint64_t len = std::min<uint64_t>(body_end - a, 64u << 10);
        emit(a, len, true);
        a += len;
    }
    if (end > body_end) emit(body_end, end - body_end, false);
}
}
