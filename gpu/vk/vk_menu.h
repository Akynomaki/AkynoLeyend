// The Insert menu (vk_menu.cpp): options that apply while the game runs, kept in AkynoLeyend_opts.ini beside the executable.
#pragma once

#include "vk_internal.h"

namespace mkwvk {

// (out of the box every feature is off: what the game does on its own. The ini beside the executable keeps a player's choices)
struct Options {
    int framegen = 0;     // made frames: 0 off, or 2 to 8 times the game's frames; 9 Dinâmica (vk_framegen.cpp, fg_dynamic.h)
    int pace = 0;         // frames shown on an even line (vk_framegen.cpp)
    int resolution = 0;   // the 3D's: 0 Auto (the game's dynamic resolution), else 100%, 75%, 67%, 50% of its full scale (nx2/oot_patches.py)
    int upscale = 0;      // 0 off, 1 Catmull-Rom, 2 Lanczos, 3 AMD FSR 1 EASU + optional RCAS
    int output_res = 0;   // boot-time output: 0 game (2048x1152), 1 2560x1440, 2 3840x2160
    int sharpness = 0;    // 0 to 100
    int realtime = 1;     // game time follows the clock (host/nn_vi.c); 0: per frame (slower frames, slower game)
    int handheld = 0;     // the game's handheld profile: ~4 fps, softer; read once, at the start (host/nn_applet.c)
    int ultrawide = 0;    // the camera at the monitor's shape when it is wider than 16:9; read once, at the start (host/hos_main.c)
    int show_fps = 0;
    int prompts = 0;      // Auto, Switch, Xbox, PS4, PS5, Steam Deck; applies to icons after restart
    int fullscreen = 0;   // borderless, at the monitor's size: F11 is the same setting
    // (AkynoLeyend r9: rows of Hookshot v2.1.0's menu)
    int preset = 0;           // Quality preset: 0 Custom, 1 Minimum to 5 Ultra (sets rows; memory limits at the start: boot_options.h)
    int gpu_device = 0;       // 0 Auto, else the listed Vulkan device + 1; read at the start (vk_main.cpp)
    int fps_cap = 0;          // Game frame rate cap: 0 60, then 90, 120, 144, 165, 240; read at the start (host/nn_vi.c)
    int anisotropy = 0;       // 0 the game's, then at least 2x, 4x, 8x, 16x; read at the start (vk_draw.cpp)
    int robust = 0;           // Robust buffers: 0 Auto, 1 Off, 2 On; read at the start (vk_main.cpp)
    int volume = 100;         // percent (host/nn_audio.c)
    int mute_background = 0;  // no sound while another window has the focus
    int menu_size = 2;        // 1 Small, 2 Medium, 3 Large: this panel and the FPS counter
    int pad_background = 0;   // the controllers count behind other windows (host/nn_hid.c)
    int mouse_invert = 0;     // the captured mouse's up and down swapped
    int invert_cam_x = 0, invert_cam_y = 0;   // the right stick's
    int stick_dead_zone = 0;  // 0 the default (24%), then 5, 10, 15, 20, 30 percent
    int rumble = 100;         // percent of the game's rumble, 0 off, up to 150
    // (AkynoLeyend r10: more rows of Hookshot v2.1.0's menu; menu_option_ids.h)
    int dlss_model = 0;       // 0 Auto (K, M at half the output and below), 1 K, 2 M, 3 L, 4 NVIDIA's default; read at the start
    int mouse_sens = 0;       // 0 the - and = keys' value, then 25% to 300% (host/nn_hid.c)
    int menu_shortcut = 0;    // 0 F1, Insert or Ctrl+M; 1 F1 only; 2 also Esc
    // (AkynoLeyend r11, Hookshot v2.1.0: vk_reflex.cpp, vk_antilag.cpp; at once, no restart)
    int reflex = 0;           // NVIDIA Reflex: 0 Off, 1 On, 2 On + Boost (VK_NV_low_latency2)
    int antilag = 0;          // AMD Anti-Lag 2: 0 Off, 1 On (VK_AMD_anti_lag)
    // (AkynoLeyend r12, Hookshot v2.1.0's Motion page: host/pad_sdl.c and host/hos_motion.h; at once)
    int gyro = 1;             // Motion controls: aim with a pad's gyroscope where the game uses motion
    int gyro_sens_x = 100, gyro_sens_y = 100;   // percent of the console's
    int gyro_inv_x = 0, gyro_inv_y = 0;
    int gyro_deadzone = 1;    // 0 low, 1 standard, 2 high
    int mic = 1;              // (r12, host/nn_audio_in.c) the ocarina's microphone: 0 off, 1 the system's default
    // (AkynoLeyend r13, Hookshot v2.1.0: hooks in the lifted code, nx2/oot_patches.py PANEL_HOOKS; at once)
    int text_speed = 0;       // how fast dialogue prints: 0 the game's, 1 2x, 2 4x, 3 instant (host/nn_vi.c; HOS_TEXT_SPEED)
    int text_size = 0;        // dialogue, Navi and signs: 0 the game's, 1 110%, 2 125%, 3 150%, 4 175% (host/oot_text_size.c)
    int mouse_native = 0;     // the mouse turns the camera's own angles (host/mouse_native.c); 0: as the right stick
    int disable_camera_centering = 0;   // 0: stock movement-follow turning; 1: keep the player's horizontal direction
    // (AkynoLeyend r13, Hookshot v2.1.0: vk_framegen.cpp framegen_hdr; at once, the swapchain made again)
    int hdr = 0;              // HDR10 out when the display lists it: 0 off, 1 the SDR picture expanded, 2 the game's own (native) HDR
    int hdr_white = 200;      // HDR paper white, nits (the picture's white)
    int hdr_peak = 1000;      // HDR peak brightness, nits (its brightest highlights)
    // (AkynoLeyend r13, Hookshot v2.1.0: nx2/oot_patches.py's WIDE sites, vk_framegen.cpp wide_sides; at once)
    // (AkynoLeyend r13, Hookshot v2.1.0 issue 640, #1001: gpu/vk/vk_main.cpp reads mesh_shaders= as the device is made)
    int mesh_mode = 0;        // task and mesh programs: 0 Automatic, 1 Native, 2 Compute (the fallback on every GPU)
    // (0.4.5-test.1, unified: host/nn_vi.c hos_render_far, its hook nx2/oot_patches.py patch_render_distance; at once)
    int render_distance = 0;  // the cameras' far plane: 0 the game's own, else menu_option_ids.h akyno_render_distance's metres
    int wide_menus = 1;       // ultrawide: the pause, item and map menus 0 at full width (stretched), 1 in the middle 16:9 with the sides out of focus, 2 with black bars
    // (AkynoLeyend 0.4.5-test.1: Frame generation at Dinâmica, fg_dynamic.h; at once)
    int fg_max = 4;           // the most frames shown per game frame, 2 to 6
    int fg_target = 0;        // the frames per second it aims at: 0 just under the display's refresh, else 60, 90, 120, 144, 165, 240
};
extern Options opts;

void menu_init();             // (the options from the file, once)
void menu_tick();             // (each frame shown: the keys, while the game's window has the focus)
bool menu_is_open();
void menu_note_frame(bool game_frame);   // (the frame rates the FPS counter shows)
/// Over the window's image (TRANSFER_DST_OPTIMAL), w x h: the menu and the FPS counter. slot: the frame in flight, 0 to 2.
void menu_record(VkCommandBuffer cmd, VkImage dst, int slot, uint32_t w, uint32_t h);

} // namespace mkwvk
