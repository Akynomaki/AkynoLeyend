/* nn::vi for MKW (TOTKPort's nn_vi.c is bound to its renderer and TOTK's frame pacing): the default display, one
   layer, and the display's vsync event, signaled at 60 Hz by a host thread. HDR and VRR are reported unsupported,
   so the game takes its SDR path. Frames are paced at the native NVN layer's window acquire (the end of this file). */
#include "hos.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../gpu/vk/dlss_math.h"
#include "../gpu/vk/vk_fsr_options.h"
#include "../gpu/vk/menu_option_ids.h"

int rx_option(int id, int otherwise);   /* (the renderer's: the F1 panel's rows, gpu/vk/vk_replay.cpp) */

void hos_system_event_init(uint64_t key, int autoclear);   /* nn_os_sync.c */
void hos_system_event_signal(uint64_t key);

static uint64_t display, layer;
static uint64_t vsync_events[8];
static volatile LONG nvsync;
static HANDLE vsync_thread;

static int fps_max(void);   /* (below: the frame rate cap) */
static DWORD WINAPI vsync_main(void *p) {
    (void)p;
    int64_t period = 1000000000LL / 60;
    int64_t next = hos_now_ns() + period;
    for (;;) {
        period = 1000000000LL / fps_max();   /* (60 until the lifted code's step hook has run: fps_max) */
        const int64_t now = hos_now_ns();
        if (next > now) hos_sleep_ns(next - now);
        next += period;
        if (next < hos_now_ns()) next = hos_now_ns() + period;   /* (fell behind: no burst of vsyncs) */
        for (LONG i = 0; i < nvsync; i++) hos_system_event_signal(vsync_events[i]);
    }
    return 0;
}

/* nn::vi::Initialize() */
HLE(_ZN2nn2vi10InitializeEv) {}

/* nn::vi::OpenDefaultDisplay(nn::vi::Display**) -> Result */
HLE(_ZN2nn2vi18OpenDefaultDisplayEPPNS0_7DisplayE) {
    if (!display) display = hos_sys_alloc(0x100, 16);
    G64(ARG(0)) = display;
    RET(0);
}

/* nn::vi::CreateLayer(nn::vi::Layer**, nn::vi::Display*) -> Result */
HLE(_ZN2nn2vi11CreateLayerEPPNS0_5LayerEPNS0_7DisplayE) {
    if (!layer) layer = hos_sys_alloc(0x100, 16);
    G64(ARG(0)) = layer;
    RET(0);
}

/* nn::vi::GetDisplayVsyncEvent(nn::os::SystemEventType*, nn::vi::Display*) -> Result */
HLE(_ZN2nn2vi20GetDisplayVsyncEventEPNS_2os15SystemEventTypeEPNS0_7DisplayE) {
    hos_system_event_init(ARG(0), 1);
    if (nvsync < (LONG)(sizeof vsync_events / sizeof vsync_events[0])) {
        vsync_events[nvsync] = ARG(0);
        InterlockedIncrement(&nvsync);
    }
    if (!vsync_thread) vsync_thread = CreateThread(NULL, 0, vsync_main, NULL, 0, NULL);
    RET(0);
}

/* nn::vi::QueryDisplayHdrStatus(bool* on, HdrOutputFormat*, unsigned short* max nits, Display const*) -> Result */
/* (AkynoLeyend r13, Hookshot v2.1.0) the F1 panel's HDR set to Native on an HDR10 swapchain: an HDR10 display (format 1, which
   makes the game present PQ codes) with the panel's peak; otherwise SDR, as before */
