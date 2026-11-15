#pragma once
#include <algorithm>
#include <cerrno>
#include <cstddef>
#include <cstdlib>
#include <limits>
namespace mkwvk::cache {
inline size_t setting(const char* name, size_t fallback, size_t lo, size_t hi) {
    const char* text = std::getenv(name);
    if (!text || !*text || *text == '-') return fallback;
    char* end = nullptr; errno = 0;
    const auto n = std::strtoull(text, &end, 10);
    return errno || !end || *end ? fallback : (size_t)std::clamp<unsigned long long>(n, lo, hi);
}
struct Policy {
    bool streaming = false;
    size_t stream_bytes = 0, stream_entries = 128, queue = 8, read_bytes_per_second = 64u << 20;
    size_t index_records = std::numeric_limits<size_t>::max();
    size_t warm_bytes = std::numeric_limits<size_t>::max(), warm_programs = std::numeric_limits<size_t>::max();
    size_t warm_pipelines = std::numeric_limits<size_t>::max(), driver_io_bytes = std::numeric_limits<size_t>::max();
    size_t workers = 0, warm_per_second = 0;
    static constexpr size_t max_record = 64u << 20;
};
inline Policy read_policy() {
    Policy p; p.streaming = setting("RX_VK_CACHE_STREAM", 0, 0, 1) != 0;
    if (!p.streaming) return p;
    p.stream_bytes = setting("RX_VK_CACHE_READ_MB", 16, 0, 256) << 20;
    p.queue = setting("RX_VK_CACHE_QUEUE", 8, 1, 32);
    p.index_records = setting("RX_VK_CACHE_INDEX_RECORDS", 65536, 1024, 262144);
    p.read_bytes_per_second = setting("RX_VK_CACHE_READ_MBPS", 64, 1, 1024) << 20;
    p.warm_bytes = setting("RX_VK_PREWARM_MB", 64, 0, 4096) << 20;   // (0.4.8: up to 4 GiB, 64K programs and notes)
    p.warm_programs = setting("RX_VK_PREWARM_PROGRAMS", 128, 0, 65536);
    p.warm_pipelines = setting("RX_VK_PREWARM_PIPELINES", 256, 0, 65536);
    p.driver_io_bytes = setting("RX_VK_PIPE_CACHE_IO_MB", 128, 0, 1024) << 20;
    p.workers = setting("RX_VK_COMPILE_THREADS", 2, 1, 8);
    p.warm_per_second = setting("RX_VK_PREWARM_PER_SECOND", 5, 1, 100);
    return p;
}
// The launcher accepts 1..8 compilation workers. Apply the same bound to
// seed translation and driver pipeline warmup, including non-streaming builds.
// Without this, the pipeline stage can launch up to 64 threads while ignoring
// the user's setting; each concurrent driver compilation can consume memory.
inline unsigned warmup_workers(unsigned hardware_threads, size_t tasks, unsigned default_threads) {
    if (!tasks) return 0;
    const unsigned reasonable = std::max(1u, std::min(hardware_threads ? hardware_threads : 1u, 8u));
    const size_t requested = setting("RX_VK_COMPILE_THREADS", default_threads, 1, 8);
    return (unsigned)std::min<size_t>(tasks, std::min<size_t>(reasonable, requested));
}
inline const Policy& policy() { static const Policy p = read_policy(); return p; }
} // namespace mkwvk::cache
