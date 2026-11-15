"""Execute production output/pool patches and host helpers against synthetic memory."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import oot_output_size as output
import oot_patches as fixed


def function(source, marker):
    start = source.index(marker)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class NativeGraphicsTests(unittest.TestCase):
    def execute(self, source):
        compiler = shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "check.cpp").write_text(source)
            binary = path / "check"
            built = subprocess.run([compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-label",
                                    str(path / "check.cpp"), "-o", str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stderr)
            env = {k: v for k, v in os.environ.items() if not k.startswith(("HOS_", "RX_"))}
            result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_output_and_all_heap_layers_scale_together(self):
        fragments = '#include "a64.h"\n' + "\n".join("void site_%d(Ctx *c){\n%s}\n" % (i, old)
                                                                        for i, (old, _) in enumerate(output.OUT_EDITS))
        fragments += output.DISPLAY_SETTINGS + "\n"
        for i, (old, _) in enumerate(output.DISPLAY_EDITS):
            fragments += old + "\n    c->x[%d] = c->x[8];\n" % (i + 10)
        fragments += "}\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "code_000.c"
            path.write_text(fragments)
            output.apply(directory)
            result = path.read_text()
            output.apply(directory)
            self.assertEqual(result, path.read_text(), "second pass changed already patched code")
            path.write_text(result.replace(output.SIZE_CHANGED, "hos_output_size(0) != 2560"))
            output.apply(directory)
            self.assertEqual(result, path.read_text(), "existing r8 output sites were not upgraded")
            self.assertTrue(output.extended_output_emitted(directory))
        host = (ROOT / "host/nn_applet.c").read_text()
        helpers = function(host, "uint32_t hos_output_size(") + function(host, "uint64_t hos_rt_pool_size(")
        fixture = r'''#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
struct Ctx {uint64_t x[32]{};}; int mode=0;
#define A64_NOESC
int hos_output_mode(){return mode;}
void hos_log(const char*,...){}
uint32_t recomp_load32(Ctx*,uint64_t p){uint32_t v;memcpy(&v,(void*)(uintptr_t)p,4);return v;}
uint64_t recomp_load64(Ctx*,uint64_t p){uint64_t v;memcpy(&v,(void*)(uintptr_t)p,8);return v;}
void recomp_store32(Ctx*,uint64_t p,uint64_t v){uint32_t n=v;memcpy((void*)(uintptr_t)p,&n,4);}
void recomp_store64(Ctx*,uint64_t p,uint64_t v){memcpy((void*)(uintptr_t)p,&v,8);}
void recomp_ldp32(Ctx*c,uint64_t p,uint64_t*a,uint64_t*b){*a=recomp_load32(c,p);*b=recomp_load32(c,p+4);}
uint32_t base_size[2]{1920,1080}; uint64_t called,usage;
void f_831cca50(Ctx*c){c->x[0]=(uintptr_t)base_size;}
void f_809df710(Ctx*c){called=c->x[0];}
void f_809df700(Ctx*c){called=c->x[0];}
void fake_call(Ctx*c){c->x[0]=usage;}
#define A64_ICALL(c,t) ((void)(t),fake_call(c))
'''
        result = result.replace('#include "a64.h"', fixture + helpers)
        result += r'''
int main(){alignas(8) unsigned char memory[8192]{};alignas(8) unsigned char config[64]{};
const unsigned sizes[][2]={{2560,1440},{2560,1440},{3840,2160},{1920,1080},{1280,720},{2560,1600}};
for(mode=0;mode<6;++mode){Ctx c;unsigned w=sizes[mode][0],h=sizes[mode][1];
assert(hos_output_size(0)==w&&hos_output_size(1)==h);
uint64_t pool=hos_rt_pool_size(0x13100000ULL),growth=pool-0x13100000ULL;
assert(pool==(mode==2?0x2af00000ULL:mode==5?0x15300000ULL:0x13100000ULL));
c.x[21]=(uintptr_t)memory;site_0(&c);assert(recomp_load64(&c,(uintptr_t)memory+20)==(uint64_t(w)|(uint64_t(h)<<32)));
recomp_store32(&c,(uintptr_t)config+8,2560);recomp_store32(&c,(uintptr_t)config+12,1440);
c.x[0]=(uintptr_t)memory;c.x[1]=(uintptr_t)config;site_1(&c);assert(recomp_load32(&c,(uintptr_t)config+8)==w);
assert(recomp_load32(&c,(uintptr_t)config+12)==h);
site_2(&c);assert(c.x[24]==w*3/4&&c.x[25]==h*3/4);
c.x[19]=(uintptr_t)memory;site_3(&c);float expected=float(w*3/4);uint32_t bits;memcpy(&bits,&expected,4);
assert(recomp_load32(&c,(uintptr_t)memory+3668)==bits);expected=float(h*3/4);memcpy(&bits,&expected,4);assert(c.x[8]==bits);
recomp_store64(&c,(uintptr_t)memory+1464,0x13100000ULL);site_4(&c);assert(recomp_load64(&c,(uintptr_t)memory+1464)==pool);
c.x[0]=0x34900000ULL;site_5(&c);assert(called==0x34900000ULL+growth);
c.x[21]=(uintptr_t)memory;c.x[22]=0;recomp_store64(&c,(uintptr_t)memory,0x34900000ULL);
usage=0x34900000ULL+growth-0x100;site_6(&c);assert(c.x[0]==0x34900000ULL-0x100);
c.x[0]=0x1b6cb48ULL+growth;site_7(&c);assert(called==0x1b6cb48ULL);
f_83213890(&c);assert(c.x[10]==(uint64_t(w)|(uint64_t(h)<<32)));
assert(c.x[11]==(uint64_t(w*3/4)|(uint64_t(h*3/4)<<32)));
}return 0;}
'''
        self.execute(result)

    def test_display_guards_are_scoped_to_the_display_settings_initializer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "code_001.c"
            header = '#include "a64.h"\n'
            base = header + "\n".join(new for _, new in output.OUT_EDITS) + "\n"
            old = [text for text, _ in output.DISPLAY_EDITS]
            unrelated = "void other(Ctx *c) {\n" + "\n".join(old) + "\n}\n"
            path.write_text(base + unrelated, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "guards incomplete"):
                output.plan(directory, legacy_only=True)
            path.write_text(base + unrelated + output.DISPLAY_SETTINGS + "\n" + "\n".join(old) + "\n}\n",
                            encoding="utf-8")
            output.apply(directory)
            patched = path.read_text(encoding="utf-8")
            self.assertIn(unrelated, patched)
            self.assertIn("/* display settings: output */", patched)
            self.assertIn("/* display settings: scaler reference */", patched)
            self.assertFalse(output.plan(directory, legacy_only=True))

    def test_missing_output_site_leaves_every_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for i, (old, _) in enumerate(output.OUT_EDITS[:-1]):
                path = Path(directory) / ("code_%03d.c" % i)
                path.write_text('#include "a64.h"\n' + old)
                paths.append(path)
            old = [p.read_bytes() for p in paths]
            with self.assertRaisesRegex(ValueError, "guards incomplete"):
                output.apply(directory)
            self.assertEqual(old, [p.read_bytes() for p in paths])

    def test_ready_frames_are_not_quantized_in_real_time(self):
        body = function((ROOT / "host/nn_vi.c").read_text(), "int hos_vi_native_interval(")
        self.execute('''#include <cassert>\n#include <cstdlib>\nstruct Ctx{};
int present_interval=1,realtime=1;int rx_option(int,int){return realtime;}
''' + body + '''
int main(){Ctx c;for(int n=1;n<=4;++n){assert(hos_vi_native_interval(&c,n)==n);assert(present_interval==1);}
realtime=0;hos_vi_native_interval(&c,3);assert(present_interval==3);return 0;}
''')

    def test_fsr_and_output_modes_reach_the_cli(self):
        from akynoleyend.graphics import graphics_environment
        from akynoleyend.cli import parser
        for choice, mode in (("native-1440", "1"), ("native-4k", "2")):
            env = graphics_environment(resolution=choice, upscaling="fsr")
            self.assertEqual(env["HOS_OUTPUT_RES"], mode)
            self.assertEqual(env["RX_VK_UPSCALE"], "3")
            self.assertEqual(env["HOS_DYNRES"], "0")
            self.assertEqual(env["HOS_RES_SCALE"], "1.0")
            parsed = parser().parse_args(["run", "--resolution", choice, "--upscaling", "fsr"])
            self.assertEqual(parsed.resolution, choice)

    def test_generated_pointer_tables_are_inside_uniform_binding(self):
        source = (ROOT / "gpu/vk/vk_draw.cpp").read_text()
        start = source.index("uint32_t used =", source.index("VkDescriptorBufferInfo uniform_range("))
        end = source.index("if (index == 0 || index == 2)", start)
        body = source[start:end]
        start = source.index("const uint32_t n =", end)
        body += source[start:source.index(";", start)+1]
        self.execute('''#include <algorithm>\n#include <array>\n#include <vector>\n#include <cassert>\n#include <cstdint>
struct Desc{uint32_t cbuf_index,cbuf_offset,count;};
namespace Shader {struct Info {static constexpr uint32_t MAX_CBUFS=18;bool uses_global_memory=false;
std::array<uint32_t,18> constant_buffer_used_sizes{};std::vector<Desc> storage_buffers_descriptors;};}
struct Stage{Shader::Info info;};uint32_t extent(const Stage&st,uint32_t index){
''' + body + '''return n;}
int main(){for(uint32_t prior:{0x690u,0x6a0u,0x780u,0x790u}){Stage s;s.info.uses_global_memory=true;
s.info.constant_buffer_used_sizes[0]=prior;s.info.storage_buffers_descriptors={{0,0x880,3}};
assert(extent(s,0)==0x8b0);s.info.uses_global_memory=false;assert(extent(s,0)==prior);}
Stage s;s.info.uses_global_memory=true;s.info.storage_buffers_descriptors={{0,0x880,3},{2,0x20,1},{4,0xe0,16}};
assert(extent(s,2)==0x30);assert(extent(s,4)==0x1e0);assert(extent(s,99)==16);
s.info.constant_buffer_used_sizes[0]=0xa00;assert(extent(s,0)==0xa00);return 0;}
''')

    def test_cached_scale_refreshes_only_when_needed(self):
        fragment = '#include "a64.h"\nvoid update(Ctx*c){\ngoto L_831f3efc;\n' + fixed.APPLY_OLD
        fragment += '\nmarked=c->x[8];\ngoto L_831f3f08;\n' + fixed.FLAGS_OLD + '}\n'
        patched, count = fixed.fixed_scale(fragment)
        self.assertEqual(count, 1)
        self.assertEqual(fixed.fixed_scale(patched), (patched, 0))
        prefix = '''#include <cstdint>\n#include <cstring>\n#include <cassert>
struct Ctx{uint64_t x[32]{};};uint64_t marked;
volatile int hos_fixed_resolution=1;volatile uint64_t hos_res_module=0;volatile uint32_t hos_fixed_scale_bits;
uint32_t recomp_load32(Ctx*,uint64_t p){uint32_t v;memcpy(&v,(void*)(uintptr_t)p,4);return v;}
uint64_t recomp_load64(Ctx*,uint64_t p){uint64_t v;memcpy(&v,(void*)(uintptr_t)p,8);return v;}
'''
        patched = patched.replace('#include "a64.h"', prefix)
        patched += '''int main(){alignas(8) unsigned char memory[4096]{};Ctx c;c.x[20]=(uintptr_t)memory;
auto put=[&](int off,float v){memcpy(memory+off,&v,4);};float want=1.5f;uint32_t u;memcpy(&u,&want,4);hos_fixed_scale_bits=u;
put(3664,2560);put(3672,2560);put(3676,0.75f);uint64_t flags=0x18;memcpy(memory+3616,&flags,8);
c.x[8]=1;update(&c);assert(marked==9);assert(c.x[8]==0);assert(hos_res_module==(uintptr_t)memory);
put(3676,1.5f);c.x[8]=1;update(&c);assert(marked==1);
hos_fixed_resolution=0;c.x[8]=1;update(&c);assert(marked==1);assert(c.x[8]==0x18);return 0;}
'''
        self.execute(patched)


if __name__ == "__main__":
    unittest.main()
