#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <vector>
struct Update { uint64_t dst; std::vector<uint8_t> bytes; };
struct Updates {
    std::vector<Update> values;
    unsigned reads=0;
    const Update& operator[](size_t i) { ++reads;return values[i]; }
} ub_updates;
std::atomic<uint64_t> ub_list_epoch{1};
// ACTUAL_GAP_FUNCTIONS
int main() {
    ub_updates.values={{100,std::vector<uint8_t>(10)},{200,std::vector<uint8_t>(10)}};
    assert(ub_try_gap(0,2,150,4));
    const unsigned before=ub_updates.reads;
    for(unsigned i=0;i<10000;i++)assert(ub_gap_holds(150,4,0,2));
    assert(ub_updates.reads==before); // Repeated misses no longer scan the updates.
    assert(!ub_gap_holds(108,4,0,2));
    assert(!ub_gap_holds(150,4,1,2));
    ub_updates.values.push_back({155,std::vector<uint8_t>(8)});
    ub_list_epoch.fetch_add(1);
    assert(!ub_gap_holds(150,4,0,2));
    assert(ub_try_gap(0,3,150,4));
    assert(!ub_try_gap(0,3,154,4));
    ub_updates.values.erase(ub_updates.values.begin());ub_list_epoch.fetch_add(1);
    assert(!ub_gap_holds(150,4,0,3));
    const uint64_t dst[]={100,200},end[]={110,210};uint64_t lo=0,hi=0;
    assert(ub_gap(dst,end,2,110,90,&lo,&hi)&&lo==110&&hi==200);
    assert(!ub_gap(dst,end,2,UINT64_MAX-2,8,&lo,&hi));
    assert(!ub_gap(dst,end,2,150,0,&lo,&hi));
}
