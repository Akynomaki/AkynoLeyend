"""Execute production sampler generation/cache and captured-copy regressions."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def function(text, marker):
    start = text.index(marker); end = text.index('{', start) + 1; depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}'); end += 1
    return text[start:end]


class RendererCpuTests(unittest.TestCase):
    def test_nvidia_retired_imports_wait_for_the_replacement_and_gpu(self):
        cxx = shutil.which("c++")
        if not cxx:
            self.skipTest("C++ compiler unavailable")
        memory = (ROOT / "gpu/vk/vk_memory.cpp").read_text()
        code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <deque>
#include <map>
#include <vector>
using VkDeviceMemory = uint64_t;
using VkBuffer = uint64_t;
using VkDeviceAddress = uint64_t;
using VmaAllocation = void*;
constexpr uint64_t VK_NULL_HANDLE = 0;
struct { int device; } dev;
std::vector<uint64_t> released;
void vkDestroyBuffer(int, uint64_t handle, void*) { assert(handle); released.push_back(handle); }
void vkFreeMemory(int, uint64_t handle, void*) { assert(handle); released.push_back(handle); }
void logf(const char*, ...) {}
uint64_t pools_gen = 0;
uint64_t mem_completed = 0, mem_rec_value = 1;
'''
        code += memory[memory.index("constexpr uint64_t kWritebackShadowBytes"):memory.index("struct Pool {")]
        code += function(memory, "struct Pool {") + ";\n"
        code += r'''
std::map<uint64_t, Pool> imported;
std::deque<std::map<uint64_t, Pool>::node_type> retired_pools;
std::vector<Pool*> retired_imports;
struct TestMutex { void lock() {} void unlock() {} } pools_mu;
#include <mutex>
'''
        code += function(memory, "int memory_guest_imported(")
        code += function(memory, "void reclaim_retired_imports(")
        code += r'''
int main() {
    Pool& source = imported[0x2000];
    source.lo = 0x2000;
    source.hi = 0x8000;
    source.buffer = 11;
    source.memory = 12;
    source.address = 13;
    source.last_value = 8;
    source.retired_value = 9;
    source.inherit_pending = true;
    source.mirror = 14;
    retired_pools.push_back(imported.extract(source.lo));
    Pool& pool = retired_pools.back().mapped();
    retired_imports.push_back(&pool);
    mem_rec_value = 12;
    mem_completed = 10;
    reclaim_retired_imports();
    assert(!pool.import_release_value && released.empty());
    pool.inherit_pending = false;
    reclaim_retired_imports();
    assert(!pool.import_release_value && released.empty());
    pool.mirror = 0;
    mem_completed = 7;
    reclaim_retired_imports();
    assert(!pool.import_release_value && released.empty());
    mem_completed = 11;
    reclaim_retired_imports();
    assert(pool.import_release_value == 12 && released.empty());
    assert(memory_guest_imported(0x3000, 0x4000));
    mem_completed = 12;
    mem_rec_value = 13;
    reclaim_retired_imports();
    assert((released == std::vector<uint64_t>{11, 12}));
    assert(!memory_guest_imported(0x3000, 0x4000));
    assert(pool.lo == 0x2000 && pool.memory == 0 && pool.address == 0 && pool.buffer == 0);
    assert(retired_pools.size() == 1 && retired_imports.empty() && pools_gen == 1);
}
'''
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "imports.cpp"
            binary = Path(temp) / "imports"
            source.write_text(code, encoding="utf-8")
            result = subprocess.run([cxx, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                                     str(source), "-o", str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sampler_cache_reuses_only_current_registration_and_compare_mode(self):
        cxx = shutil.which('c++')
        if not cxx: self.skipTest('C++ compiler unavailable')
        bank = (ROOT/'gpu/vk/vk_bank.cpp').read_text()
        draw = (ROOT/'gpu/vk/vk_draw.cpp').read_text()
        code = r'''
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <thread>
#include <vector>
#define _Static_assert static_assert
#include "rx_nvn.h"
using VkSampler = uint64_t;
struct SampReg {nvn_samp_par p{};bool ok=false;};
std::mutex reg_mu;std::vector<SampReg> samp_regs;
std::atomic<uint64_t> samp_gen{1};std::atomic<int> made{0};
'''
        code += function(bank, 'void register_sampler_copy(')
        code += function(bank, 'uint64_t sampler_registrations_generation(')
        code += function(bank, 'bool sampler_of(')
        code += r'''
VkSampler sampler_make(int id,bool compare){++made;nvn_samp_par p{};sampler_of(id,&p);
return (uint64_t(id+2)<<24)+(uint64_t(p.minf)<<1)+(compare?1:0);}
'''
        code += function(draw, 'VkSampler sampler_for(int id, bool compare) {')
        code += r'''
int main(){
 const bool on=!getenv("RX_VK_SAMPLER_CACHE")||atoi(getenv("RX_VK_SAMPLER_CACHE"))!=0;
 nvn_samp_par p{};p.minf=1;register_sampler_copy(5,p);
 const auto gen=sampler_registrations_generation();register_sampler_copy(5,p);assert(sampler_registrations_generation()==gen);
 const auto original=sampler_for(5,false);for(int n=0;n<10000;n++)assert(sampler_for(5,false)==original);
 assert(made==(on?1:10001));
 auto before=made.load();assert(sampler_for(5,true)!=original);assert(made==before+1);
 p.minf=2;register_sampler_copy(5,p);assert(sampler_registrations_generation()==gen+1);
 assert(sampler_for(5,false)!=original);
 const auto changed=sampler_registrations_generation();register_sampler_copy(-1,p);register_sampler_copy(4096,p);
 assert(sampler_registrations_generation()==changed);
 before=made.load();sampler_for(-1,false);sampler_for(-1,false);assert(made==before+2);
 before=made.load();std::thread worker([]{sampler_for(5,false);sampler_for(5,false);});worker.join();
 assert(made==before+(on?1:2));
}
'''
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'sampler.cpp';binary=Path(temp)/'sampler';source.write_text(code)
            result=subprocess.run([cxx,'-std=c++20','-O2','-pthread','-Wall','-Wextra','-Werror',
                                   '-I'+str(ROOT/'gpu/render'),str(source),'-o',str(binary)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            for setting in ['0','1']:
                env=dict(os.environ,RX_VK_SAMPLER_CACHE=setting)
                result=subprocess.run([str(binary)],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_captured_copy_merging_preserves_every_byte_and_boundary(self):
        cxx=shutil.which('c++')
        if not cxx:self.skipTest('C++ compiler unavailable')
        result=subprocess.run([sys.executable,str(ROOT/'tools/test_capture_copy_runs.py'),'--cxx',cxx],
                              capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('PASS merged exact bytes',result.stdout)