HLE(_ZN2nn2vi21QueryDisplayHdrStatusEPbPNS0_15HdrOutputFormatEPtPKNS0_7DisplayE) {
    const int native = rx_option(AKYNO_OPT_HDR_NATIVE, 0);
    *(uint8_t *)GP(ARG(0)) = native ? 1 : 0;
    if (ARG(1)) G32(ARG(1)) = native ? 1 : 0;
    if (ARG(2)) *(uint16_t *)GP(ARG(2)) = native ? (uint16_t)rx_option(AKYNO_OPT_HDR_PEAK, 1000) : 0;
    static int logged = -1;
    if (logged != native) logged = native, hos_log("vi: QueryDisplayHdrStatus -> %s", native ? "HDR10 (the game's native HDR)" : "SDR");
    RET(0);
}
/* nn::vi::QueryDisplayHdrPaperWhite(unsigned short*, Display const*) -> Result */
HLE(_ZN2nn2vi25QueryDisplayHdrPaperWhiteEPtPKNS0_7DisplayE) {
    *(uint16_t *)GP(ARG(0)) = rx_option(AKYNO_OPT_HDR_NATIVE, 0) ? (uint16_t)rx_option(AKYNO_OPT_HDR_WHITE, 203) : 203;
    RET(0);
}
/* nn::vi::QueryDisplayVrrSupported(bool*, Display const*) -> Result */
HLE(_ZN2nn2vi24QueryDisplayVrrSupportedEPbPKNS0_7DisplayE) {
    *(uint8_t *)GP(ARG(0)) = 0;
    RET(0);
}
HLE(_ZN2nn2vi23SetDisplayVrrCapabilityEPNS0_7DisplayEb) { RET(0); }
HLE(_ZN2nn2vi28SetLayerExtendedSwapIntervalEPNS0_5LayerEii) { RET(0); }
HLE(_ZN2nn2vi30ClearLayerExtendedSwapIntervalEPNS0_5LayerE) { RET(0); }

/* nn::vi::GetNativeWindow(void**, nn::vi::Layer*) -> Result: a window object (NVN builds its window on it; the
   native NVN layer only keeps the pointer) */
HLE(_ZN2nn2vi15GetNativeWindowEPPvPNS0_5LayerE) {
    static uint64_t window;
    if (!window) window = hos_sys_alloc(0x100, 16);
    G64(ARG(0)) = window;
    hos_log("vi: GetNativeWindow -> %#llx", (unsigned long long)window);
    RET(0);
}

/* ---- frame pacing for the native NVN layer's window (nvn_native.c) ----
   The game acquires a window texture before each frame and presents it after; on the console the acquire blocks
   while every texture waits for the display. Here the acquire waits for the frame's display time: the present
   interval's vsyncs (1: 60 fps, 2: 30) after the last present, so the game runs at the display's rate.
   HOS_NO_PACING=1: as fast as it can. */
static volatile int present_interval = 1;
/* (AkynoLeyend r9, from Hookshot v2.1.0) The F1 panel's Game frame rate cap, frame_rate_cap= in the options file: 0 the
   console's 60, then 90, 120, 144, 165, 240; HOS_FPS_MAX=<61-240> over it. Past 60 the display pacing's interval, the game's
   own limiter (+0xfc) and the vsync event go up to it, and the game's time step is the frames' own time (realtime_step and
   nx2/oot_patches.py's step hook), so the game is not sped up. The cap counts only once that hook has run (hos_step_probe):
   a lift without it would play fps / 60 times too fast, so it stays at 60. */
/* (AkynoLeyend r13, from Hookshot v2.1.0) The F1 panel's Text speed (0 the game's, 1 2x, 2 4x, 3 the page at once),
   HOS_TEXT_SPEED=<0..3> over it: what the time of a letter animation's step is multiplied by (the letters' clock of a text
   pane, f_80b1e140: nx2/oot_patches.py). Instant: the page at once, as the game's own skip on A */
volatile float hos_text_scale = 1.0f;
static float text_scale(const char *env, int menu) {
    const int v = env && *env ? atoi(env) : menu;
    return v == 1 ? 2.0f : v == 2 ? 4.0f : v >= 3 ? 1e6f : 1.0f;
}
/* (AkynoLeyend 0.4.5-test.1, unified) The F1 panel's Render distance (0 the game's own; the rows' metres in akyno_render_distance,
   menu_option_ids.h), AKYNO_RENDER_DISTANCE=<metres> over it: the far plane the engine's perspective projections make their
   matrix with (f_834a5cc0: nx2/oot_patches.py). Read every present, so the row counts at once; the game makes the camera's
   matrix again each frame. A projection whose far plane is inside the limit keeps it (interiors, the menus' models, the
   lights' shadow views), and so does one whose near plane is not well inside the limit. */
