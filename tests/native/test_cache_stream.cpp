#include "cache_stream.h"
#include "cache_reader.h"
#include "cache_policy.h"
#include "cache_rate.h"
#include "cache_io.h"
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <future>
#include <limits>
using namespace mkwvk::cache;
using namespace std::chrono_literals;
#define CHECK(x) do {if (!(x)) {std::fprintf(stderr,"cache check failed at %d: %s\n",__LINE__,#x);std::abort();}} while (0)
int main(int argc,char**) {
    if (argc>1) {
        auto p=read_policy();
        CHECK(p.streaming && p.stream_bytes==(16u<<20) && p.workers==8 && p.queue==8);
        CHECK(p.warm_bytes==0 && p.driver_io_bytes==(128u<<20) && p.warm_per_second==5 && p.index_records==65536);
        CHECK(warmup_workers(24, 100, 4)==8); // env=999 is clamped to 8
        CHECK(warmup_workers(2, 100, 4)==2);  // never exceed logical CPUs
        CHECK(warmup_workers(24, 3, 4)==3);   // no idle workers
        CHECK(warmup_workers(24, 0, 4)==0);   // no threads for empty work
        puts("cache policy checks passed");return 0;
    }
    FILE* file=std::tmpfile();CHECK(file);
    for (int i=0;i<256;++i) std::fputc(i,file);
    std::fflush(file);std::atomic<unsigned> reads{0};const auto main_id=std::this_thread::get_id();
    {
        Stream s(80,2,2,0,[&](Range r,uint8_t* out){CHECK(std::this_thread::get_id()!=main_id);++reads;
            return !std::fseek(file,(long)r.offset,SEEK_SET) && read_chunks(file,out,r.size);});
        CHECK(s.request({0,40}) && s.request({40,40}) && s.wait_idle(2s));
        CHECK(s.request({40,40}) && s.request({80,40}) && s.wait_idle(2s));
        CHECK(reads==3 && s.take({0,40}).empty());
        auto a=s.take({40,40}),b=s.take({80,40});CHECK(a.size()==40 && b.size()==40);
        for (unsigned i=0;i<40;++i) CHECK(a[i]==i+40 && b[i]==i+80);
        CHECK(!s.request({1,81}));auto stats=s.stats();CHECK(stats.hits==2 && stats.misses==1 && stats.peak<=80 && stats.reserved==80);
        CHECK(!s.request({120,1}));a={};b={};CHECK(!s.stats().reserved);
    }
    std::fclose(file);
    {
        std::promise<void> started,release;auto go=release.get_future().share();
        Stream s(64,1,2,0,[&](Range r,uint8_t* out){started.set_value();go.wait();std::memset(out,9,r.size);return true;});
        CHECK(s.request({1,64}) && started.get_future().wait_for(2s)==std::future_status::ready);
        CHECK(s.request({1,64}) && !s.request({2,1}));
        CHECK(s.take({1,64}).empty()); // cannot wait for the blocked reader
        CHECK(s.stats().reserved==64 && s.stats().pending==1);
        release.set_value();CHECK(s.wait_idle(2s) && s.take({1,64}).size()==64);
        s.stop();CHECK(!s.request({3,1}));
    }
    {
        Stream bad(64,2,2,0,[](Range,uint8_t*){return false;});
        CHECK(bad.request({1,32}) && bad.wait_idle(2s) && !bad.stats().reserved && bad.stats().dropped==1);
        std::promise<void> started;std::atomic<int> calls{0};
        Stream slow(64,2,2,1,[&](Range r,uint8_t* out){std::memset(out,1,r.size);if (calls++==0) started.set_value();return true;});
        CHECK(slow.request({1,32}) && slow.request({40,32}));
        CHECK(started.get_future().wait_for(2s)==std::future_status::ready);
        auto now=std::chrono::steady_clock::now();slow.stop();CHECK(std::chrono::steady_clock::now()-now<2s && calls==1);
    }
    uint8_t wire[16]{};uint64_t count=2;uint32_t values[2]={42,73};
    std::memcpy(wire,&count,8);std::memcpy(wire+8,values,8);
    Reader reader(wire,16);std::vector<uint32_t> items;reader.list(items);CHECK(items.size()==2 && items[1]==73 && !reader.remaining());
    for (size_t n=0;n<16;++n) {bool rejected=false;try {Reader r(wire,n);r.list(items);}catch(const std::runtime_error&){rejected=true;}CHECK(rejected);}
    count=std::numeric_limits<uint64_t>::max();std::memcpy(wire,&count,8);bool rejected=false;
    try {Reader r(wire,16);r.list(items);}catch(const std::runtime_error&){rejected=true;}CHECK(rejected);
    auto now=TokenBucket::Clock::now();TokenBucket bucket(5,now);
    CHECK(bucket.try_take(now) && !bucket.try_take(now) && !bucket.try_take(now+199ms));
    CHECK(bucket.try_take(now+201ms) && bucket.try_take(now+10s) && !bucket.try_take(now+10s));
    std::vector<uint8_t> source(io_chunk*3+17),out(source.size());
    for(size_t i=0;i<source.size();++i) source[i]=(uint8_t)(i*17);
    file=std::tmpfile();CHECK(file && write_chunks(file,source.data(),source.size()));std::rewind(file);
    CHECK(read_chunks(file,out.data(),out.size()) && out==source && !read_chunks(file,out.data(),1));std::fclose(file);
    puts("cache stream checks passed: real disk I/O, eviction, byte/queue bounds, pending lookup, failures, throttle stop, reader, tokens, chunked files");
}
