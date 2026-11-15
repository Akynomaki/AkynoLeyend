"""Execute production binding updates and shader-layout selection with synthetic state."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def function(source, marker):
    start = source.index(marker)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class ReplayPerformanceTests(unittest.TestCase):
    def execute(self, source):
        compiler = shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "check.cpp").write_text(source)
            binary = path / "check"
            built = subprocess.run([compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                                    "-I" + str(ROOT / "gpu/render"), str(path / "check.cpp"), "-o", str(binary)],
                                   capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stderr)
            env = {k: v for k, v in os.environ.items() if not k.startswith(("HOS_", "RX_"))}
            result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_identical_bindings_keep_descriptors_and_real_changes_invalidate(self):
        source = (ROOT / "gpu/vk/vk_replay.cpp").read_text()
        begin = source.index("        case NOP_BIND_BUFS:")
        end = source.index("        case NOP_STENCIL:", begin)
        cases = source[begin:end]
        helpers = function(source, "bool handles_unchanged(") + function(source, "bool buf_unchanged(")
        helpers += "template<class T> " + function(source, "T payload(")
        fixture = r'''
#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <cstdlib>
#include <cstring>
#define _Static_assert static_assert
#include "rx_nvn.h"
constexpr int kNvnStages=8;
struct State {uint64_t bind_gen{},tex_gen[8]{},ssbo_gen[8]{};
nvn_p_bind_buf ubo[8][16]{},ssbo[8][16]{};uint64_t tex[8][128]{},samp[8][128]{},img[8][32]{};};
struct Host {bool gpu_read(uint64_t,void*,uint64_t){return false;}} host_value;
Host* host=&host_value;bool deferred_late(){return false;}
void logf(const char*,...){} void log_stage_bind(int,int){}
'''
        fixture += helpers + r'''
template<class T> void bind(State& s,int op,const T& value){
    const auto* a=reinterpret_cast<const uint8_t*>(&value);const uint32_t avail=sizeof value;
    struct {int op;uint32_t size;} h{op,sizeof value+8};switch(op){
''' + cases + 'default:break;}}\n'
        fixture += r'''
int main(){State s;
nvn_p_bind_buf u{};u.stage=0;u.index=3;u.addr=0x1000;u.size=64;
bind(s,NOP_BIND_UBO,u);assert(s.bind_gen==1);bind(s,NOP_BIND_UBO,u);assert(s.bind_gen==1);
u.addr=0x2000;bind(s,NOP_BIND_UBO,u);assert(s.bind_gen==2);
bind(s,NOP_BIND_SSBO,u);assert(s.bind_gen==3 && s.ssbo_gen[0]==3 && s.tex_gen[0]==0);
bind(s,NOP_BIND_SSBO,u);assert(s.bind_gen==3);
u.index=4;bind(s,NOP_BIND_UBO,u);assert(s.bind_gen==4 && s.ssbo_gen[0]==3);
nvn_p_bind_handles h{};h.stage=0;h.first=0;h.n=2;h.h[0]=0x123;h.h[1]=0x456;
bind(s,NOP_BIND_TEX,h);assert(s.bind_gen==5 && s.tex_gen[0]==5);
bind(s,NOP_BIND_TEX,h);assert(s.bind_gen==5);
bind(s,NOP_BIND_SAMP,h);assert(s.bind_gen==6 && s.tex_gen[0]==6);
h.first=4;bind(s,NOP_BIND_IMG,h);assert(s.bind_gen==7 && s.tex_gen[0]==7);
h.stage=7;bind(s,NOP_BIND_TEX,h);assert(s.bind_gen==8 && s.tex_gen[7]==8);
const auto before=s.bind_gen;
for(int first:{-1,32,128,999}){h.stage=0;h.first=first;bind(s,NOP_BIND_IMG,h);assert(s.bind_gen==before);}
h.stage=99;h.first=0;bind(s,NOP_BIND_TEX,h);assert(s.bind_gen==before);
h.stage=0;h.n=-1;bind(s,NOP_BIND_TEX,h);assert(s.bind_gen==before);
nvn_p_bind_bufs many{};many.stage=2;many.first=0;many.ssbo=1;many.n=2;
many.r[0].address=0x3000;many.r[0].size=128;many.r[1].address=0x4000;many.r[1].size=256;
bind(s,NOP_BIND_BUFS,many);auto generation=s.bind_gen;assert(generation==before+2 && s.ssbo_gen[2]==generation);
bind(s,NOP_BIND_BUFS,many);assert(s.bind_gen==generation);
many.r[1].size=512;bind(s,NOP_BIND_BUFS,many);assert(s.bind_gen==generation+1 && s.ssbo_gen[2]==generation+1);
}
'''
        self.execute(fixture)

    def test_unrelated_graphics_ubo_changes_do_not_refill_driver_banks(self):
        source = (ROOT / "gpu/vk/vk_draw.cpp").read_text()
        start = source.index('        static const bool stage_gen_off =')
        end = source.index('        if (!no_bank_cache', start)
        body = source[start:end]
        self.execute(r'''
#include <algorithm>
#include <cstdlib>
#include <cstdint>
#include <cassert>
constexpr int kNvnStages=8;
struct State{uint64_t bind_gen=100,tex_gen[8]{},ssbo_gen[8]{};};struct Stage{int nvn_stage;};
uint64_t generation(const State&s,const Stage&st,uint32_t index){
''' + body + r'''return gen;}
int main(){State s;s.tex_gen[0]=10;s.ssbo_gen[0]=20;Stage vertex{0};
assert(generation(s,vertex,0)==20 && generation(s,vertex,2)==10);
for(int i=0;i<5000;++i){s.bind_gen++;assert(generation(s,vertex,0)==20 && generation(s,vertex,2)==10);}
s.ssbo_gen[0]=s.bind_gen;assert(generation(s,vertex,0)==s.bind_gen && generation(s,vertex,2)==10);
for(int stage:{5,6,7}){Stage special{stage};assert(generation(s,special,0)==s.bind_gen && generation(s,special,2)==s.bind_gen);}
}
''')

    def test_seed_compute_layout_uses_its_control_without_polluting_live_cache(self):
        source = (ROOT / "gpu/vk/vk_bank.cpp").read_text()
        start = source.index("struct CsLayout {")
        end = source.index("CsLayout cs_layout(const", start)
        layout = source[start:end]
        layout += function(source, "CsLayout cs_layout(const")
        self.execute(r'''
#include <cstdint>
#include <cassert>
#include <initializer_list>
#include <cstdlib>
#include <cstdio>
#include <mutex>
#include <unordered_map>
thread_local const uint8_t* seed_cs_control=nullptr;
struct NvnState {uint32_t cs_push_n=0;struct {uint64_t serial=23;uint32_t nstage=0;struct {uint64_t control=0;} sd[6];} prog;};
struct Host {bool gpu_read(uint64_t,void*,uint64_t){return false;}} host_object;
Host* host=&host_object;void logf(const char*,...){}
''' + layout + r'''
int main(){uint8_t control[0xd8]{};NvnState state;
assert(cs_layout(state).end()==0x10);
for(uint32_t push:{0u,1u,15u,21u,255u}){
control[0xa9]=push;control[0xb1]=3;control[0xb2]=8;control[0xb3]=5;control[0xb6]=2;
seed_cs_control=control;auto l=cs_layout(state);assert(l.push==((push*4+15)&~15u));
assert(l.ubo_at()==0x10+l.push);assert(l.ssbo_at()==l.ubo_at()+48);
assert(l.tex_at()==l.ssbo_at()+128);assert(l.img_at()==l.tex_at()+40);assert(l.end()==l.img_at()+16);
seed_cs_control=nullptr;assert(cs_layout(state).end()==0x10);
}}
''')


if __name__ == "__main__":
    unittest.main()