volatile float hos_render_far = 0.0f;
static float render_far(const char *env, int row) {
    const float v = env && *env ? (float)atof(env) : (float)akyno_render_distance(row);
    return v >= 1.0f ? v : 0.0f;
}
float hos_render_far_clamp(float near_plane, float far_plane) {
    const float limit = hos_render_far;
    static volatile LONG told;
    if (far_plane > 0.0f && told < 12) {   /* (the far planes the game asks for, a few: what the rows are measured against) */
        static float seen[12];
        int known = 0;
        for (int i = 0; i < 12; i++) known |= seen[i] == far_plane;
        if (!known) {
            const LONG at = InterlockedIncrement(&told) - 1;
            if (at < 12) seen[at] = far_plane, hos_log("vi: render distance: a projection with near %g, far %g (limit %g)",
                                                       (double)near_plane, (double)far_plane, (double)limit);
        }
    }
    if (!(limit > 0.0f) || !(far_plane > limit) || !(near_plane > 0.0f) || !(near_plane < limit * 0.25f)) return far_plane;
    return limit;
}
/* The lifted hook writes the answer into the projection (at: its far plane, +0x9c). The game's own far plane per projection
   is kept here, so a lifted or raised limit gives it back; a value other than the one written is the game's new one. */
float hos_render_far_site(uint64_t at, float near_plane, float far_plane) {
    static struct { uint64_t at; float game, wrote; } kept[32];
    static SRWLOCK lock = SRWLOCK_INIT;
    AcquireSRWLockExclusive(&lock);
    int slot = -1, free_slot = -1;
    for (int i = 0; i < 32; i++) {
        if (kept[i].at == at) { slot = i; break; }
        if (!kept[i].at && free_slot < 0) free_slot = i;
    }
    const float game = slot >= 0 && far_plane == kept[slot].wrote ? kept[slot].game : far_plane;
    float want = hos_render_far_clamp(near_plane, game);
    if (want == game) {
        if (slot >= 0) kept[slot].at = 0;
    } else if (slot >= 0 || (slot = free_slot) >= 0) {
        kept[slot].at = at, kept[slot].game = game, kept[slot].wrote = want;
    } else {
        want = game;   /* (no room to keep the game's value: this projection keeps it) */
    }
    ReleaseSRWLockExclusive(&lock);
    return want;
}
volatile uint64_t hos_step_probe = 0;          /* (f_80706be0's object, set by the lifted code: the hook is in this build) */
volatile uint32_t hos_frame_seconds_bits = 0;  /* (the frame's seconds as a float's bits for the hook; 0: the game's own step) */
int hos_ini_option(const char *key, int otherwise);   /* (nn_applet.c) */
static int fps_cap_asked(void) {
    static int v = -1;
    if (v < 0) {
        const char *e = getenv("HOS_FPS_MAX");
        const int want = e ? atoi(e) : akyno_fps_cap(hos_ini_option("frame_rate_cap", 0));
        v = want > 60 ? (want > 240 ? 240 : want) : 60;
        if (v > 60) hos_log("vi: frame rate cap %d asked: pacing, the game's limiter and its time step follow it", v);
    }
    return v;
}
static int fps_max(void) {
    const int asked = fps_cap_asked();
    if (asked <= 60) return 60;
    static int told;
    if (!hos_step_probe) return 60;
    if (!told) told = 1, hos_log("vi: frame rate cap %d on: the step hook is in this build", asked);
    return asked;
}
static int64_t next_frame_at, window_start, frames_in_window;
static volatile LONG64 presents;

