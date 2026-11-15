#include <algorithm>
#include <atomic>
#include <iterator>
#include <new>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>
using VkCommandBuffer = int;
std::vector<uint64_t> table((12ull << 30) >> 12);
uint64_t* guest_pages = table.data();
int guest_pages_buffer = 1, guest_pages_allocation = 0;
struct Update { uint64_t offset; std::vector<uint64_t> words; };
std::vector<Update> updates;
void flush_mapped_range(int,uint64_t,uint64_t) {}
void logf(const char*, ...) {}
VkCommandBuffer upload_command_buffer() { return 1; }
void vkCmdUpdateBuffer(int,int,uint64_t offset,uint64_t bytes,const void* data) {
    assert(bytes && bytes <= 65536 && !(offset & 3) && !(bytes & 3));
    const auto* q = static_cast<const uint64_t*>(data);
    updates.push_back({offset,std::vector<uint64_t>(q,q+bytes/8)});
}
// ACTUAL_TABLE_FUNCTIONS
void apply() {
    for (const auto& u : updates)
        std::copy(u.words.begin(),u.words.end(),table.begin()+u.offset/8);
    updates.clear();
}
int main() {
    const uint64_t lo = 0x1000000000ull, other = 0x7f00000000ull;
    guest_pages_set(lo,lo+3*4096,0x100000);
    assert(table[0] == 0x100000 && table[2] == 0x102000);
    memory_table_begin();
    guest_pages_set(lo,lo+3*4096,0);
    guest_pages_set(lo,lo+3*4096,0x200000);
    assert(table[0] == 0x100000); // Previously submitted work sees the old table.
    assert(memory_table_flush());
    assert(table[0] == 0x100000); // Recording transfers must not modify host memory.
    assert(updates.size() == 1); apply();
    assert(table[0] == 0x200000 && table[2] == 0x202000);
    assert(!memory_table_flush());
    memory_table_begin();
    guest_pages_set(other,other+20000*4096ull,0x300000);
    assert(memory_table_flush() && updates.size() == 3); apply();
    const uint64_t first = (8ull<<30)>>12;
    assert(table[first] == 0x300000 && table[first+19999] == 0x300000+19999*4096ull);
    memory_table_begin();
    guest_pages_set(lo+4096,lo+8192,0x800000);
    guest_pages_set(lo+4096,lo+8192,0);
    assert(memory_table_flush()); apply();
    assert(table[0] == 0x200000 && table[1] == 0 && table[2] == 0x202000);
}
