// A single background reader with byte reservations shared by queued,
// in-flight, ready and consumer-owned payloads. Metadata and demand/driver allocations differ.
#pragma once
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <functional>
#include <list>
#include <memory>
#include <mutex>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>
namespace mkwvk::cache {
struct Range { uint64_t offset; size_t size; };
class Stream {
public:
    // Move-only payload: its bytes remain charged until decoding releases them.
    class Payload {
        friend class Stream;
        std::shared_ptr<std::atomic<size_t>> consumed;
        std::vector<uint8_t> bytes;
        size_t charged=0;
        Payload(std::vector<uint8_t>&& input,std::shared_ptr<std::atomic<size_t>> owner)
            : consumed(std::move(owner)),bytes(std::move(input)),charged(bytes.size()) {
            consumed->fetch_add(charged,std::memory_order_relaxed);
        }
        void release() {
            std::vector<uint8_t>().swap(bytes); // Free allocation before releasing its budget.
            if (consumed) consumed->fetch_sub(charged,std::memory_order_relaxed);
            consumed.reset();charged=0;
        }
    public:
        Payload()=default;
        Payload(const Payload&)=delete;
        Payload& operator=(const Payload&)=delete;
        Payload(Payload&& other) noexcept
            : consumed(std::move(other.consumed)),bytes(std::move(other.bytes)),charged(std::exchange(other.charged,0)) {}
        Payload& operator=(Payload&& other) noexcept {
            if (this!=&other) {release();consumed=std::move(other.consumed);bytes=std::move(other.bytes);charged=std::exchange(other.charged,0);}
            return *this;
        }
        ~Payload(){release();}
        bool empty() const {return bytes.empty();}
        size_t size() const {return bytes.size();}
        const uint8_t* data() const {return bytes.data();}
        const uint8_t& operator[](size_t n) const {return bytes[n];}
    };
    using Read = std::function<bool(Range,uint8_t*)>;
    struct Stats { size_t reserved=0, peak=0, pending=0, ready=0; uint64_t hits=0, misses=0, reads=0, dropped=0; };
private:
    struct Entry { Range range; bool ready=false; std::vector<uint8_t> bytes; std::list<uint64_t>::iterator lru; };
    const size_t budget, queue_limit, entry_limit, rate;
    Read read;
    std::function<void()> on_start;
    mutable std::mutex mu;
    std::condition_variable changed;
    std::deque<std::shared_ptr<Entry>> queue;
    std::unordered_map<uint64_t,std::shared_ptr<Entry>> entries;
    std::list<uint64_t> lru;
    Stats counters;
    std::shared_ptr<std::atomic<size_t>> consumed=std::make_shared<std::atomic<size_t>>(0);
    bool stopping=false;
    std::thread worker;
    bool evict() {
        if (lru.empty()) return false;
        auto it=entries.find(lru.back());
        counters.reserved-=it->second->range.size;
        entries.erase(it); lru.pop_back(); return true;
    }
    void run() {
        if (on_start) on_start();
        auto next=std::chrono::steady_clock::now();
        for (;;) {
            std::shared_ptr<Entry> entry;
            {
                std::unique_lock lock(mu);
                changed.wait(lock,[&]{return stopping || !queue.empty();});
                if (stopping || changed.wait_until(lock,next,[&]{return stopping;})) return;
                entry=queue.front(); queue.pop_front();
            }
            std::vector<uint8_t> data;
            bool ok=false;
            try { data.resize(entry->range.size); ok=read(entry->range,data.data()); } catch (...) { ok=false; }
            if (rate) next=std::chrono::steady_clock::now()+std::chrono::duration_cast<std::chrono::steady_clock::duration>(
                std::chrono::duration<double>((double)entry->range.size/rate));
            {
                std::lock_guard lock(mu); --counters.pending;
                if (ok) {
                    entry->bytes=std::move(data); entry->ready=true;
                    lru.push_front(entry->range.offset); entry->lru=lru.begin(); ++counters.reads;
                } else {
                    std::vector<uint8_t>().swap(data);
                    counters.reserved-=entry->range.size; entries.erase(entry->range.offset); ++counters.dropped;
                }
                entry.reset();
                changed.notify_all();
            }
        }
    }
public:
    Stream(size_t bytes,size_t pending,size_t count,size_t bytes_per_second,Read reader,std::function<void()> started={})
        : budget(bytes),queue_limit(pending),entry_limit(count),rate(bytes_per_second),read(std::move(reader)),
          on_start(std::move(started)),worker([this]{run();}) {}
    Stream(const Stream&)=delete;
    Stream& operator=(const Stream&)=delete;
    ~Stream(){stop();}
    void stop() {
        { std::lock_guard lock(mu); stopping=true; changed.notify_all(); }
        if (worker.joinable()) worker.join();
        std::lock_guard lock(mu); queue.clear(); entries.clear(); lru.clear(); counters.reserved=counters.pending=0;
    }
    bool request(Range range) {
        std::lock_guard lock(mu);
        if (stopping || !range.size || range.size>budget) {++counters.dropped;return false;}
        if (auto it=entries.find(range.offset);it!=entries.end()) return it->second->range.size==range.size;
        if (counters.pending>=queue_limit || !entry_limit) {++counters.dropped;return false;}
        while (range.size>budget-std::min(budget,counters.reserved+consumed->load(std::memory_order_relaxed)) || entries.size()>=entry_limit)
            if (!evict()) {++counters.dropped;return false;}
        auto e=std::make_shared<Entry>(); e->range=range;
        entries.emplace(range.offset,e); queue.push_back(e);
        counters.reserved+=range.size; counters.peak=std::max(counters.peak,counters.reserved+consumed->load(std::memory_order_relaxed)); ++counters.pending;
        changed.notify_all(); return true;
    }
    Payload take(Range range) {
        std::lock_guard lock(mu);
        auto it=entries.find(range.offset);
        if (it==entries.end() || !it->second->ready || it->second->range.size!=range.size) {++counters.misses;return {};}
        Payload data(std::move(it->second->bytes),consumed);
        counters.reserved-=it->second->range.size; lru.erase(it->second->lru); entries.erase(it); ++counters.hits;
        return data;
    }
    Stats stats() const {std::lock_guard lock(mu);auto s=counters;s.ready=lru.size();s.reserved+=consumed->load(std::memory_order_relaxed);return s;}
    bool wait_idle(std::chrono::milliseconds timeout) {std::unique_lock lock(mu);return changed.wait_for(lock,timeout,[&]{return !counters.pending || stopping;});}
};
}