/* The lift adds this only to the projection loads used to build the GPU
   uniforms. The game's camera, culling and shadow frusta stay in place. */
/* (diagnostic, AKYNO_FAR_PROBE=1) the projection the GPU uniforms are built from: its depth terms, a few distinct ones */
static void far_probe(uint64_t projection) {
    static int on = -1, told;
    if (on < 0) on = getenv("AKYNO_FAR_PROBE") != NULL;
    if (!on || told >= 300) return;
    static uint64_t addr[16];
    static float last[16][3];
    int i = 0;
    while (i < 16 && addr[i] && addr[i] != projection) i++;
    if (i == 16) return;
    float m[16];
    memcpy(m, GP(projection), sizeof m);
    if (addr[i] && m[10] == last[i][0] && m[11] == last[i][1] && m[14] == last[i][2]) return;
    addr[i] = projection, last[i][0] = m[10], last[i][1] = m[11], last[i][2] = m[14];
    told++;
    hos_log("vi: far probe %#llx: m00 %g m11 %g m02 %g m12 %g | m22 %g m23 %g m32 %g m33 %g | gl n %g f %g, d3d n %g f %g",
            (unsigned long long)projection, (double)m[0], (double)m[5], (double)m[2], (double)m[6], (double)m[10], (double)m[11],
            (double)m[14], (double)m[15], (double)(m[11] / (m[10] - 1.0f)), (double)(m[11] / (m[10] + 1.0f)),
            (double)(m[11] / m[10]), (double)(m[11] / (m[10] + 1.0f)));
}
int hos_fsr_jitter_clip(uint64_t projection, float out[2]) {
    int rx_option(int id, int otherwise);
    far_probe(projection);
    const int width = rx_option(HOS_OPT_FSR_JITTER_W, 0);
    if (width <= 0) return 0;
    const int height = rx_option(HOS_OPT_FSR_JITTER_H, 0);
    const int phases = rx_option(HOS_OPT_FSR_JITTER_PHASES, 8);
    float matrix[16];
    memcpy(matrix, GP(projection), sizeof matrix);
    const unsigned frame = (unsigned)InterlockedCompareExchange64(&presents, 0, 0);
    const float aspect = height > 0 ? (float)width / (float)height : 0.0f;
    return dlss_jitter_clip(matrix, aspect, frame, phases, (float)width, (float)height, out);
}
int hos_vi_native_interval(Ctx *c, int requested) {
    (void)c;
    /* Hookshot v2.0.6: real-time play presents ready frames without 30/20/15 fps steps. */
    int rx_option(int id, int otherwise);
    static int game_interval = -1;
    if (game_interval < 0) game_interval = getenv("HOS_GAME_INTERVAL") && atoi(getenv("HOS_GAME_INTERVAL")) != 0;
    const int clamped = requested < 1 ? 1 : requested > 4 ? 4 : requested;
    present_interval = game_interval || !rx_option(0, 1) ? clamped : 1;
    return requested;
}
/* (hookshot) The window's textures as the console's display queue has them: each present is shown at its display
   time, the later of its present and one interval after the frame shown before it, and a texture is free again once
   the frame presented after it is shown. The acquire of a frame waits for its texture: with `active` textures, the
   texture of the frame `active` back, freed when the frame after that one is shown. With three (OoT) a frame slower
   than the display waits for nothing and a fast one is held to the display's rate, two frames queued at most;
   the acquire waited for one interval after the last present before (two textures' behaviour), which held every
   frame over 16.7 ms to the next vsync step (gameplay at 27 ms frames, 5 ms of them in this sleep). HOS_VI_DOUBLE=1:
   that behaviour */
