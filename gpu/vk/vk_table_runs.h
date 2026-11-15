// The guest page table's pending changes (vk_memory.cpp, memory_table_flush), turned into the transfers that write them:
// kept apart from Vulkan so that it can be compiled and compared with a plain reference (tests/test_table_runs_043.py).
//
// (11-10, Kokiri on a tester's PC) The flush used to expand every pending run into one (page, value) pair per page,
// duplicates included, in a vector it then sorted: 16 bytes for each page of each run, asked for at once, on the
// thread that records the frame. With the system's commit exhausted that allocation threw std::bad_alloc where
// nothing catches it. Here the runs are resolved as ranges: the memory used grows with the number of runs, not with
// the pages they cover, and the values go through one fixed block of at most 8192 entries (64 KiB, the size of one
// vkCmdUpdateBuffer).
//
// (r5) No two transfers of one flush write the same page, on either path. Transfers recorded one after the other in a
// command buffer are not ordered against each other by that alone: two writes of the same bytes need a memory
// dependency between them, and the barrier after the whole batch (texture_uploads_recorded) orders the batch against
// what reads it, not its transfers among themselves. So when the ranges cannot be allocated, the runs are not written
// in order over each other (r4 did): each run writes only the pages no later run sets, found by looking at the later
// runs again for every stretch. That needs no memory at all and costs time instead, only when memory was refused.
#pragma once

#include <cstddef>
#include <cstdint>
#include <new>
#include <vector>

namespace mkwvk {

struct TableRun { uint64_t first, count, address; };   // (pages [first, first + count): address + 4096 * i, or 0 for none)

constexpr size_t kTableChunk = 8192;        // (64-bit values in one transfer: vkCmdUpdateBuffer takes 65536 bytes at most)

struct TableFlushStats {
    uint64_t runs = 0;       // pending runs
    uint64_t pages_set = 0;  // pages over all runs, duplicates included (what was expanded before, 16 bytes each)
    uint64_t pages_out = 0;  // pages transferred (the unique ones, when resolved)
    uint64_t transfers = 0;
    uint64_t scratch = 0;    // bytes of temporary memory held for this flush (ranges and block)
    bool resolved = false;   // false: the ranges were not allocated (each run then writes what no later run sets)
};

inline uint64_t table_value(const TableRun& r, uint64_t i) { return r.address ? r.address + (i << 12) : 0; }

// The runs, in the order they were set, as disjoint ranges sorted by page, each page with the value set last.
// false: memory for the ranges was refused (out and spare are then left for the next flush; nothing was written).
inline bool table_runs_resolve(const std::vector<TableRun>& runs, std::vector<TableRun>& out, std::vector<TableRun>& spare) noexcept {
    try {
        out.clear();
        for (const TableRun& r : runs) {
            if (!r.count) continue;
            const uint64_t a = r.first, b = r.first + r.count;
            if (out.empty() || out.back().first + out.back().count <= a) {   // (after everything so far: the usual case)
                out.push_back(r);
                continue;
            }
            spare.clear();
            bool placed = false;
            for (const TableRun& s : out) {
                const uint64_t s0 = s.first, s1 = s.first + s.count;
                if (s1 <= a) {
                    spare.push_back(s);
                } else if (s0 >= b) {
                    if (!placed) spare.push_back(r), placed = true;
                    spare.push_back(s);
                } else {   // (overlapped: what of it lies before and after the new run stays)
                    if (s0 < a) spare.push_back({s0, a - s0, s.address});
                    if (!placed) spare.push_back(r), placed = true;
                    if (s1 > b) spare.push_back({b, s1 - b, table_value(s, b - s0)});
                }
            }
            if (!placed) spare.push_back(r);
            out.swap(spare);
        }
        return true;
    } catch (const std::bad_alloc&) {
        return false;
    }
}

// emit(first page, values, how many): one transfer. The block holds `capacity` values (kTableChunk, or fewer when
// even that was refused: more, smaller transfers, the same table).
template <class Emit>
void table_runs_flush(const std::vector<TableRun>& runs, std::vector<TableRun>& ranges, std::vector<TableRun>& spare,
                      uint64_t* block, size_t capacity, Emit&& emit, TableFlushStats& stats) {
    stats = TableFlushStats{};
    stats.runs = runs.size();
    for (const TableRun& r : runs) stats.pages_set += r.count;
    stats.resolved = table_runs_resolve(runs, ranges, spare);
    stats.scratch = (ranges.capacity() + spare.capacity()) * sizeof(TableRun) + capacity * sizeof(uint64_t);
    size_t held = 0;
    uint64_t held_first = 0;
    const auto send = [&] {
        if (!held) return;
        emit(held_first, (const uint64_t*)block, held);
        stats.transfers++;
        stats.pages_out += held;
        held = 0;
    };
    // (pages [from, to) of r: a transfer for each stretch of consecutive pages, cut at the block's size)
    const auto put = [&](const TableRun& r, uint64_t from, uint64_t to) {
        for (uint64_t page = from; page < to; page++) {
            if (held && (page != held_first + held || held == capacity)) send();
            if (!held) held_first = page;
            block[held++] = table_value(r, page - r.first);
        }
    };
    if (stats.resolved) {   // (disjoint already, in rising order)
        for (const TableRun& r : ranges) put(r, r.first, r.first + r.count);
    } else {
        // (no memory: of each run, the stretches that no later run covers. Disjoint by construction; a page is
        // written once, with the value of the last run that sets it)
        for (size_t i = 0; i < runs.size(); i++) {
            const TableRun& r = runs[i];
            const uint64_t end = r.first + r.count;
            for (uint64_t page = r.first; page < end;) {
                uint64_t stop = end;      // (where the next later run begins, if before this run's end)
                bool covered = false;
                for (size_t j = i + 1; j < runs.size(); j++) {
                    const uint64_t a = runs[j].first, b = runs[j].first + runs[j].count;
                    if (a <= page && page < b) {
                        page = b;         // (a later run sets it: on to that run's end, and looked at again)
                        covered = true;
                        break;
                    }
                    if (a > page && a < stop && b > a) stop = a;
                }
                if (covered) continue;
                put(r, page, stop);
                page = stop;
            }
        }
    }
    send();
}

} // namespace mkwvk
