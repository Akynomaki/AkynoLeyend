// Indexed HKSEED01 input: metadata stays in RAM, raw shader packages stay on disk.
#pragma once
#include <algorithm>
#include <array>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <vector>

namespace mkwvk::seedio {
inline constexpr size_t io_chunk = 64u << 10;
inline constexpr uint64_t raw_limit = 16u << 20;

inline bool seek(FILE* file, uint64_t offset) {
#ifdef _WIN32
    return _fseeki64(file, (int64_t)offset, SEEK_SET) == 0;
#else
    return fseeko(file, (off_t)offset, SEEK_SET) == 0;
#endif
}
inline uint32_t u32(const uint8_t* bytes) {
    return uint32_t(bytes[0]) | uint32_t(bytes[1]) << 8 | uint32_t(bytes[2]) << 16 | uint32_t(bytes[3]) << 24;
}
struct Stage {
    uint64_t control = 0, code = 0;
    uint32_t control_size = 0, code_size = 0, kind = 0;
};

class Reader {
    FILE* file = nullptr;
    uint64_t size = 0;
    std::mutex mu;
    std::vector<Stage> stages_;
    std::vector<uint64_t> programs_;
    size_t max_read_ = 0;

    bool at(uint64_t offset, void* out, size_t bytes) {
        if (!file || offset > size || bytes > size - offset) return false;
        std::lock_guard lock(mu);
        if (!seek(file, offset)) return false;
        auto* destination = static_cast<uint8_t*>(out);
        for (size_t done = 0; done < bytes;) {
            const size_t n = std::min(bytes - done, io_chunk);
            max_read_ = std::max(max_read_, n);
            if (std::fread(destination + done, 1, n, file) != n) return false;
            done += n;
        }
        return true;
    }

public:
    Reader() = default;
    Reader(const Reader&) = delete;
    Reader& operator=(const Reader&) = delete;
    ~Reader() { close(); }
    void close() {
        if (file) std::fclose(file);
        file = nullptr;
        std::vector<Stage>().swap(stages_);
        std::vector<uint64_t>().swap(programs_);
        size = 0;
        max_read_ = 0;
    }
    bool open(const char* path) {
        close();
        file = std::fopen(path, "rb");
        if (!file) return false;
        const auto fail = [&] { close(); return false; };
#ifdef _WIN32
        if (_fseeki64(file, 0, SEEK_END)) return fail();
        const int64_t length = _ftelli64(file);
#else
        if (fseeko(file, 0, SEEK_END)) return fail();
        const int64_t length = ftello(file);
#endif
        if (length < 16 || uint64_t(length) > (16ull << 30)) return fail();
        size = uint64_t(length);
        uint8_t header[20]{};
        if (!at(0, header, 16) || std::memcmp(header, "HKSEED01", 8)) return fail();
        const uint32_t programs = u32(header + 8), stages = u32(header + 12);
        if (!programs || !stages || programs > 262144 || stages > 262144 ||
            uint64_t(stages) * 20 + uint64_t(programs) * 8 > size - 16) return fail();
        stages_.reserve(stages);
        programs_.reserve(programs);
        uint64_t offset = 16;
        for (uint32_t i = 0; i < stages; i++) {
            if (!at(offset, header, 20)) return fail();
            Stage st{};
            st.kind = u32(header + 8);
            st.control_size = u32(header + 12);
            st.code_size = u32(header + 16);
            st.control = offset + 20;
            st.code = st.control + st.control_size;
            if (st.kind > 7 || st.control_size < 0x60 || st.control_size > 4096 ||
                !st.code_size || st.code_size > raw_limit || st.code > size || st.code_size > size - st.code)
                return fail();
            stages_.push_back(st);
            offset = st.code + st.code_size;
        }
        std::array<uint8_t, 16 * 4> ids{};
        for (uint32_t i = 0; i < programs; i++) {
            if (!at(offset, header, 4)) return fail();
            const uint32_t n = u32(header);
            if (!n || n > 16 || !at(offset + 4, ids.data(), size_t(n) * 4)) return fail();
            for (uint32_t k = 0; k < n; k++)
                if (u32(ids.data() + k * 4) >= stages) return fail();
            programs_.push_back(offset);
            offset += 4 + uint64_t(n) * 4;
        }
        if (offset != size) return fail();
        return true;
    }
    size_t stage_count() const { return stages_.size(); }
    size_t program_count() const { return programs_.size(); }
    const Stage& stage(size_t i) const { return stages_.at(i); }
    size_t max_read() const { return max_read_; } // Read only after workers join.
    bool control(size_t i, void* out, size_t bytes) {
        return i < stages_.size() && bytes <= stages_[i].control_size && at(stages_[i].control, out, bytes);
    }
    bool code(size_t i, uint64_t offset, void* out, size_t bytes) {
        return i < stages_.size() && offset <= stages_[i].code_size &&
               bytes <= stages_[i].code_size - offset && at(stages_[i].code + offset, out, bytes);
    }
    bool program(size_t i, std::vector<uint32_t>& out) {
        if (i >= programs_.size()) return false;
        uint8_t header[4];
        std::array<uint8_t, 16 * 4> ids{};
        if (!at(programs_[i], header, 4)) return false;
        const uint32_t n = u32(header);
        if (!n || n > 16 || !at(programs_[i] + 4, ids.data(), n * 4)) return false;
        out.resize(n);
        for (uint32_t k = 0; k < n; k++) {
            out[k] = u32(ids.data() + k * 4);
            if (out[k] >= stages_.size()) return false;
        }
        return true;
    }
};

// Bounds raw input held by simultaneous translators; driver/compiler memory is separate.
class RawBudget {
    std::mutex mu;
    std::condition_variable ready;
    uint64_t used = 0, peak_ = 0;
public:
    class Lease {
        RawBudget& budget;
        uint64_t bytes = 0;
    public:
        Lease(RawBudget& b, uint64_t n) : budget(b) {
            if (n > raw_limit) return;
            std::unique_lock lock(b.mu);
            b.ready.wait(lock, [&] { return n <= raw_limit - b.used; });
            bytes = n;
            b.used += n;
            b.peak_ = std::max(b.peak_, b.used);
        }
        Lease(const Lease&) = delete;
        Lease& operator=(const Lease&) = delete;
        ~Lease() {
            if (!bytes) return;
            { std::lock_guard lock(budget.mu); budget.used -= bytes; }
            budget.ready.notify_all();
        }
        explicit operator bool() const { return bytes != 0; }
    };
    uint64_t peak() { std::lock_guard lock(mu); return peak_; }
};
} // namespace mkwvk::seedio