static int64_t shown_at[16];
static volatile LONG64 shown_count;
void hos_vi_native_acquire(int active) {
    static int no_pacing = -1, double_buffered = -1;
    if (no_pacing < 0) no_pacing = getenv("HOS_NO_PACING") != NULL;
    if (double_buffered < 0) double_buffered = getenv("HOS_VI_DOUBLE") != NULL;
    if (no_pacing || !next_frame_at) return;
    int64_t until = next_frame_at;
    if (!double_buffered && active >= 2) {
        const int64_t n = shown_count, frame = n - active + 1;   /* (the frame whose showing frees this texture) */
        until = frame >= 0 && frame < n ? shown_at[frame & 15] : 0;
    }
    const int64_t now = hos_now_ns();
    if (until > now) hos_sleep_ns(until - now);
}
/* (mkw-recomp) MKW's frame pacer (0x806bcbb0, x19 when it sets the interval: nvn_native.c): its measured frame time
   (+0x128, ticks), its running excess (+0x218) and interval (+0x214), logged with the frame rate */
volatile uint64_t hos_mkw_pacer;
/* HOS_SCAN_DT=<file prefix> (diagnostic): writes every float in guest memory between ~0.015 and ~0.04, with its
   address, four times 300 presents apart: the game's frame step is either one exact 1/60 or follows the frames */
static void scan_dt(long long presents) {
    static long long first; static const char *prefix; static int scans, read_env;
    if (!read_env) read_env = 1, prefix = getenv("HOS_SCAN_DT");
    if (!prefix) return;
    if (!first) {   /* (once <prefix>go exists) */
        if (presents % 60) return;
        char go[512];
        snprintf(go, sizeof go, "%sgo", prefix);
        FILE *g = fopen(go, "r");
        if (!g) return;
        fclose(g);
        first = presents;
    }
    if (presents < first + scans * 300 || scans >= 4) return;
    char name[512];
    snprintf(name, sizeof name, "%s%d.txt", prefix, scans++);
    FILE *f = fopen(name, "w");
    if (!f) return;
    size_t hits = 0;
    for (uint64_t a = 0x80000000ULL; a < 0x2000000000ULL && hits < 4000000;) {
        MEMORY_BASIC_INFORMATION m;
        if (!VirtualQuery(GP(a), &m, sizeof m)) break;
        const uint64_t size = m.RegionSize;
        if (m.State == MEM_COMMIT && (m.Protect & PAGE_READWRITE)) {
            const uint32_t *w = (const uint32_t *)m.BaseAddress;
            for (size_t i = 0; i < size / 4; i++)
                if (w[i] >= 0x3c800000 && w[i] <= 0x3d230000) {
                    fprintf(f, "%llx %08x\n", (unsigned long long)((uint8_t *)&w[i] - (uint8_t *)GP(0)), w[i]);
                    if (++hits >= 4000000) break;
                }
        }
        a = (uint64_t)((uint8_t *)m.BaseAddress - (uint8_t *)GP(0)) + size;
    }
    fclose(f);
    hos_log("vi: scan %s: %zu floats", name, hits);
}
/* (hookshot) Game time follows the clock. The engine steps every frame by ratio = 60 / <the graphics module's nominal fps,
   an int at +0x2c8> (main+0x6e6cc4, f_83b6e300 makes seconds = ratio / 60 and the rest), so at 50 fps the game ran at 83%
   speed: walking the same 8 s at 52 and 33 fps went as far as those rates. Each present writes the rate of the last 5
   display intervals there, the rounding error carried to the next frame so that no time is lost; a step is at most
   1/15 s, as TotK Recomp's frame_rate.c (slower frames slow the game down, as on the console), at least 1/60 s (the game's
   own limit holds it at 60). HOS_REALTIME_STEP=0: the shipping whole steps. */
