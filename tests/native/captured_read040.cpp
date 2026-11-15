#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <map>
#include <mutex>
#include <random>
#include "captured_read_cache.h"
using namespace mkwvk;
constexpr uint64_t kPageShift=12, high_gpu=1ull<<44;
std::array<uint8_t,65536> live{}, captured{};
struct Host {
    bool fail=false; uint64_t reads=0;
    uint64_t gpu_guest(uint64_t a){return a>=high_gpu?a-high_gpu:a;}
    bool gpu_read(uint64_t a,void* p,uint64_t n){
        reads++;a=gpu_guest(a);if(fail||a>live.size()||n>live.size()-a)return false;
        std::memcpy(p,live.data()+a,n);return true;
    }
} host_value;
Host* host=&host_value;
bool capture_enabled=true;
bool capture_on(){return capture_enabled;}
std::atomic<bool> captures_seen{true};
struct CapEntry {uint32_t gen=0,slot=0;};
struct CapBuf {void* map=nullptr;};
std::map<uint64_t,CapEntry> entries;
std::map<uint64_t,uint32_t> generations;
std::map<uint32_t,CapBuf> cap_bufs;
CapEntry cap_entry(uint64_t p){return entries[p];}
uint32_t page_gen(uint64_t p){return generations[p];}
std::atomic<uint64_t> captured_view{1};
uint32_t gen_now=1;
struct CountedMutex {
    std::mutex mutex;
    uint64_t locks = 0;
    void lock() { mutex.lock(); ++locks; }
    void unlock() { mutex.unlock(); }
} pools_mu;
void logf(const char*,...){}
// ACTUAL_READ
int main(){
    std::mt19937 rng(491);
    for(size_t i=0;i<live.size();i++){live[i]=uint8_t(i*13);captured[i]=uint8_t(i*7+1);}
    auto reset=[&]{entries.clear();generations.clear();cap_bufs.clear();++gen_now;
        for(uint32_t p=1;p<15;p++){
            generations[p]=gen_now;
            if(p%3){entries[p]={gen_now,p};}
        }
        cap_bufs[gen_now]={captured.data()};
        ++captured_view;
    };
    reset();
    std::array<uint8_t,64> result{},expected{};
    assert(memory_read_as_submitted(4096,result.data(),4));
    assert(memory_read_as_submitted(8192,result.data(),4));
    const auto locks = pools_mu.locks;
    for (unsigned i=0;i<128;i++) {
        const uint64_t address = i%2 ? 4096 : 8192;
        assert(memory_read_as_submitted(address,result.data(),4));
        assert(std::memcmp(result.data(),captured.data()+address,4)==0);
    }
    if (!std::getenv("AKYNO_READ_CACHE") || std::atoi(std::getenv("AKYNO_READ_CACHE")))
        assert(pools_mu.locks == locks);
    uint64_t prior_address=4096;
    for(unsigned i=0;i<40000;i++){
        if(i%263==0){++captured_view;}
        if(i%97==0){reset();}
        if(i%151==0){capture_enabled=!capture_enabled;}
        if(i%173==0){captures_seen=!captures_seen.load();}
        uint64_t n=1+rng()%32;
        uint64_t a=i%2?prior_address:4096+rng()%56000;
        if(i%5==0){n=4;a=8190;}
        prior_address=a;
        live[a]^=uint8_t(i);
        std::memcpy(expected.data(),live.data()+a,n);
        if(capture_on()&&captures_seen){
            for(uint64_t p=a>>12;p<((a+n+4095)>>12);p++){
                const auto e=cap_entry(p);
                if(!e.gen||e.gen!=page_gen(p)||!cap_bufs.count(e.gen))continue;
                uint64_t b=std::max(p*4096,a),z=std::min((p+1)*4096,a+n);
                std::memcpy(expected.data()+b-a,captured.data()+e.slot*4096+b-p*4096,z-b);
            }
        }
        const uint64_t address=a+(i%7==0?high_gpu:0);
        auto before=host->reads;
        assert(memory_read_as_submitted(address,result.data(),n));
        assert(host->reads==before+1);
        assert(std::memcmp(result.data(),expected.data(),n)==0);
        if(i%101==0){host->fail=true;assert(!memory_read_as_submitted(address,result.data(),n));host->fail=false;}
    }
    // Same key becomes invalid when a capture is retired or remapped, even within one submission.
    capture_enabled=true;captures_seen=true;reset();
    assert(memory_read_as_submitted(4096,result.data(),4));
    cap_bufs.clear();++captured_view;
    assert(memory_read_as_submitted(4096,result.data(),4));
    assert(std::memcmp(result.data(),live.data()+4096,4)==0);
    return 0;
}
