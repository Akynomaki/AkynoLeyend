#pragma once
#include <array>
#include <cstdint>
#include <cstring>
namespace mkwvk {
struct CapturedReadKey {
  uint64_t address, size, view;
  bool operator==(const CapturedReadKey &) const = default;
};
class CapturedReadCache {
  struct Entry {
    CapturedReadKey key{};
    std::array<uint8_t, 16> bytes{};
    bool valid = false;
  };
  std::array<Entry, 256> entries{};
  static size_t index(const CapturedReadKey &k) {
    return (size_t)(((k.address >> 2) ^ (k.address >> 11) ^ k.size) & 255);
  }

public:
  bool read(const CapturedReadKey &k, void *out) const {
    if (!k.size || k.size > 16)
      return false;
    const auto &e = entries[index(k)];
    if (!e.valid || !(e.key == k))
      return false;
    std::memcpy(out, e.bytes.data(), (size_t)k.size);
    return true;
  }
  void remember(const CapturedReadKey &k, const void *in) {
    if (!k.size || k.size > 16)
      return;
    auto &e = entries[index(k)];
    e.key = k;
    std::memcpy(e.bytes.data(), in, (size_t)k.size);
    e.valid = true;
  }
};
} // namespace mkwvk
