#include "shader_seed.h"
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstring>
#include <string>
#include <thread>
#include <vector>
using namespace mkwvk;

int main(int argc, char** argv) {
    assert(argc == 3);
    seedio::Reader reader;
    if (std::string(argv[2]) == "reject") {
        assert(!reader.open(argv[1]));
        assert(reader.program_count() == 0);
        return 0;
    }
    assert(reader.open(argv[1]));
    assert(reader.stage_count() == 2 && reader.program_count() == 2);
    std::vector<uint32_t> ids;
    assert(reader.program(0, ids) && ids == std::vector<uint32_t>({0, 1}));
    assert(reader.program(1, ids) && ids == std::vector<uint32_t>({1}));
    std::vector<uint8_t> code(reader.stage(0).code_size);
    assert(code.size() > seedio::io_chunk);
    assert(reader.code(0, 0, code.data(), code.size()));
    for (size_t i = 0; i < code.size(); i++) assert(code[i] == i % 251);
    std::array<uint8_t, 216> control{};
    assert(reader.control(0, control.data(), control.size()));
    assert(control[0] == 0x34 && control[1] == 0x12);
    assert(!reader.program(2, ids));
    assert(!reader.code(0, code.size(), code.data(), 1));
    assert(reader.max_read() == seedio::io_chunk);
    std::vector<std::thread> threads;
    for (int i = 0; i < 4; i++) threads.emplace_back([&] {
        for (int k = 0; k < 20; k++) {
            std::vector<uint8_t> local(257);
            assert(reader.code(0, 123, local.data(), local.size()));
            for (size_t n = 0; n < local.size(); n++) assert(local[n] == (n + 123) % 251);
        }
    });
    for (auto& thread : threads) thread.join();
    seedio::RawBudget budget;
    std::atomic<int> active{0}, peak{0};
    threads.clear();
    for (int i = 0; i < 8; i++) threads.emplace_back([&] {
        const seedio::RawBudget::Lease lease(budget, 9u << 20);
        assert(lease);
        const int n = ++active;
        int old = peak.load();
        while (old < n && !peak.compare_exchange_weak(old, n)) {}
        std::this_thread::sleep_for(std::chrono::milliseconds(2));
        --active;
    });
    for (auto& thread : threads) thread.join();
    assert(peak == 1 && budget.peak() <= seedio::raw_limit);
    { const seedio::RawBudget::Lease oversized(budget, seedio::raw_limit + 1); assert(!oversized); }
    // An exception cannot retain a reservation and hang future work.
    try { const seedio::RawBudget::Lease lease(budget, seedio::raw_limit); throw 1; } catch (int) {}
    { const seedio::RawBudget::Lease lease(budget, seedio::raw_limit); assert(lease); }
    reader.close();
    assert(reader.program_count() == 0 && reader.stage_count() == 0);
    std::puts("indexed seed checks passed");
}
