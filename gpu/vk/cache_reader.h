#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <stdexcept>
namespace mkwvk::cache {
class Reader {
    const uint8_t* cursor;
    const uint8_t* end;
public:
    Reader(const uint8_t* data, size_t size) : cursor(data), end(data+size) {}
    size_t remaining() const { return (size_t)(end-cursor); }
    void copy(void* out, size_t size) {
        if (size > remaining()) throw std::runtime_error("truncated cache record");
        std::memcpy(out, cursor, size); cursor += size;
    }
    template<class T> T get() { T value{}; copy(&value, sizeof value); return value; }
    uint64_t count(size_t minimum) {
        const auto n = get<uint64_t>();
        if (!minimum || n > remaining()/minimum) throw std::runtime_error("invalid cache count");
        return n;
    }
    template<class V> void list(V& out) {
        using T = typename V::value_type;
        const auto n = count(sizeof(T)); out.clear();
        for (uint64_t i = 0; i < n; ++i) out.push_back(get<T>());
    }
};
}
