// (AkynoLeyend r13h) NVN's samples-passed counter (NVN_COUNTER_TYPE_SAMPLES_PASSED) counted with Vulkan occlusion queries.
//
// NVN keeps one running count on the queue: RESET_COUNTER zeroes it, every draw after it adds the samples that passed the
// depth and stencil tests, REPORT_COUNTER writes {count, timestamp} to memory. Ocarina tests what may be hidden this way
// hundreds of times a frame and culls on the counts its CPU reads back; the replay had no count (16 a draw, a guess) and the
// game's queries were turned off (AKYNO_OCCLUSION_OFF, nx2/oot_occlusion.py), so it drew every candidate: hidden scenery
// floating with nothing under it, and draws the frame did not need.
//
// Here, once the game has reset the counter, each pass with a draw gets an occlusion query (precise where the device has
// occlusionQueryPrecise) from its first draw to its end, or to the next reset or report, after which the next draw opens
// another (a query begun in a pass must end in it, and one of a type is active at a time). The queries closed since the
// last reset or report and that reset or report make an entry, queued in stream order with the timeline value of the
// submission that records them. Once that value is reached (occlusion_collect: at each recording and at the game's
// waits), the entries are taken in order: the queries' results added to the running count, a reset zeroing it, a
// report writing {count, timestamp} into guest memory. A draw the count should have seen and that went unrecorded (left
// out while its pipeline is built, or a full ring) makes its report at least 1, so it never culls what was not tested.
// The slots come from one ring, reset from the host once read (hostQueryReset): the replay records no reset commands.
// The serial replay only: with RX_VK_PARALLEL the reports keep the old count (vk_replay.cpp).
// Written for this project from NVN's counter semantics and the Vulkan specification.

#include "vk_occlusion.h"
#include "occlusion_count.h"

#include <atomic>
#include <cstdlib>
#include <deque>
#include <mutex>
#include <unordered_map>
#include <vector>

#include "vk_work.h"   // (after the Vulkan headers)

