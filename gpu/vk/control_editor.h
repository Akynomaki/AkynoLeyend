// Control editing shared by the native overlay and game-free regressions.
#pragma once
#include <algorithm>
#include <cstdint>
#include "vk_api.h"
namespace mkwvk::controls {
inline constexpr const char* names[HOS_KEY_N] = {
    "a","b","x","y","ls","rs","l","r","zl","zr","plus","minus","left","up","right","down",
    "move_up","move_down","move_left","move_right","cam_up","cam_down","cam_left","cam_right"};
inline constexpr const char* actions[HOS_KEY_N] = {
    "A / action","B / cancel","X","Y / attack","Left stick press","Right stick press","L","R","ZL","ZR",
    "Plus / menu","Minus / map","D-pad left","D-pad up","D-pad right","D-pad down",
    "Move up","Move down","Move left","Move right","Camera up","Camera down","Camera left","Camera right"};
inline constexpr int nintendo[HOS_SW_N] = {1,0,3,2,7,8,9,10,15,16,6,4,13,11,14,12};
struct Editor {
    bool page=false;
    int action=0, pad=-1, key[2]={}, layout=0;
    void refresh(const MkwVkHost* h) {
        if(!h || !h->binding) return;
        action=std::clamp(action,0,int(HOS_KEY_N)-1);
        pad=action<HOS_SW_N?h->binding(HOS_BIND_PAD,action,0):-1;
        for(int i=0;i<2;++i) key[i]=h->binding(HOS_BIND_KEY,action,i);
        bool a=true,b=true;
        for(int i=0;i<HOS_SW_N;++i) {
            const int v=h->binding(HOS_BIND_PAD,i,0);
            const int pc=i<4?nintendo[i^1]:nintendo[i];
            a &= v==nintendo[i]; b &= v==pc;
        }
        layout=a?0:b?1:2;
    }
    void preset(const MkwVkHost* h,int choice) {
        if(!h || !h->bind) return;
        for(int i=0;i<HOS_SW_N;++i) h->bind(HOS_BIND_PAD,i,0,nintendo[i]);
        if(choice==1) {
            h->bind(HOS_BIND_PAD,HOS_SW_A,0,HOS_PAD_SOUTH);
            h->bind(HOS_BIND_PAD,HOS_SW_X,0,HOS_PAD_WEST);
        }
        refresh(h);
    }
    void bind(const MkwVkHost* h,int set,int slot,int code) {
        if(h && h->bind && (set==HOS_BIND_KEY || action<HOS_SW_N))
            h->bind(set,action,slot,code);
        refresh(h);
    }
};
// Held keys/buttons must be released before they can become a new binding.
// The caller suppresses normal menu navigation while this capture is active.
struct Capture {
    bool active=false, keys[256]{};
    int set=HOS_BIND_PAD,slot=0;
    uint32_t raw=0;
    void begin(int kind,int target_slot,const bool* held,uint32_t buttons) {
        active=true;set=kind;slot=target_slot;raw=buttons;
        std::copy(held,held+256,keys);
    }
    // 0 pending, 1 binding returned, -1 cancelled. VK_ESCAPE=27, VK_DELETE=46.
    int poll(const bool* held,uint32_t buttons,bool focused,int& code) {
        if(!active) return 0;
        if(!focused || (held[27] && !keys[27])) {active=false;return -1;}
        if(held[46] && !keys[46]) {code=set==HOS_BIND_PAD?-1:0;active=false;return 1;}
        if(set==HOS_BIND_PAD) {
            const uint32_t pressed=buttons&~raw;
            for(int i=0;i<HOS_PAD_N;++i) if(pressed&(1u<<i)) {code=i;active=false;return 1;}
        } else {
            for(int i=1;i<256;++i) if(held[i] && !keys[i]) {code=i;active=false;return 1;}
        }
        std::copy(held,held+256,keys);raw=buttons;return 0;
    }
};
} // namespace mkwvk::controls
