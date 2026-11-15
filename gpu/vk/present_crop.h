// Present, interpolation and upscaling must use the same bounded source rectangle.
#pragma once

#include <algorithm>
#include <cstdint>
#include <limits>

namespace mkwvk {

struct PresentCrop {
    int32_t x = 0, y = 0;
    uint32_t width = 0, height = 0;
};

inline bool present_crop(uint32_t width, uint32_t height, const int crop[4], PresentCrop& out) {
    out = {};
    // VkImageBlit offsets are signed, even though image extents are unsigned.
    if (!width || !height || width > uint32_t(std::numeric_limits<int32_t>::max()) ||
        height > uint32_t(std::numeric_limits<int32_t>::max())) return false;
    if (!crop || crop[2] <= 0 || crop[3] <= 0) {
        out = {0, 0, width, height};
        return true;
    }
    const int64_t x0 = std::max<int64_t>(crop[0], 0), y0 = std::max<int64_t>(crop[1], 0);
    const int64_t x1 = std::min<int64_t>(int64_t(crop[0]) + crop[2], width);
    const int64_t y1 = std::min<int64_t>(int64_t(crop[1]) + crop[3], height);
    if (x1 <= x0 || y1 <= y0) return false;
    out = {int32_t(x0), int32_t(y0), uint32_t(x1 - x0), uint32_t(y1 - y0)};
    return true;
}

// The window can be 16:10 while a movie or the game itself is 16:9.
// Fit the source into the swapchain without changing its proportions.
inline PresentCrop fit_present(PresentCrop source, uint32_t width, uint32_t height) {
    if (!source.width || !source.height || !width || !height ||
        width > uint32_t(INT32_MAX) || height > uint32_t(INT32_MAX)) return {};
    uint32_t w = width, h = height;
    if (uint64_t(width) * source.height > uint64_t(height) * source.width)
        w = std::max(1u, uint32_t(uint64_t(height) * source.width / source.height));
    else
        h = std::max(1u, uint32_t(uint64_t(width) * source.height / source.width));
    return {int32_t((width - w) / 2), int32_t((height - h) / 2), w, h};
}

} // namespace mkwvk
