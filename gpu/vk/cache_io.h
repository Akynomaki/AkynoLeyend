// File chunks are separate from the contiguous Vulkan snapshot buffer.
#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstdio>
namespace mkwvk::cache {
inline constexpr size_t io_chunk = 64u << 10;
inline bool read_chunks(FILE* file, void* destination, size_t size) {
    auto* p = (uint8_t*)destination;
    for (size_t at = 0; at < size;) {
        const size_t n = std::min(io_chunk, size-at);
        if (std::fread(p+at, 1, n, file) != n) return false;
        at += n;
    }
    return true;
}
inline bool write_chunks(FILE* file, const void* source, size_t size) {
    const auto* p = (const uint8_t*)source;
    for (size_t at = 0; at < size;) {
        const size_t n = std::min(io_chunk, size-at);
        if (std::fwrite(p+at, 1, n, file) != n) return false;
        at += n;
    }
    return true;
}
}
