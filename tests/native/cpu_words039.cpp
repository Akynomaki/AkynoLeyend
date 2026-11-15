#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <mutex>
#include <set>
#include <vector>
struct VkBufferCopy { uint64_t srcOffset,dstOffset,size; };
namespace mkwvk { namespace {
struct Pool { uint64_t lo; };
int forgotten=0;
void shadow_written_range(uint64_t guest,uint64_t size){assert(guest&&size);++forgotten;}
// ACTUAL_COUNTER_FUNCTIONS
} }
int main() {
    using namespace mkwvk;
    Pool pool{0x100000};
    memory_cpu_owned(pool.lo+24,16);
    memory_cpu_owned(pool.lo+48,8);
    std::vector<VkBufferCopy> runs{{0,0,64}};
    cut_cpu_words(pool,runs);
    assert(runs.size() == 3);
    assert(runs[0].srcOffset == 0 && runs[0].size == 24);
    assert(runs[1].srcOffset == 40 && runs[1].size == 8);
    assert(runs[2].srcOffset == 56 && runs[2].size == 8);
    std::vector<uint8_t> host(64,42), gpu(64,0);
    for (const auto& r : runs)
        std::copy_n(gpu.begin()+r.srcOffset,r.size,host.begin()+r.dstOffset);
    for (size_t i=0;i<host.size();i++) {
        const bool counter = (i>=24 && i<40) || (i>=48 && i<56);
        assert(host[i] == (counter ? 42 : 0));
    }
    runs={{24,24,16},{48,48,8}};cut_cpu_words(pool,runs);assert(runs.empty());
    const auto kept=cpu_words.size();
    memory_cpu_owned(pool.lo+9,0);
    memory_cpu_owned(UINT64_MAX-4,16);
    assert(cpu_words.size()==kept);
    assert(forgotten==2);
}
