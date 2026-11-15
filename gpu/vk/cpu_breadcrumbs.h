// Diagnostic record of CPU recording order. It does not identify GPU completion
// or the faulting shader.
#pragma once
#include <array>
#include <cstdint>
#include <mutex>
#include <vector>
namespace mkwvk {
struct CpuBreadcrumb {
  uint64_t sequence = 0, key = 0, frame = 0;
  char kind = 0;
};
class CpuBreadcrumbs {
  std::mutex mutex;
  std::array<CpuBreadcrumb, 64> ring{};
  uint64_t next = 0;

public:
  void record(uint64_t key, uint64_t frame, char kind) {
    std::lock_guard lock(mutex);
    const uint64_t seq = ++next;
    ring[(seq - 1) % ring.size()] = {seq, key, frame, kind};
  }
  std::vector<CpuBreadcrumb> snapshot() {
    std::lock_guard lock(mutex);
    std::vector<CpuBreadcrumb> out;
    const uint64_t start = next > ring.size() ? next - ring.size() : 0;
    for (uint64_t i = start; i < next; i++)
      out.push_back(ring[i % ring.size()]);
    return out;
  }
};
} // namespace mkwvk