namespace mkwvk {
namespace {

constexpr uint32_t kSlots = 16384;   // (a few frames of Hyrule Field's passes and reports)
VkQueryPool pool = VK_NULL_HANDLE;
std::atomic<int> state{0};            // 0 not set up, 1 on, -1 off (read by the waits on the game's threads)
VkQueryControlFlags query_flags = 0;
std::atomic<uint8_t> busy[kSlots];    // (from its begin until it is read and reset)

// (the replay's side: the replay's lock is held)
uint32_t next_slot = 0;
int open_slot = -1;                   // (the query active in the open pass)
bool counting = false;                // (a reset seen: NVN's count runs from it on)
std::vector<uint32_t> closed;         // (closed since the last reset or report)
bool lost = false;

struct Entry {
    uint64_t value = 0;               // (the submission recording it)
    std::vector<uint32_t> slots;
    bool lost = false, reset = false;
    uint64_t addr = 0, timestamp = 0; // (a report)
};
std::mutex mu;                        // (the entries, the running count, the pending addresses)
std::deque<Entry> entries;
OcclusionRunning running;             // (occlusion_count.h)
std::unordered_map<uint64_t, int> pending_reports;
int64_t st_reports = 0, st_queries = 0, st_lost = 0, st_zero = 0;

struct QueryResult {
    uint64_t samples, available;
};
QueryResult results[kSlots];   // (shared scratch, protected by mu)

void collect_query_range(uint32_t first, uint32_t count) {
    if (!count) return;
    const VkResult status = vkGetQueryPoolResults(dev.device, pool, first, count, count * sizeof(QueryResult),
                                                   results + first, sizeof(QueryResult),
                                                   VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WITH_AVAILABILITY_BIT);
    if (status != VK_SUCCESS && status != VK_NOT_READY) {
        for (uint32_t slot = first; slot < first + count; ++slot) results[slot].available = 0;
    }
    vkResetQueryPool(dev.device, pool, first, count);
    for (uint32_t slot = first; slot < first + count; ++slot)
        busy[slot].store(0, std::memory_order_release);
}

void close_open(VkCommandBuffer cmd) {
    if (open_slot < 0) return;
    vkCmdEndQuery(cmd, pool, (uint32_t)open_slot);
    closed.push_back((uint32_t)open_slot);
    open_slot = -1;
}

void push(uint64_t value, bool reset, uint64_t addr, uint64_t timestamp) {
    Entry e;
    e.value = value, e.reset = reset, e.addr = addr, e.timestamp = timestamp;
    e.slots.swap(closed);
    e.lost = lost;
    lost = false;
    std::lock_guard lk(mu);
    if (!reset) pending_reports[addr]++;
    entries.push_back(std::move(e));
}

} // namespace

bool occlusion_on() {
    if (state) return state > 0;
    state = -1;
    if (const char* e = getenv("RX_VK_OCCLUSION"); e && !atoi(e)) {
        logf("vk: samples-passed counters: occlusion queries off (RX_VK_OCCLUSION=0): 16 a draw");
        return false;
    }
    if (!dev.vk12.hostQueryReset) {
        logf("vk: samples-passed counters: no host query reset on this device: 16 a draw");
        return false;
    }
    VkQueryPoolCreateInfo qi{VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO};
    qi.queryType = VK_QUERY_TYPE_OCCLUSION;
    qi.queryCount = kSlots;
    if (vkCreateQueryPool(dev.device, &qi, nullptr, &pool) != VK_SUCCESS) {
        logf("vk: samples-passed counters: the occlusion query pool was not made: 16 a draw");
        pool = VK_NULL_HANDLE;
        return false;
    }
    vkResetQueryPool(dev.device, pool, 0, kSlots);
    for (auto& b : busy) b.store(0, std::memory_order_relaxed);
    query_flags = dev.features.occlusionQueryPrecise ? VK_QUERY_CONTROL_PRECISE_BIT : 0;
    state = 1;
    logf("vk: samples-passed counters from occlusion queries (%s, %u slots)", query_flags ? "precise" : "not precise", kSlots);
    return true;
}

void occlusion_reset(VkCommandBuffer cmd, uint64_t value) {
    if (state <= 0) return;
    close_open(cmd);
    counting = true;
    push(value, true, 0, 0);
}

void occlusion_report(VkCommandBuffer cmd, uint64_t value, uint64_t addr, uint64_t timestamp) {
    if (state <= 0) return;
    close_open(cmd);
    push(value, false, addr, timestamp);
}

void occlusion_draw_in_pass(VkCommandBuffer cmd) {
    if (state <= 0 || !counting || open_slot >= 0) return;
    const uint32_t s = next_slot;
    uint8_t free_ = 0;
    if (!busy[s].compare_exchange_strong(free_, 1)) {   // (the ring came round to a slot not read yet)
        lost = true;
        st_lost++;
        return;
    }
    next_slot = (next_slot + 1) % kSlots;
    vkCmdBeginQuery(cmd, pool, s, query_flags);
    open_slot = (int)s;
    st_queries++;
}

void occlusion_pass_end(VkCommandBuffer cmd) {
    if (state <= 0) return;
    close_open(cmd);
}

void occlusion_draw_lost() {
    if (state <= 0 || !counting) return;
    lost = true;
    st_lost++;
}

bool occlusion_pending(uint64_t addr) {
    if (state <= 0) return false;
    std::lock_guard lk(mu);
    const auto it = pending_reports.find(addr);
    return it != pending_reports.end() && it->second > 0;
}

void occlusion_collect(uint64_t done) {
    if (state <= 0) return;
    std::lock_guard lk(mu);
    // Consecutive slots can be read together across reports, stopping at the completed
    // prefix and splitting at the end of the ring. Fold the reports in their original order.
    uint32_t first = 0, count = 0;
    for (const Entry& e : entries) {
        if (e.value > done) break;
        for (const uint32_t slot : e.slots) {
            if (slot != first + count || !count) {
                collect_query_range(first, count);
                first = slot;
                count = 0;
            }
            ++count;
        }
    }
    collect_query_range(first, count);

    while (!entries.empty() && entries.front().value <= done) {   // (0: recorded outside a submission, taken at once)
        Entry& e = entries.front();
        uint64_t sum = 0;
        bool missed = e.lost;
        for (const uint32_t s : e.slots) {
            if (results[s].available) sum += results[s].samples;
            else missed = true;   // (not available after its submission: counted as seen)
        }
        const uint64_t count = occlusion_fold(running, sum, missed, e.reset);
        if (!e.reset) {
            const uint64_t rec[2] = {count, e.timestamp};
            guest_cpu_write(e.addr, rec, sizeof rec);
            st_reports++;
            if (!rec[0]) st_zero++;
            const auto it = pending_reports.find(e.addr);
            if (it != pending_reports.end() && --it->second <= 0) pending_reports.erase(it);
            if (st_reports % 20000 == 0)
                logf("vk: samples-passed counters: %lld reports written (%lld of 0), %lld queries, %lld draws uncounted",
                     (long long)st_reports, (long long)st_zero, (long long)st_queries, (long long)st_lost);
        }
        entries.pop_front();
    }
}

} // namespace mkwvk
