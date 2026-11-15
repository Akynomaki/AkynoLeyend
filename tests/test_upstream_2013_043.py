"""Exercise the actual backported helpers without a game dump or a physical GPU."""
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


class Upstream2013Tests(unittest.TestCase):
    def test_resolution_patches_find_literal_bracket_paths_without_touching_neighbour(self):
        import contextlib
        import io
        import sys
        from unittest.mock import patch
        sys.path.insert(0,str(ROOT / "nx2"))
        import oot_patches
        with tempfile.TemporaryDirectory() as directory:
            literal=Path(directory)/"pasta [teste] com espaço";literal.mkdir()
            neighbour=Path(directory)/"pasta t com espaço";neighbour.mkdir()
            source='#include "a64.h"\n'+oot_patches.OLD+'\n'+oot_patches.LABEL+'\n'+oot_patches.SCALE_OLD+'\n'
            source+=oot_patches.APPLY_OLD+'\n'+oot_patches.FLAGS_OLD
            for folder in (literal,neighbour): (folder/"code_000.c").write_text(source, newline="\n")  # (LF bytes, as generated)
            with patch("oot_output_size.apply") as output, contextlib.redirect_stdout(io.StringIO()):
                oot_patches.apply(literal)
                oot_patches.apply(literal)  # same path and idempotent update
            self.assertEqual(output.call_count,2)
            self.assertIn(oot_patches.NEW,(literal/"code_000.c").read_text())
            self.assertEqual((neighbour/"code_000.c").read_text(),source)

    def test_hot_split_removes_only_own_stale_files_in_literal_bracket_path(self):
        import contextlib
        import io
        import sys
        sys.path.insert(0,str(ROOT / "nx2"))
        import split_hot
        with tempfile.TemporaryDirectory() as directory:
            literal=Path(directory)/"[build] com espaço";literal.mkdir()
            neighbour=Path(directory)/"b com espaço";neighbour.mkdir()
            (literal/"code_hot.c").write_text('void f_80000000(Ctx *__restrict A64_NOESC c) {\n}\n')
            for folder in (literal,neighbour): (folder/"code_hot_99.c").write_text('old')
            with contextlib.redirect_stdout(io.StringIO()): split_hot.split(literal,2)
            self.assertFalse((literal/"code_hot_99.c").exists())
            self.assertEqual((neighbour/"code_hot_99.c").read_text(),'old')
            self.assertTrue((literal/"code_hot_0.c").is_file())

    def test_only_verified_test3_source_can_enter_incremental_maintenance(self):
        from akynoleyend.coherence import compatible_previous_host, HOST_REVISION
        manifest={"version":"0.4.3-test.3", "host_revision":HOST_REVISION,
                  "source_sha256":"9b71fcc98444139a9c1388ca6d575ef5fa8cd1083693a450142e2a09b40c1e7a",
                  "game_build_id":"e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348"}
        self.assertTrue(compatible_previous_host(manifest))
        self.assertFalse(compatible_previous_host({**manifest,"source_sha256":"unknown"}))
        self.assertFalse(compatible_previous_host({**manifest,"host_revision":"other-abi"}))
        self.assertFalse(compatible_previous_host({**manifest,"game_build_id":"another-game"}))

    def run_cpp(self, source, cases=((),)):
        compiler = shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "check.cpp").write_text(source)
            binary = path / "check"
            built = subprocess.run([
                compiler, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror",
                "-fsanitize=undefined", "-fno-sanitize-recover=all",
                "-I" + str(ROOT / "gpu/vk"), "-I" + str(ROOT / "gpu/vk/eden"),
                "-I" + str(ROOT / "gpu/vk/compat"), str(path / "check.cpp"), "-o", str(binary)],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stderr)
            env = {k: v for k, v in os.environ.items() if not k.startswith(("HOS_", "RX_", "AKYNO_"))}
            for case in cases:
                run = subprocess.run([str(binary), *case], env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_lea_hi_constant_real_encodings_and_carry_guards(self):
        # Eden's generated arithmetic helpers have unused parameters in GCC.
        source = '#pragma GCC diagnostic ignored "-Wunused-parameter"\n'
        source += (ROOT / "tests/native/lower_lea_hi_constant.cpp").read_text()
        self.run_cpp(source)

    def test_overlay_clips_stride_and_matches_pointer_origin(self):
        self.run_cpp(r'''
#include <cassert>
#include "menu_pointer.h"
using namespace mkwvk::menu_pointer;
int main() {
    auto p = origin(1920, 1080, 720, 920);
    assert(p.x == 600 && p.y == 80);
    assert(row(620-p.x, 184-p.y, 720, 1, 15) == 0);
    p = origin(640, 400, 720, 920);
    assert(p.x == 0 && p.y == 0);
    auto r = clip(p.x, p.y, 720, 920, 640, 400);
    assert(r.width == 640 && r.height == 400 && r.offset == 0);
    r = clip(-10, -20, 720, 920, 640, 400);
    assert(r.x == 0 && r.y == 0 && r.offset == (20*720+10)*4);
    assert(r.width == 640 && r.height == 400);
    r = clip(20, 30, 100, 100, 640, 400);
    assert(r.x == 20 && r.y == 30 && r.width == 100 && r.height == 100);
    assert(clip(700, 0, 100, 100, 640, 400).width == 0);
    assert(clip(0, 400, 100, 100, 640, 400).height == 0);
    assert(clip(0, 0, 100, 100, 0, 0).width == 0);
    for (int w : {640, 1280, 1920, 2560, 3440, 3840, 5120})
        for (int h : {400, 720, 1080, 1440, 2160}) {
            p = origin(w, h, 720, 920);
            r = clip(p.x, p.y, 720, 920, w, h);
            assert(r.width && r.height && r.x >= 0 && r.y >= 0);
            assert(r.x+r.width <= (unsigned)w && r.y+r.height <= (unsigned)h);
        }
}
''')

    def test_texture_budget_leaves_room_for_buffers_and_unknown_budget(self):
        self.run_cpp(r'''
#include <cassert>
#include "texture_budget.h"
using mkwvk::default_texture_budget;
int main() {
    constexpr uint64_t M=1ull<<20;
    assert(default_texture_budget(false, 0, false) == 4096*M);
    assert(default_texture_budget(true, 0, true) == 2560*M);
    for (uint64_t n : {6, 8}) {
        uint64_t allowed=n*1024*M, budget=default_texture_budget(true, allowed, false);
        assert(budget == allowed/100*45 && budget < allowed/2);
    }
    assert(default_texture_budget(true, 12*1024*M, false) == 6144*M);
    assert(default_texture_budget(true, 4*1024*M, true) == 4*1024*M/100*45);
    assert(default_texture_budget(true, 12*1024*M, true) == 2560*M);
}
''')

    def test_texture_budget_follows_a_short_system_commit(self):
        self.run_cpp(r'''
#include <cassert>
#include "texture_budget.h"
using mkwvk::commit_limited_budget;
int main() {
    constexpr uint64_t M=1ull<<20;
    assert(commit_limited_budget(6144*M, 5000*M, 8000*M) == 6144*M);   // room: as it was
    assert(commit_limited_budget(6144*M, 5000*M, 3072*M) == 6144*M);
    assert(commit_limited_budget(6144*M, 5000*M, 2072*M) == 4000*M);   // 1 GB short: 1 GB of textures go
    assert(commit_limited_budget(3265*M, 5000*M, 2072*M) == 3265*M);   // never above the budget
    assert(commit_limited_budget(6144*M, 1000*M, 0) == 768*M);         // the floor
    assert(commit_limited_budget(512*M, 1000*M, 0) == 512*M);          // a budget under the floor stays
}
''')
        source = (ROOT / "gpu/vk/vk_texture.cpp").read_text(encoding="utf-8")
        self.assertIn("commit_limited_budget(budget, total_bytes, commit_free)", source)
        self.assertLess(source.index("commit_limited_budget(budget"), source.index("vma_log_heaps();"))

    def test_menu_reduces_whole_scale_steps_then_recovers_on_resize(self):
        s=(ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
        self.run_cpp(r'''
#include <cassert>
#include <cstdint>
#include <algorithm>
#include <mutex>
struct {struct {uint32_t width,height;} swap_extent;} dev;
std::mutex bmp_mu;
struct {uint32_t w=0,h=0;} menu_bmp;
int cur_scale=1,menu_fit=1<<20;
struct { int menu_size=2; } opts;
uint32_t menu_fit_w=0,menu_fit_h=0;
int scale_of(uint32_t h) {return std::max(1,int(h/720));}
void redraw_menu_at(int s) {menu_bmp.w=720*s;menu_bmp.h=920*s;}
''' + function(s,"int menu_scale_for(") + function(s,"void redraw_menu(") + r'''
int main() {
    dev.swap_extent={2560,1440};cur_scale=menu_scale_for(2560,1440);
    assert(cur_scale==2);redraw_menu(cur_scale);
    assert(cur_scale==1 && menu_bmp.h==920 && menu_scale_for(2560,1440)==1);
    dev.swap_extent={2560,1600};redraw_menu(menu_scale_for(2560,1600));
    assert(menu_bmp.w<=2560 && menu_bmp.h<=1600);
    dev.swap_extent={1280,720};redraw_menu(menu_scale_for(1280,720));
    assert(cur_scale==1 && menu_bmp.w<=1280);
    dev.swap_extent={3840,2160};cur_scale=menu_scale_for(3840,2160);
    assert(cur_scale==3);redraw_menu(cur_scale);assert(cur_scale==2 && menu_bmp.h==1840);
    dev.swap_extent={640,400};cur_scale=menu_scale_for(640,400);redraw_menu(cur_scale);
    assert(cur_scale==1 && menu_bmp.h==920); // clipped, not dropped, by copy_over
    dev.swap_extent={3840,2160};assert(menu_scale_for(3840,2160)==3);
}
''')

    def test_hybrid_core_selection_uses_fast_cores_and_avoids_small_laptops(self):
        s = (ROOT / "host/hos_thread.c").read_text()
        self.run_cpp(r'''
#include <cstdint>
#include <cassert>
#include <vector>
''' + function(s, "static uint64_t pick_reserved_core(") + r'''
uint64_t pick(int fast, int slow, bool ht) {
    std::vector<uint64_t> m; std::vector<unsigned char> c;
    int bit=0;
    for (int i=0; i<fast; ++i) { m.push_back((ht?3ull:1ull)<<bit); c.push_back(1); bit+=ht?2:1; }
    for (int i=0; i<slow; ++i) { m.push_back(1ull<<bit++); c.push_back(0); }
    return pick_reserved_core(m.data(), c.data(), (int)m.size());
}
int main() {
    assert(pick(12, 0, true)==0xc00000);
    assert(pick(6, 0, true)==0xc00);
    assert(pick(8, 0, false)==0x80);
    assert(pick(4, 0, true)==0xc0);
    assert(pick(6, 0, false)==0);
    assert(pick(8, 4, true)==0xc000);
    assert(pick(8, 16, true)==0xc000);
    assert(pick(4, 4, false)==8);
    assert(pick(2, 8, true)==0);
    assert(pick(2, 4, true)==0);
    assert(pick(3, 8, true)==0);
    // Ultra 9 275HX: P cores can be interleaved, not necessarily LP 0..7.
    const uint64_t masks[]={1,2,4,8,16,32,64,128,256,512,1024,2048};
    const unsigned char cls[]={1,1,0,0,0,0,0,0,0,0,1,1};
    assert(pick_reserved_core(masks,cls,12)==2048);
    assert(pick_reserved_core(nullptr,nullptr,0)==0);
}
''')

    def test_replay_pin_restores_affinity_nested_async_optout_and_failure(self):
        s = (ROOT / "gpu/vk/vk_replay.cpp").read_text()
        a=s.index("thread_local int replay_pin_depth = 0;")
        b=s.index("/// A submission's command buffers", a)
        self.run_cpp(r'''
#include <cstdint>
#include <cassert>
using DWORD_PTR=uintptr_t;
bool async=false, fail=false; uint64_t mask=8;
int calls=0; DWORD_PTR current=0xff;
bool async_on() { return async; }
uint64_t replay_pin_mask() { return mask; }
int GetCurrentThread() { return 1; }
DWORD_PTR SetThreadAffinityMask(int, DWORD_PTR m) {
    ++calls; if(fail) return 0; auto old=current; current=m; return old;
}
''' + s[a:b] + r'''
int main() {
    { ReplayPin a; assert(current==8 && calls==1); {ReplayPin b; assert(calls==1);} assert(current==8); }
    assert(current==0xff && calls==2 && replay_pin_depth==0);
    async=true; {ReplayPin a;} assert(calls==2); async=false;
    mask=0; {ReplayPin a;} assert(calls==2);
    mask=8; fail=true; {ReplayPin a;} assert(calls==3 && current==0xff && replay_pin_depth==0);
}
''')

    def test_gpu_profile_toggle_keeps_stamp_but_gp_test_and_driver_do_not(self):
        s = (ROOT / "gpu/vk/vk_shader.cpp").read_text()
        self.run_cpp(r'''
#include <cstdint>
#include <cstring>
#include <cassert>
#include <initializer_list>
#define HOOKSHOT_SHADER_STAMP 0x123456789abcdef0ull
char** _environ;
struct {struct {uint32_t vendorID=0x10de,deviceID=1,driverVersion=1;} props;
 int driver_id=1; uint32_t subgroup_size=32,subgroup_max=32; int sg32_stages=1;} dev;
namespace Shader::Backend::SPIRV { bool mma_software=false; }
int depth() {return 1;} struct {int (*depth_minus_w)();} api{depth}; auto*host=&api;
''' + function(s, "uint64_t disk_stamp()") + r'''
int main() {
    char base[]="RX_VK_NATIVE=1", on[]="RX_VK_GPU_PROFILE=1", off[]="RX_VK_GPU_PROFILE=0";
    char gp[]="RX_VK_GP_TEST=1", gp2[]="RX_VK_GP_TEST=2";
    char *a[]={base,nullptr}, *b[]={base,on,nullptr}, *c[]={base,off,nullptr};
    _environ=a; auto normal=disk_stamp(); _environ=b;assert(disk_stamp()==normal);
    _environ=c;assert(disk_stamp()==normal);
    char *d[]={base,gp,nullptr}, *e[]={base,gp2,nullptr};
    _environ=d;auto changed=disk_stamp();assert(changed!=normal);
    _environ=e;assert(disk_stamp()!=changed);
    _environ=a;dev.props.driverVersion++;assert(disk_stamp()!=normal);
}
''')

    def test_detailed_timers_avoid_counter_reads_but_coarse_timers_stay_exact(self):
        s = (ROOT / "gpu/vk/vk_internal.h").read_text()
        block = s[s.index("struct ProfScope {"):s.index("} // namespace mkwvk", s.index("struct ProfScope {"))]
        self.run_cpp(r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
int reads=0; int64_t prof_ns[2]{};
int64_t prof_now() { return ++reads*100; }
''' + block + r'''
int main(int argc, char** argv) {
    if(argc>1) setenv(argv[1], argv[2], 1);
    const bool detailed=argc>1 && strcmp(argv[2],"0");
    for(int i=0;i<1000;i++) { ProfScope p(1,prof_details_on()); }
    assert(reads==(detailed?2000:0));
    assert(prof_ns[1]==(detailed?100000:0));
    {ProfScope p(0);} assert(prof_ns[0]==100);
    assert(reads==(detailed?2002:2));
}
''', ((), ("RX_VK_PROF_ALL","1"), ("RX_VK_PROF_ALL","0"), ("RX_VK_SLOW_LOG","40")))

    def test_target_pool_exact_keys_capacity_idle_and_pressure_retirement(self):
        s=(ROOT / "gpu/vk/vk_texture.cpp").read_text()
        a=s.index("struct PooledTarget {"); b=s.index("// ---- the recording's upload",a)
        self.run_cpp(r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <array>
#include <algorithm>
#include <map>
#include <mutex>
#include <unordered_map>
#include <vector>
using VkImage=uint64_t; using VmaAllocation=uint64_t; using VkImageView=uint64_t;
using TargetImageKey=std::array<uint32_t,11>;
struct VkImageCreateInfo {uint32_t flags=0,imageType=1,format=37; struct {uint32_t width=32,height=32,depth=1;} extent;
 uint32_t mipLevels=1,arrayLayers=1,samples=1,tiling=0,usage=3;};
struct Texture {VkImage image=0;VmaAllocation allocation=0;std::unordered_map<uint64_t,VkImageView> views;};
struct Dead {bool pool_eligible=true; VkImage image=1;VmaAllocation allocation=2;TargetImageKey pool_key{};
 std::unordered_map<uint64_t,VkImageView> view_map;uint64_t bytes=0;};
struct {int device=0;} dev; uint64_t frame_no=1; int images_freed=0,views_freed=0;
void vkDestroyImageView(int,uint64_t,const void*) {++views_freed;}
void destroy_image(uint64_t,uint64_t) {++images_freed;}
''' + s[a:b] + r'''
int main() {
    setenv("RX_VK_TARGET_POOL_MB","1",1); constexpr uint64_t M=1ull<<20;
    setenv("RX_VK_TARGET_POOL_PRESSED_MB","0",1);   // (0.4.5-test.4: pressed, nothing kept, as before)
    VkImageCreateInfo ci; auto k=target_key(ci);
    ci.extent.width++;assert(target_key(ci)!=k); ci.extent.width--;
    ci.usage++;assert(target_key(ci)!=k);ci.usage--;
    ci.samples++;assert(target_key(ci)!=k);ci.samples--;
    Dead d;d.pool_key=k;d.bytes=M/2;d.view_map[3]=9;
    assert(target_put(d) && d.view_map.empty());
    assert(target_pool_bytes==M/2 && target_pool_count==1);
    Texture t; auto wrong=k;wrong[3]++;
    assert(!target_take(wrong,t));assert(target_take(k,t));
    assert(t.image==1 && t.views.at(3)==9 && target_pool_bytes==0 && target_pool_count==0);
    assert(!target_take(k,t));
    d.view_map=t.views;assert(target_put(d));d.image=2;assert(target_put(d));
    assert(target_pool_bytes==M && !target_put(d));
    target_trim();assert(images_freed==0);frame_no+=121;target_trim();
    assert(images_freed==2 && views_freed==1 && target_pool_count==0);
    d.bytes=1;for(int i=0;i<70;i++) assert(target_put(d));
    target_pool_pressed=true;assert(!target_put(d)); target_trim();
    assert(target_pool_count==6 && images_freed==66);
    target_trim(); assert(target_pool_bytes==0 && target_pool_count==0 && images_freed==72);
    d.bytes=M+1;target_pool_pressed=false;assert(!target_put(d));
    d.bytes=1;d.pool_eligible=false;assert(!target_put(d));
}
''')


if __name__ == "__main__":
    unittest.main()
