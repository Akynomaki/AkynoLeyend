"""Execute the production video queue/acquire code and overlay geometry with synthetic data."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def function(text, marker):
    a=text.index(marker);b=text.index('{',a)+1;depth=1
    while depth:
        depth+=(text[b]=='{')-(text[b]=='}');b+=1
    return text[a:b]


class NativeTest3(unittest.TestCase):
    def run_cpp(self, code, cases=((),), environment=None):
        cxx=shutil.which('c++')
        if not cxx:self.skipTest('C++ compiler unavailable')
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'test.cpp';exe=Path(d)/'test';source.write_text(code)
            p=subprocess.run([cxx,'-std=c++20','-O1','-I'+str(ROOT/'gpu/vk'),str(source),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            for case in cases:
                p=subprocess.run([str(exe),*case],capture_output=True,text=True,env=environment)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_nv12_frames_keep_exact_planes_and_skip_unused_rgba_conversion(self):
        s=(ROOT/'host/nn_video.c').read_text()
        code=r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#define MAX_QUEUE 8
#define SWS_BILINEAR 1
enum AVPixelFormat{AV_PIX_FMT_NV12,AV_PIX_FMT_RGBA,AV_PIX_FMT_YUV420P,AV_PIX_FMT_YUVA420P};
struct SwsContext{};int conversions=0,contexts=0;
SwsContext* sws_getContext(int,int,AVPixelFormat,int,int,AVPixelFormat,int,void*,void*,void*){++contexts;static SwsContext c;return &c;}
void sws_freeContext(SwsContext*){}
int sws_scale(SwsContext*,const uint8_t*const*,const int*,int,int,uint8_t*const*,const int*){++conversions;return 4;}
using LONG=long;LONG InterlockedIncrement(volatile LONG* n){return ++*n;}void hos_log(const char*,...){}
struct AVFrame{int width,height,format;int64_t pts;uint8_t*data[8];int linesize[8];};
struct Picture{uint8_t*rgba,*nv12;int w,h;int64_t pts;int last;};
struct Dec{SwsContext*sws=nullptr;int sws_w=0,sws_h=0,sws_fmt=0;Picture queue[8]{};int qhead=0,qn=0;};
'''
        code+=function(s,'static void picture_free(')+function(s,'static void queue_frame(')
        code+=r'''
int main(){
 uint8_t y[32],uv[16];for(int i=0;i<32;i++)y[i]=uint8_t(i+16);for(int i=0;i<16;i++)uv[i]=uint8_t(120+i);
 AVFrame frame{};frame.width=frame.height=4;frame.format=AV_PIX_FMT_NV12;frame.pts=123456;
 frame.data[0]=y;frame.data[1]=uv;frame.linesize[0]=frame.linesize[1]=8;
 Dec d;queue_frame(&d,&frame);assert(d.qn==1&&contexts==0&&conversions==0);
 auto&p=d.queue[0];assert(!p.rgba&&p.pts==123456&&p.w==4&&p.h==4);
 for(int r=0;r<4;r++)assert(!memcmp(p.nv12+r*4,y+r*8,4));
 for(int r=0;r<2;r++)assert(!memcmp(p.nv12+16+r*4,uv+r*8,4));
 for(int n=0;n<20;n++){frame.pts++;queue_frame(&d,&frame);}assert(d.qn==8&&contexts==0&&conversions==0);
 for(int n=0;n<d.qn;n++)picture_free(&d.queue[(d.qhead+n)%8]);
}
'''
        self.run_cpp(code)

    def test_actual_movie_acquire_limits_catchup_instead_of_decoding_a_whole_backlog(self):
        s=(ROOT/'host/nn_video.c').read_text()
        code=r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#define MAX_SLOTS 16
#define MAX_QUEUE 8
#define POOL_MAGIC 1
#define DEC_MAGIC 2
#define RESULT_NO_OUTPUT 123
struct Ctx{uint64_t x[32]{};};
#define ARG(i) (c->x[i])
#define RET(v) (c->x[0]=(v))
#define GP(v) ((void*)(uintptr_t)(v))
#define G32(v) (*(uint32_t*)GP(v))
#define G64(v) (*(uint64_t*)GP(v))
#define HOS_WRITTEN(p,n) ((void)0)
int64_t clock_ns=1000000000,decode_ns=0;int calls=0;
int64_t hos_now_ns(){return clock_ns;}void hos_sleep_ns(int64_t n){clock_ns+=n;}int video_log(){return 0;}
void hos_log(const char*,...){}void AcquireSRWLockExclusive(int*){}void ReleaseSRWLockExclusive(int*){}
struct Pool{int w=4,h=4,format=0,count=1;uint8_t*rgba,*nv12;uint64_t mem=0,mem_size=0;int rgba_stale=0,read_by_api=0;};
struct Picture{uint8_t*rgba,*nv12;int w,h;int64_t pts;int last;};
struct Dec{uint64_t slots[16]{};int busy[16]{};int64_t slot_pts[16]{};int slot_last[16]{};Picture queue[8]{};
 int qhead=0,qn=1,eos=0;void*phead=(void*)1;int64_t acquires=0;int clock_set=1;int64_t clock_ns=-1000000000,clock_pts=0;int lock=0;};
void*host_of(uint64_t p,uint32_t){return GP(p);}void pool_rgba(Pool*){}
Picture make_picture(int64_t pts){return{(uint8_t*)calloc(64,1),(uint8_t*)calloc(24,1),4,4,pts,0};}
void decode_pending(Dec*){}
void decode_next(Dec*d){++calls;clock_ns+=decode_ns;d->queue[(d->qhead+d->qn)%8]=make_picture(calls*16666667);++d->qn;if(calls==100)d->phead=nullptr;}
'''
        code+=function(s,'static void picture_free(')
        code+=function(s,'static int video_catchup_more(')
        code+=function(s,'static void dec_acquire(')
        code+=r'''
int main(int argc,char**argv){
 unsetenv("HOS_VIDEO_NO_CATCHUP");decode_ns=argc>1?atoll(argv[1]):100000;
 Dec d;d.queue[0]=make_picture(0);uint8_t rgba[64]{},nv12[24]{};Pool pool;pool.rgba=rgba;pool.nv12=nv12;
 d.slots[0]=(uintptr_t)&pool;uint32_t index=99;Ctx c;c.x[0]=(uintptr_t)&index;c.x[2]=(uintptr_t)&d;
 dec_acquire(&c);assert(c.x[0]==0&&index==0&&d.busy[0]);assert(calls>0&&calls<=2);
 if(decode_ns>=8000000)assert(calls==1);
 for(int n=0;n<d.qn;n++)picture_free(&d.queue[(d.qhead+n)%8]);
}
'''
        self.run_cpp(code,cases=(('100000',),('10000000',)))

    def test_native_full_hd_works_with_docked_and_handheld_without_reindexing_old_options(self):
        s=(ROOT/'host/nn_applet.c').read_text()
        code=r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
void hos_log(const char*,...){}int ini_option(const char*,int v){return v;}int handheld(){return getenv("HOS_HANDHELD")&&atoi(getenv("HOS_HANDHELD"));}
'''+function(s,'int hos_output_mode(')+function(s,'uint32_t hos_output_size(')+r'''
int main(int argc,char**argv){setenv("HOS_OUTPUT_RES",argv[1],1);setenv("HOS_HANDHELD",argv[2],1);
 const int expected=atoi(argv[3]);assert(hos_output_mode()==expected);
 if(expected==3)assert(hos_output_size(0)==1920&&hos_output_size(1)==1080);
 if(expected==2)assert(hos_output_size(0)==3840&&hos_output_size(1)==2160);
 if(expected==1)assert(hos_output_size(0)==2560&&hos_output_size(1)==1440);
}
'''
        self.run_cpp(code,cases=(('3','0','3'),('3','1','3'),('2','0','2'),('1','0','1'),('2','1','0'),('99','0','0')))

    def test_mouse_geometry_maps_client_pixels_to_rows_and_sharpness(self):
        self.run_cpp(r'''
#include <cassert>
#include "menu_pointer.h"
int main(){using namespace mkwvk::menu_pointer;
 assert(row(16,rows_top,548,1,11)==0);
 assert(row(16,rows_top+10*row_height,548,1,11)==10);
 assert(row(16,rows_top+11*row_height,548,1,11)==-1);
 assert(row(-1,rows_top,548,1,11)==-1);
 assert(row(32,2*(rows_top+2*row_height),1096,2,11)==2);
 assert(first_row(0,10,4,12)==7);
 assert(first_row(7,2,4,12)==2);
 assert(first_row(7,10,12,12)==0);
 assert(image_coordinate(640,1280,1920)==960);assert(image_coordinate(0,0,1920)==-1);
 assert(slider(0,360,1)==0&&slider(999,360,1)==100&&slider(260,360,1)==50);
}
''')
