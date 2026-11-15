#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <mutex>
#include <unordered_map>
constexpr unsigned kPageShift=12;
// ACTUAL_TRACKER
struct Host {uint64_t gpu_guest(uint64_t g){return g;}} value;
Host* host=&value;
bool behind=false;
int queue_waits=0,timeline_waits=0;
uint64_t done=0,last_wait=0;
bool replay_behind(){return behind;}
void wait_queue_empty(){queue_waits++;behind=false;wb_pages_note(4096,4100,19);}
uint64_t completed(){return done;}
void wait_value(uint64_t v){timeline_waits++;last_wait=v;done=v;}
void invalidate_test(uint64_t gpu,uint64_t size){
// ACTUAL_WAIT
}
int main(){
    bool ever=true;
    assert(memory_writeback_value(4096,4,&ever)==0&&!ever);
    wb_pages_note(4096,4100,7);
    wb_pages_note(12287,12289,12);
    assert(memory_writeback_value(4096,4,&ever)==7&&ever);
    assert(memory_writeback_value(12286,8,&ever)==12&&ever);
    assert(memory_writeback_value(UINT64_MAX-1,8,&ever)==0&&!ever);
    assert(memory_writeback_value(4096,0,&ever)==0&&!ever);
    behind=true;
    invalidate_test(4096,4);
    assert(queue_waits==1&&timeline_waits==1&&last_wait==19);
    invalidate_test(4096,4);
    assert(queue_waits==1&&timeline_waits==1);
    invalidate_test(16384,4);
    assert(queue_waits==1&&timeline_waits==1);
    // Spans cover both sides of a 2 MiB directory boundary.
    constexpr uint64_t edge = 2ull << 20;
    wb_pages_note(edge - 4096, edge + 8192, 23);
    wb_pages_note(edge + 2, edge + 7, 31);
    assert(memory_writeback_value(edge - 1, 1, &ever) == 23 && ever);
    assert(memory_writeback_value(edge - 1, 2, &ever) == 31 && ever);
    assert(memory_writeback_value(edge + 4096, 1, &ever) == 23 && ever);
    assert(memory_writeback_value(edge + 8192, 1, &ever) == 0 && !ever);
    return 0;
}