extern volatile uint64_t hos_gfx_module;
volatile int hos_fixed_resolution = 0;   /* (the lifted code reads these: nx2/oot_patches.py) */
volatile uint32_t hos_fixed_scale_bits = 0x3f800000;   /* (HOS_RES_SCALE: the fixed path's scale) */
volatile uint64_t hos_res_module = 0;   /* fixed-scale refresh tracks the game's resolution object */
volatile int hos_dynres_runs = 0;   /* (the dynamic path's frames: it fills fields the 3D reads, +8 +16 +168) */
static void realtime_step(int64_t now) {
    int rx_option(int id, int otherwise);
    /* (Resolution 100% from the start: the fixed path skipped the dynamic block from the first frame, its fields stayed
       unset and the 3D came out black. The dynamic path runs a few frames first, as when the menu turns it on in game) */
    hos_fixed_resolution = !rx_option(2, 1) && hos_dynres_runs >= 30;
    {
        static const char *env;
        static int looked;
        if (!looked) looked = 1, env = getenv("HOS_TEXT_SPEED");
        const float scale = text_scale(env, rx_option(AKYNO_OPT_TEXT_SPEED, 0));
        if (scale != hos_text_scale) hos_log("vi: text speed x%g (the panel's row)", (double)scale);
        hos_text_scale = scale;
    }
    {   /* (0.4.5-test.1, unified: the panel's Render distance row, each present) */
        static const char *env;
        static int looked;
        if (!looked) looked = 1, env = getenv("AKYNO_RENDER_DISTANCE");
        const float limit = render_far(env, rx_option(AKYNO_OPT_RENDER_DISTANCE, 0));
        if (limit != hos_render_far) hos_log("vi: render distance %g m (0: the game's own)", (double)limit);
        hos_render_far = limit;
    }
    {   /* (AkynoLeyend r13, Hookshot v2.1.0: ultrawide's menus. The panel's Ultrawide menus row, each frame: which screens
           keep the whole picture; only with a margin, a picture wider than 16:9) */
        extern volatile float hos_wide_margin;
        extern volatile uint32_t hos_wide_keep_mask;
        uint32_t rx_wide_menus(float margin);
        if (hos_wide_margin > 0.0f) {
            const uint32_t mask = rx_wide_menus(hos_wide_margin);
            if (mask != hos_wide_keep_mask) hos_log("vi: ultrawide menus: the screens kept whole %#x (the panel's row)", mask);
            hos_wide_keep_mask = mask;
        }
    }
    {   /* (the Insert menu's Resolution: the fixed path's scale, live; HOS_RES_SCALE below stays over it) */
        const int percent = rx_option(3, 0);
        if (percent > 0 && !getenv("HOS_RES_SCALE")) {
            const float v = percent / 100.0f;
            memcpy((void *)&hos_fixed_scale_bits, &v, 4);
        }
    }
    {
        static int read_scale;
        if (!read_scale) {
            read_scale = 1;
            if (getenv("HOS_RES_SCALE")) {
                const float v = (float)atof(getenv("HOS_RES_SCALE"));
                if (v >= 0.5f && v <= 2.0f) {
                    memcpy((void *)&hos_fixed_scale_bits, &v, sizeof v);
                    hos_log("vi: fixed scale requested: %.3f (not verified on GPU)", (double)v);
                } else {
                    hos_log("vi: HOS_RES_SCALE invalid; ignoring (valid interval 0.5 to 2.0)");
                }
            }
        }
    }
    const uint64_t mod = hos_gfx_module;
    if (!mod) return;
    /* A request is not an applied scale until the fixed path becomes active.
       This reports CPU-side switch selection, NOT measured render-target size. */
    {
        static int last_fixed = -1;
        const int fixed_now = hos_fixed_resolution != 0;
        if (fixed_now != last_fixed) {
            last_fixed = fixed_now;
            if (fixed_now) {
                float actual = 1.0f;
                const uint32_t bits = hos_fixed_scale_bits;
                memcpy(&actual, &bits, sizeof actual);
                hos_log("vi: fixed scale active: %.3f after %d dynamic frames (CPU-side)",
                        (double)actual, hos_dynres_runs);
            }
        }
    }
    {   /* (hookshot) The frame limiter (f_8042cd20 sleeps to 1 / +0xfc). The engine's adaptive controller writes +0xfc when
           variable refresh is on (+0x231, f_804fc0f0), any rate from 40 up. HOS_FPS_TARGET=<fps>: that rate kept, 0: left alone;
           HOS_FPS_LOG=1: what the game asks for, every 300 presents */
        static int target = -1, log_on = -1;
        static long long n;
        if (target < 0) target = getenv("HOS_FPS_TARGET") ? atoi(getenv("HOS_FPS_TARGET")) : 0, log_on = getenv("HOS_FPS_LOG") != NULL;
        int *limit = (int *)GP(mod + 0xfc);
        if (log_on && !(n++ % 300))
            hos_log("vi: frame limiter %d, vrr %d %d, nominal %d, controller +0x58.. %d %d %d %d", *limit, *(uint8_t *)GP(mod + 0x231),
                    *(uint8_t *)GP(mod + 0x232), *(int *)GP(mod + 0x2c8), *(int *)GP(mod + 0x270 + 0x58), *(int *)GP(mod + 0x270 + 0x28),
                    *(int *)GP(mod + 0x270 + 0x2c), *(int *)GP(mod + 0x270 + 0x30));
        if (target && *limit > 0 && *limit < target) *limit = target;
        if (fps_max() > 60 && *limit > 0 && *limit < fps_max()) *limit = fps_max();
    }
    /* (per frame: a frame is a 60th of a second of game time. Not past 60 fps: the game would run faster than real time, so a
       cap above 60 keeps the real-time step whatever that row says) */
    if (!rx_option(0, 1) && fps_max() <= 60) {
        int *slot = (int *)GP(mod + 0x2c8);
        if (*slot >= 15 && *slot <= 60) *slot = 60;
        return;
    }
    static int64_t last;
    static double samples[5], carry;
    static unsigned count, next;
    static long long steps;
    const double dt = (now - last) / 1e9;
    last = now;
    if (dt <= 0 || dt > 0.25) { count = next = 0; carry = 0; return; }   /* (a load: the average starts again) */
    samples[next++ % 5] = dt;
    if (count < 5) count++;
    double sum = 0;
    for (unsigned i = 0; i < count; i++) sum += samples[i];
    /* (Hookshot v2.1.0) A cap above 60: the engine's own rate is 60 / <whole display intervals>, and its controller puts 60 back
       over a higher +0x2c8 before the step is made from it. The step is then the frames' own time at the two places the engine
       makes it (nx2/oot_patches.py, hos_frame_seconds_bits): this same average, at most 1/15 s and at least 1/240 s, and the
       rate under it stays the engine's, 60 at most. */
    if (fps_max() > 60) {
        const double secs = sum / count;
        const float f = (float)(secs > 4.0 / 60.0 ? 4.0 / 60.0 : secs < 1.0 / 240.0 ? 1.0 / 240.0 : secs);
        uint32_t bits;
        memcpy(&bits, &f, 4);
        __atomic_store_n(&hos_frame_seconds_bits, bits, __ATOMIC_RELAXED);   /* (read by the game's threads) */
    } else if (hos_frame_seconds_bits) {
        __atomic_store_n(&hos_frame_seconds_bits, 0, __ATOMIC_RELAXED);
    }
    double ratio = sum / count * 60.0 + carry;
    ratio = ratio < 1.0 ? 1.0 : ratio > 4.0 ? 4.0 : ratio;
    int fps = (int)(60.0 / ratio + 0.5);
    fps = fps < 15 ? 15 : fps > 60 ? 60 : fps;
    int *slot = (int *)GP(mod + 0x2c8);
    if (*slot < 15 || *slot > 60) {
        static int logged;
        if (!logged++) hos_log("vi: the graphics module's frame rate reads %d: no real-time step", *slot);
        return;
    }
    carry = ratio - 60.0 / fps;
    carry = carry > 0.5 ? 0.5 : carry < -0.5 ? -0.5 : carry;
    *slot = fps;
    if (!(steps++ % 3000)) hos_log("vi: real-time step on: ratio %.3f, game's frame rate %d", ratio, fps);
}
void hos_vi_native_presented(void) {
    static long long scan_n;
    scan_dt(++scan_n);
    {   /* HOS_FRAME_SLEEP_MS (diagnostic): slower frames, for game speed against frame rate */
        static int ms = -1;
        if (ms < 0) ms = getenv("HOS_FRAME_SLEEP_MS") ? atoi(getenv("HOS_FRAME_SLEEP_MS")) : 0;
        if (ms) hos_sleep_ns(ms * 1000000LL);
    }
    const int64_t period = 1000000000LL / fps_max() * present_interval, now = hos_now_ns();
    realtime_step(now);
    /* (behind by more than a frame: the next one is paced from now, with no burst to catch up) */
    next_frame_at = next_frame_at && now - next_frame_at < period ? next_frame_at + period : now + period;
    {   /* (the display queue: this frame is shown one interval after the last, or now when the display waits) */
        const int64_t n = shown_count, last = n ? shown_at[(n - 1) & 15] : 0;
        shown_at[n & 15] = last + period > now ? last + period : now;
        shown_count = n + 1;
    }
    const int64_t n = InterlockedIncrement64(&presents);
    {   /* HOS_MKW_INTERVAL=<0|1|2>: the interval MKW's pacer is held at, through its own override (+0x210, any
           non-zero value is used as the interval): 1 (the default): a steady 60 fps; 2: 30; 0: the game's choice,
           which with frames between 16.7 and 33 ms swings between the two (25-27 fps, stutters). Its timing counts
           vsyncs, so an interval the renderer cannot keep slows the game down rather than dropping frames */
        static int forced = -1;
        if (forced < 0) forced = getenv("HOS_MKW_INTERVAL") ? atoi(getenv("HOS_MKW_INTERVAL")) : 1;
        if (hos_mkw_pacer && forced >= 0 && forced <= 2) G32(hos_mkw_pacer + 0x210) = (uint32_t)forced;
    }
    if (!window_start) window_start = now;
    frames_in_window++;
    /* (present-to-present intervals of the window, in buckets: which frames miss their vsync) */
    static int64_t last_present;
    static int hist[6];
    if (last_present) {
        const int64_t d = now - last_present;
        hist[d < 15500000 ? 0 : d < 17800000 ? 1 : d < 22000000 ? 2 : d < 30000000 ? 3 : d < 40000000 ? 4 : 5]++;
    }
    last_present = now;
    if (now - window_start >= 5000000000LL) {
        hos_log("vi: %lld frames presented (%.1f fps over the last %.1f s, interval %d)", (long long)n,
                frames_in_window * 1e9 / (double)(now - window_start), (now - window_start) / 1e9, present_interval);
        hos_log("vi: present intervals: <15.5 ms %d, 15.5-17.8 %d, 17.8-22 %d, 22-30 %d, 30-40 %d, over 40 %d", hist[0],
                hist[1], hist[2], hist[3], hist[4], hist[5]);
        memset(hist, 0, sizeof hist);
        window_start = now, frames_in_window = 0;
        const uint64_t pacer = hos_mkw_pacer, freq = pacer ? G64(0x837de940) : 0;   /* (MKW only: nvn_native.c) */
        if (pacer && freq)
            hos_log("vi: the game's pacer: frame work %.1f ms, excess %.1f ms, interval %d",
                    (double)(int64_t)G64(pacer + 0x128) * 1e3 / (double)freq,
                    (double)(int64_t)G64(pacer + 0x218) * 1e3 / (double)freq, (int)G32(pacer + 0x214)),
            hos_log("vi: pacer raw: now %llx f0 %llx 128 %llx e8 %llx 50 %x 210 %x 22c %x freq %llu", (unsigned long long)hos_ticks(),
                    (unsigned long long)G64(pacer + 0xf0), (unsigned long long)G64(pacer + 0x128),
                    (unsigned long long)G64(pacer + 0xe8), G32(pacer + 0x50), G32(pacer + 0x210), *(const uint8_t *)GP(pacer + 0x22c),
                    (unsigned long long)freq);
    }
}
