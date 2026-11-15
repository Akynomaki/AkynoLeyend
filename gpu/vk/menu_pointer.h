// Mouse geometry shared by the native overlay and its portable regression.
#pragma once
#include <algorithm>
#include <cstdint>
namespace mkwvk::menu_pointer {
inline constexpr int inset = 14, rows_top = 104, row_height = 28;
struct Point { int x, y; };
inline Point origin(int image_width, int image_height, int menu_width, int menu_height) {
    return {std::max(0, (image_width - menu_width) / 2), std::max(0, (image_height - menu_height) / 2)};
}
struct CopyRect { int x, y; uint32_t width, height; uint64_t offset; };
inline CopyRect clip(int x, int y, uint32_t bitmap_width, uint32_t bitmap_height,
                     uint32_t image_width, uint32_t image_height) {
    const int64_t left = std::max<int64_t>(0, x), top = std::max<int64_t>(0, y);
    const int64_t right = std::min<int64_t>(image_width, int64_t(x) + bitmap_width);
    const int64_t bottom = std::min<int64_t>(image_height, int64_t(y) + bitmap_height);
    if (right <= left || bottom <= top) return {};
    return {int(left), int(top), uint32_t(right - left), uint32_t(bottom - top),
            (uint64_t(top - y) * bitmap_width + uint64_t(left - x)) * 4};
}
inline int row(int x, int y, int width, int scale, int count) {
    if (scale < 1 || x < inset * scale || x >= width - inset * scale || y < rows_top * scale) return -1;
    const int n = (y - rows_top * scale) / (row_height * scale);
    return n < count ? n : -1;
}
inline int first_row(int first, int selected, int visible, int count) {
    return std::clamp(first, std::max(0, selected + 1 - visible), std::min(selected, count - visible));
}
inline int slider(int x, int width, int scale) {
    const int left = width / 2, right = width - 20 * scale;
    return right <= left ? 0 : std::clamp((x - left) * 100 / (right - left), 0, 100) / 10 * 10;
}
inline int image_coordinate(int position, int client, int image) {
    return client > 0 ? int((static_cast<long long>(position) * image) / client) : -1;
}
}
