"""Game-free regressions of the real binding, capture, asset cache and write-back code."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import sys
import io
from unittest.mock import patch

from akynoleyend import prompts

ROOT = Path(__file__).resolve().parents[1]


def function(source, marker):
    start = source.index(marker)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class ControlsNative(unittest.TestCase):
    def compile_run(self, text, args=()):
        cc = shutil.which("c++")
        if not cc:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as d:
            src, exe = Path(d)/"test.cpp", Path(d)/"test"
            src.write_text(text)
            built = subprocess.run([cc, "-std=c++20", "-O1", "-D_Static_assert=static_assert", "-I"+str(ROOT),
                                    str(src), "-o", str(exe)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(exe), *args], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout+run.stderr)

    def test_actual_bindings_presets_duplicate_keys_and_capture_edges(self):
        source = (ROOT/"host/control_bindings.c").read_text()
        # Keep every production function. Only replace Windows OS/CRT calls for this fixture.
        source = "\n".join(x for x in source.splitlines() if not x.startswith("#include") and not x.startswith("#define fopen"))
        fixture = r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include "gpu/vk/control_editor.h"
using LONG=long;using DWORD=unsigned long;
LONG InterlockedExchange(volatile LONG*p,LONG v){LONG old=*p;*p=v;return old;}
LONG InterlockedCompareExchange(volatile LONG*p,LONG v,LONG old){LONG got=*p;if(got==old)*p=v;return got;}
void Sleep(int){} void hos_log(const char*,...){}
DWORD hos_game_path_a(char*,DWORD){return 0;}
#define HOS_FS_PATH_CAP 4096
#define VK_SHIFT 16
#define VK_SPACE 32
#define VK_LBUTTON 1
#define VK_RBUTTON 2
#define VK_CONTROL 17
#define VK_TAB 9
#define VK_RETURN 13
#define VK_UP 38
#define VK_DOWN 40
#define VK_LEFT 37
#define VK_RIGHT 39
'''+source+r'''
int main(){
 using namespace mkwvk::controls;
 MkwVkHost h{};h.binding=hos_binding;h.bind=hos_bind;
 for(int i=0;i<HOS_SW_N;++i){assert(hos_binding(HOS_BIND_PAD,i,0)==nintendo[i]);assert(hos_map_pad(1ull<<nintendo[i])==(1ull<<i));}
 assert(hos_binding(HOS_BIND_KEY,HOS_SW_Y,0)==1);
 Editor e;e.refresh(&h);assert(e.layout==0);
 int key=hos_binding(HOS_BIND_KEY,HOS_SW_A,0);
 e.preset(&h,1);assert(e.layout==1&&hos_map_pad(1ull<<HOS_PAD_SOUTH)==1);
 assert(hos_binding(HOS_BIND_KEY,HOS_SW_A,0)==key);
 e.action=HOS_SW_R;e.bind(&h,HOS_BIND_PAD,0,HOS_PAD_RSTICK);
 assert(e.layout==2&&hos_map_pad(1ull<<HOS_PAD_RSTICK)==(1ull<<HOS_SW_R));
 assert(hos_binding(HOS_BIND_PAD,HOS_SW_RS,0)==HOS_PAD_RSHOULDER);
 e.bind(&h,HOS_BIND_KEY,1,'W');
 assert(hos_binding(HOS_BIND_KEY,HOS_KEY_MOVE_UP,0)==0);
 assert(hos_binding(HOS_BIND_KEY,HOS_SW_R,1)=='W');
 hos_bind(HOS_BIND_PAD,HOS_SW_R,0,999);assert(hos_binding(HOS_BIND_PAD,HOS_SW_R,0)==HOS_PAD_RSTICK);
 e.preset(&h,0);assert(e.layout==0);
 bool keys[256]{};keys[13]=true;Capture c;int code=999;
 c.begin(HOS_BIND_KEY,1,keys,1);assert(c.poll(keys,1,true,code)==0);
 keys[13]=false;assert(c.poll(keys,0,true,code)==0);
 keys['R']=true;assert(c.poll(keys,0,true,code)==1&&code=='R'&&!c.active);
 c.begin(HOS_BIND_PAD,0,keys,1);assert(c.poll(keys,1,true,code)==0);
 assert(c.poll(keys,0,true,code)==0);assert(c.poll(keys,8,true,code)==1&&code==3);
 c.begin(HOS_BIND_PAD,0,keys,0);assert(c.poll(keys,0,false,code)==-1);
 c.begin(HOS_BIND_KEY,0,keys,0);keys[27]=true;assert(c.poll(keys,0,true,code)==-1);keys[27]=false;
 c.begin(HOS_BIND_PAD,0,keys,0);keys[46]=true;assert(c.poll(keys,0,true,code)==1&&code==-1);
}
'''
        self.compile_run(fixture)

    def test_auto_face_respects_manual_choice_and_actual_device_name(self):
        self.compile_run(r'''
#include <cassert>
#include "gpu/vk/vk_api.h"
#include "host/prompt_face.h"
int main(){
 assert(prompt_face_for(0,"DualSense Wireless Controller",1)==HOS_PROMPT_PS5);
 assert(prompt_face_for(0,"DUALSHOCK 4",1)==HOS_PROMPT_PS4);
 assert(prompt_face_for(0,"Steam Deck",0)==HOS_PROMPT_STEAMDECK);
 assert(prompt_face_for(0,"Nintendo Switch Pro Controller",1)==HOS_PROMPT_SWITCH);
 assert(prompt_face_for(0,"",1)==HOS_PROMPT_XBOX);
 assert(prompt_face_for(0,"",0)==HOS_PROMPT_SWITCH);
 assert(prompt_face_for(2,"DualSense",0)==HOS_PROMPT_XBOX);
}
''')

    def test_writeback_chunks_cover_runs_without_overrun_or_reordering(self):
        self.compile_run(r'''
#include <cassert>
#include <vector>
#include "gpu/vk/wb_diff_split.h"
int main(){
 for(uint64_t at=0;at<68;at+=4)for(uint64_t n=4;n<=262172;n=n<128?n+4:n+1024){
  uint64_t next=at,total=0;
  mkwvk::wbd_split(at,n,[&](uint64_t a,uint64_t size,bool vectors){
   assert(a==next&&size&&size%4==0&&a+size<=at+n);
   if(vectors)assert(a%16==0&&size%16==0&&size<=65536);
   next+=size;total+=size;
  });assert(next==at+n&&total==n);
 }
}
''')

    def test_actual_writeback_dirty_queue_invalidates_bounded_ranges_and_handles_overflow(self):
        source=(ROOT/"gpu/vk/vk_memory.cpp").read_text()
        fixture=r'''
#include <cassert>
#include <cstdint>
#include <mutex>
#include <vector>
constexpr unsigned kPageShift=12;
std::mutex shadow_written_mu;std::vector<uint32_t> shadow_written_pages,shadow_written_collected_list,shadow_written_by_replay;
bool shadow_written_all=false,enabled=false;
bool wb_diff_on(){return enabled;}
'''
        # (the three lists of Hookshot 2.1.0's reports: the captures', the collection's and the replay's own writes)
        fixture+=function(source,'void shadow_written_to(std::vector<uint32_t>& list, const uint32_t* pages, int64_t n) {')
        fixture+=function(source,'void shadow_written(const uint32_t* pages, int64_t n) {')
        fixture+=function(source,'void shadow_written_range(uint64_t guest, uint64_t size) {')
        fixture+=r'''
int main(){
 uint32_t p[]={3,8};shadow_written(p,2);assert(shadow_written_pages.empty());
 enabled=true;shadow_written(p,2);assert(shadow_written_pages==std::vector<uint32_t>({3,8}));
 shadow_written_range(4095,2);assert(shadow_written_pages==std::vector<uint32_t>({3,8,0,1}));
 shadow_written_range(UINT64_MAX-1,5);shadow_written_range(0,0);assert(shadow_written_pages.size()==4);
 shadow_written(p,(8u<<20)+1);assert(shadow_written_all&&shadow_written_pages.empty());
 shadow_written(p,2);assert(shadow_written_pages.empty());
 shadow_written_all=false;shadow_written_range(0,(uint64_t(8u<<20)+1)*4096);
 assert(shadow_written_all&&shadow_written_pages.empty());
}
'''
        self.compile_run(fixture)

    def test_actual_cmap_parser_rejects_short_buffers(self):
        source = (ROOT/"host/prompts.c").read_text()
        fixture = '#include <cassert>\n#include <cstdint>\n#include <cstddef>\n#include "gpu/vk/vk_api.h"\n#define PAD_BASE 0xF700\n'
        fixture += 'int hos_binding(int,int,int){return 0;}\n'
        fixture += re.search(r"static const uint16_t switch_code\[HOS_SW_N\] = \{[^}]*\};", source).group(0)
        for marker in ('static unsigned rd16(', 'static void wr16(', 'static unsigned cmap4_glyph(', 'static int cmap4_bind('):
            fixture += function(source, marker)
        fixture += 'int main(){uint8_t b[16]{};for(size_t n=0;n<16;++n){assert(!cmap4_glyph(b,n,0));assert(!cmap4_bind(b,n));}}'
        self.compile_run(fixture)

    def test_actual_font_binding_maps_custom_r3_and_preserves_other_glyphs(self):
        sys.path.insert(0,str(ROOT/"nx2"))
        self.addCleanup(lambda:sys.path.remove(str(ROOT/"nx2")))
        import prompt_assets as assets
        mapping={code:100+i for i,code in enumerate(assets.SWITCH)}
        mapping.update({assets.PAD_BASE+i:200+i for i in range(len(assets.PADS))})
        data=assets.cmap4(mapping,set(assets.SWITCH))[20:]
        source=(ROOT/"host/prompts.c").read_text()
        fixture=r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
#include "gpu/vk/vk_api.h"
#define PAD_BASE 0xF700
int hos_binding(int,int button,int){return button==HOS_SW_A?HOS_PAD_RSTICK:button==HOS_SW_Y?HOS_PAD_SOUTH:-1;}
'''
        fixture+=re.search(r"static const uint16_t switch_code\[HOS_SW_N\] = \{[^}]*\};",source).group(0)
        for marker in ('static unsigned rd16(', 'static void wr16(', 'static unsigned cmap4_glyph(', 'static int cmap4_bind('):
            fixture+=function(source,marker)
        fixture+='int main(){uint8_t b[]={'+','.join(map(str,data))+'};'
        fixture+='assert(cmap4_bind(b,sizeof b)==2);'
        for i,code in enumerate(assets.SWITCH):
            expected=208 if i==0 else 200 if i==3 else 100+i
            fixture+=f'assert(cmap4_glyph(b,sizeof b,{code})=={expected});'
        for i in range(len(assets.PADS)):
            fixture+=f'assert(cmap4_glyph(b,sizeof b,{assets.PAD_BASE+i})=={200+i});'
        self.compile_run(fixture+'}')

    def test_all_five_fonts_are_generated_from_fixture_and_preserve_normal_text(self):
        try:
            from fontTools.fontBuilder import FontBuilder
            from fontTools.pens.t2CharStringPen import T2CharStringPen
            from fontTools.ttLib import TTFont
        except ImportError:
            self.skipTest("fontTools unavailable; production launcher reports the missing dependency")
        sys.path.insert(0,str(ROOT/"nx2"))
        self.addCleanup(lambda:sys.path.remove(str(ROOT/"nx2")))
        import prompt_assets as assets
        codes = sorted(set(assets.SWITCH_ICON.values()) | set(assets.STATIC) | {65})
        mapping = {c:f"g{c}" for c in codes}
        order=[".notdef",*mapping.values()]
        builder=FontBuilder(1000,isTTF=False)
        builder.setupGlyphOrder(order)
        builder.setupCharacterMap(mapping)
        builder.setupHorizontalMetrics({g:(700,0) for g in order})
        builder.setupHorizontalHeader(ascent=900,descent=-100)
        builder.setupNameTable({"familyName":"Synthetic", "styleName":"Regular"})
        builder.setupOS2(sTypoAscender=900,sTypoDescender=-100,usWinAscent=900,usWinDescent=100)
        builder.setupPost()
        chars={}
        for g in order:
            pen=T2CharStringPen(700,None)
            pen.moveTo((50,0));pen.lineTo((650,0));pen.lineTo((650,600));pen.lineTo((50,600));pen.closePath()
            chars[g]=pen.getCharString()
        builder.setupCFF("Synthetic",{},chars,{})
        out=io.BytesIO();builder.font.save(out)
        for face in prompts.FACES:
            font=TTFont(io.BytesIO(assets.face_font(out.getvalue(),face)))
            cmap=font.getBestCmap()
            self.assertEqual(cmap[65],mapping[65])
            self.assertEqual(len({cmap[assets.PAD_BASE+i] for i in range(len(assets.PADS))}),len(assets.PADS))
            for code,pad in zip(assets.SWITCH,assets.DEFAULT):
                self.assertEqual(cmap[code],cmap[assets.PAD_BASE+assets.PADS.index(pad)])

    def test_real_mod_lookup_takes_priority_over_generated_prompt_font(self):
        source=(ROOT/"host/mods.c").read_text()
        fixture=r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cctype>
using LONG=long;
LONG InterlockedIncrement(volatile LONG*p){return ++*p;}
void hos_log(const char*,...){}
#define HOS_FS_PATH_CAP 4096
#define _strdup strdup
typedef struct {char*key;char*host;uint64_t size;int is_dir,logged;} Entry;
static Entry*table;static size_t table_cap,table_n;
int fallback=0;
int hos_prompts_romfs(const char*,char*out,size_t n){++fallback;snprintf(out,n,"generated-font");return 1;}
'''
        for marker in ('static uint64_t hash_str(', 'static void lower_slash(', 'static Entry *find(',
                       'static int put(', 'int hos_mods_romfs(', 'int hos_mods_has('):
            fixture+=function(source,marker)
        fixture+=r'''
int main(){
 char out[4096];const char*key="font2/scalable/external.nin_ounce_nvn2.bfotf.zs";
 assert(hos_mods_romfs(key,out,sizeof out)&&fallback==1);
 assert(put(key,"my-mod-font",123,0));
 assert(hos_mods_romfs("Font2/Scalable/External.Nin_Ounce_NVN2.bfotf.zs",out,sizeof out));
 assert(!strcmp(out,"my-mod-font")&&fallback==1);
 assert(put(key,"later-mod-font",456,0));
 assert(hos_mods_romfs(key,out,sizeof out)&&!strcmp(out,"later-mod-font")&&fallback==1);
 assert(hos_mods_has("font2/",".zs"));
 assert(!hos_mods_romfs(key,out,2));
 for(size_t i=0;i<table_cap;++i){free(table[i].key);free(table[i].host);}free(table);
}
'''
        self.compile_run(fixture)


class PromptPreparation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game, self.romfs = self.root/"game", self.root/"romfs"
        self.game.mkdir()
        self.protected = self.root/"work/objcache/keep.o"
        self.protected.parent.mkdir(parents=True)
        self.protected.write_bytes(b"compiled")
        for rel in prompts.INPUTS + ("System/Resource/ResourceSizeTable.Product.rsizetable.zs",):
            path=self.romfs/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"fixture")

    def runner(self, args, **kwargs):
        if "-c" not in args:
            dest=Path(args[args.index("--out")+1])
            for name in prompts.REQUIRED:
                path=dest/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"complete")
        return subprocess.CompletedProcess(args,0,"","")

    def prepare(self, runner=None):
        with patch.object(prompts,"source_stamp",return_value="source-fixture"):
            return prompts.prepare_prompts(self.game,self.romfs,root=ROOT,report=lambda _:None,runner=runner or self.runner)

    def test_complete_generation_is_cached_and_work_is_preserved(self):
        self.assertEqual(self.prepare()["state"],"prepared")
        def no_run(*a,**kw):self.fail("A cache hit must not launch Python or regenerate")
        self.assertEqual(self.prepare(no_run)["state"],"cached")
        self.assertEqual(self.protected.read_bytes(),b"compiled")
        self.assertFalse(list(self.game.glob(".prompts-*")))

    def test_missing_module_does_not_leave_a_half_cache_or_abort_game(self):
        def missing(args,**kwargs):return subprocess.CompletedProcess(args,1,"","ModuleNotFoundError")
        self.assertEqual(self.prepare(missing)["state"],"missing-dependencies")
        self.assertFalse((self.game/"prompts").exists())

    def test_foreign_folder_and_malformed_marker_are_preserved(self):
        external=self.game/"prompts";external.mkdir();(external/"keep.bin").write_bytes(b"mod")
        self.assertEqual(self.prepare()["state"],"external-folder")
        (external/prompts.MARKER).write_text("broken JSON")
        self.assertEqual(self.prepare()["state"],"external-folder")
        self.assertEqual((external/"keep.bin").read_bytes(),b"mod")

    def test_failed_regeneration_preserves_previous_complete_assets(self):
        self.prepare()
        before=(self.game/"prompts/Common.bntx").read_bytes()
        (self.game/"prompts/xbox/hint.bin").unlink() # corrupt own cache triggers regeneration
        def broken(args,**kwargs):
            if "-c" in args:return self.runner(args,**kwargs)
            return subprocess.CompletedProcess(args,1)
        self.assertEqual(self.prepare(broken)["state"],"generation-failed")
        self.assertEqual((self.game/"prompts/Common.bntx").read_bytes(),before)

    def test_incomplete_child_output_is_not_published(self):
        def partial(args,**kwargs):return subprocess.CompletedProcess(args,0,"","")
        self.assertEqual(self.prepare(partial)["state"],"incomplete")
        self.assertFalse((self.game/"prompts").exists())


if __name__ == "__main__":
    unittest.main()
