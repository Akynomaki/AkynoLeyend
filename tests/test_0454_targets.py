"""0.4.5-test.4: the game's render targets reused under VRAM pressure, and the recording thread's waits named.

The target pool is compiled here from gpu/vk/vk_texture.cpp with stand-ins for Vulkan (as test_upstream_2013_043 does);
the sampler and the summary are read from the sources and run on a made-up log. No game: none of this says how many targets
a session reuses or what the frame waits for.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


def target_pool_program():
    """The pool's code between its markers, with stand-ins, and checks of the pressed policy."""
    s = source("gpu/vk/vk_texture.cpp")
    a = s.index("struct PooledTarget {")
    b = s.index("// ---- the recording's upload", a)
    return r'''
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
    constexpr uint64_t M=1ull<<20;
    // (defaults: 256 MB, 64 MB pressed)
    VkImageCreateInfo ci; auto k=target_key(ci);
    Dead d; d.pool_key=k; d.bytes=M;
    target_pool_pressed=true;
    assert(target_pool_cap_now()==64*M);
    assert(target_put(d));                                   // pressed: kept now (before: refused)
    Texture t; assert(target_take(k,t) && target_pool_reused==1 && target_pool_count==0);
    for (int i=0;i<64;i++) assert(target_put(d));
    assert(target_pool_bytes==64*M && !target_put(d));     // the pressed cap
    target_trim(); assert(images_freed==0);                 // young: kept
    frame_no+=9; target_trim(); assert(images_freed==64 && target_pool_count==0);   // 8 frames, then gone
    // filled while not pressed, then pressed: over the pressed cap goes whatever its age
    target_pool_pressed=false; d.bytes=2*M;
    for (int i=0;i<40;i++) assert(target_put(d));
    assert(target_pool_bytes==80*M);
    target_pool_pressed=true; target_trim();
    assert(target_pool_bytes<=64*M && target_pool_count==32 && images_freed==72);
    target_trim(); assert(target_pool_count==32);           // under the cap and young: kept
    // not pressed: 120 frames as before
    target_pool_pressed=false; frame_no+=100; target_trim(); assert(target_pool_count==32);
    frame_no+=21; target_trim(); target_trim(); assert(target_pool_count==0);
    return 0;
}
'''


def compile_and_run(program, compiler, extra=(), env=None):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path / "check.cpp").write_text(program)
        binary = path / ("check.exe" if os.name == "nt" else "check")
        built = subprocess.run([compiler, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", *extra,
                                str(path / "check.cpp"), "-o", str(binary)], capture_output=True, text=True, timeout=180)
        if built.returncode:
            return built.returncode, built.stderr
        run = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=30)
        return run.returncode, run.stdout + run.stderr


class TargetsUnderPressure(unittest.TestCase):
    def test_pressed_pool_keeps_64_mb_for_8_frames(self):
        compiler = shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("HOS_", "RX_", "AKYNO_"))}
        code, out = compile_and_run(target_pool_program(), compiler, ("-fsanitize=undefined", "-fno-sanitize-recover=all"), env)
        self.assertEqual(code, 0, out)

    def test_the_old_policy_stays_one_variable_away(self):
        text = source("gpu/vk/vk_texture.cpp")
        self.assertIn('getenv("RX_VK_TARGET_POOL_PRESSED_MB")', text)
        self.assertIn("const uint64_t cap = target_pool_cap_now();", text)
        self.assertNotIn("target_pool_pressed || !cap", text)
        self.assertIn('setenv("RX_VK_TARGET_POOL_PRESSED_MB","0",1)', source("tests/test_upstream_2013_043.py"))
        from akynoleyend.environment import EXPERIMENTS
        self.assertEqual(EXPERIMENTS["alvos-como-antes"], {"RX_VK_TARGET_POOL_PRESSED_MB": "0"})
        # (0.4.6: the launcher's Teste de desempenho is gone, test_046_final)


class Waits(unittest.TestCase):
    def test_the_sampler_takes_several_threads_and_keeps_the_chain(self):
        text = source("host/mkw_glue.c")
        self.assertIn("prof-sample %s (%u samples) [%s]:", text)
        self.assertIn('"chain"', text)
        self.assertIn("CHAIN_DEPTH", text)
        from akynoleyend.environment import EXPERIMENTS
        self.assertEqual(EXPERIMENTS["amostrar"], {"HOS_SAMPLE": "Presentation Thread|sead::MainThread"})

    def test_summary_splits_threads_and_ranks_chains(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import resumo_medicao
        with tempfile.TemporaryDirectory(prefix="esperas-") as tmp:
            folder = Path(tmp)
            (folder / "erros.log").write_text("\n".join([
                "[hos host] prof-sample leaf (1000 samples) [Presentation Thread]: ntdll.dll+163cb4 600, AkynoLeyend.dll+1a00 300,",
                "[hos host] prof-sample ours (1000 samples) [Presentation Thread]: AkynoLeyend.exe+400 600,",
                "[hos host] prof-sample chain (1000 samples) [Presentation Thread]: AkynoLeyend.exe+400<+500<+600 550, AkynoLeyend.exe+400<+700 50,",
                "[hos host] prof-sample leaf (1000 samples) [sead::MainThread]: ntdll.dll+163cb4 900,",
                "[hos host] prof-sample chain (1000 samples) [sead::MainThread]: AkynoLeyend.exe+400<+800 900,",
                "[hos host] prof-sample leaf (500 samples): ntdll.dll+163cb4 500,",
                "[hos Presentation Thread] vk: target pool: 120 reused, 30 new, 100 retired; 4 images (12 MB)",
            ]) + "\n", encoding="utf-8")
            r = resumo_medicao.summarize(folder, symbols=False)
        pres = r["samples"]["Presentation Thread"]
        self.assertEqual(pres["leaf"]["samples"], 1500)      # (a line without a thread: the first thread's, as before)
        self.assertEqual(pres["chain"]["top"][0], ("AkynoLeyend.exe+400<+500<+600", 550, 55.0))
        self.assertEqual(r["samples"]["sead::MainThread"]["chain"]["top"][0][1], 900)
        self.assertEqual(r["targets"], {"reused": 120, "new": 30, "retired": 100})
        text = resumo_medicao.report(r)
        self.assertIn("Amostras de Presentation Thread (onde estava), 1500 no total:", text)
        self.assertIn("Alvos de render: 120 reaproveitados, 30 novos", text)

    def test_report_survives_a_non_utf8_console(self):
        text = source("tools/resumo_medicao.py")
        self.assertIn('reconfigure(encoding="utf-8"', text)


class Version(unittest.TestCase):
    def test_test_3_installs_update_in_place(self):
        from akynoleyend import __version__
        from akynoleyend.coherence import PREVIOUS_HOST_SOURCES
        self.assertIn("0.4.5-test.3", PREVIOUS_HOST_SOURCES)   # (0.4.5-test.5: the version itself in test_0455_waits)
        self.assertIn('"0.4.5-test.3"', source("builder/AkynoLeyendUpdater/Core.cs"))


if __name__ == "__main__":
    unittest.main()
