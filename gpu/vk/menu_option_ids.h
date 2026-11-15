/* (AkynoLeyend r9) The F1 panel's rows the host asks the renderer for (rx_option, host/rx_backend.c): the rows are Hookshot
   v2.1.0's (GPL-3.0), which numbers them from 4 in gpu/vk/vk_api.h; here 4 to 6 are the temporal upscalers' jitter
   (vk_fsr_options.h), so these start at 64, and vk_api.h is left as it is. C and C++. */
#pragma once

enum {
    AKYNO_OPT_PAD_BACKGROUND = 64, /* the controllers count while another window has the focus */
    AKYNO_OPT_MOUSE_INVERT,        /* the captured mouse's up and down swapped */
    AKYNO_OPT_RUMBLE,              /* the rumble's strength in percent, 0 off */
    AKYNO_OPT_STICK_DEAD_ZONE,     /* 0 the default (24%), then 5, 10, 15, 20, 30 percent */
    AKYNO_OPT_INVERT_CAM_X,        /* the right stick's left and right swapped */
    AKYNO_OPT_INVERT_CAM_Y,        /* the right stick's up and down swapped */
    AKYNO_OPT_VOLUME,              /* 0 to 100 */
    AKYNO_OPT_MUTE_BACKGROUND,     /* no sound while another window has the focus */
    AKYNO_OPT_MOUSE_SENS,          /* (r10) 0 the - and = keys' value (<user>/mouse_sens.txt), else akyno_mouse_sens_percent */
    /* (r12, Hookshot v2.1.0's Motion page: host/pad_sdl.c, host/hos_motion.h; its HOS_OPT_GYRO* 18-23) */
    AKYNO_OPT_GYRO,                /* Motion controls: 1 on (the default), 0 the pad lying still */
    AKYNO_OPT_GYRO_SENS_X,         /* percent, 10 to 600, 100 the console's */
    AKYNO_OPT_GYRO_SENS_Y,         /* percent, 10 to 300 */
    AKYNO_OPT_GYRO_INV_X,
    AKYNO_OPT_GYRO_INV_Y,
    AKYNO_OPT_GYRO_DEADZONE,       /* 0 low, 1 standard (the console's), 2 high */
    AKYNO_OPT_MIC,                 /* (r12, host/nn_audio_in.c) 0 off, 1 the system's default microphone */
    /* (r13, Hookshot v2.1.0's options 5, 10, 6 and 45; their hooks in the lifted code: nx2/oot_patches.py PANEL_HOOKS) */
    AKYNO_OPT_TEXT_SPEED,          /* 0 the game's, 1 2x, 2 4x, 3 the page at once (host/nn_vi.c hos_text_scale) */
    AKYNO_OPT_TEXT_SIZE,           /* 0 the game's, 1 110%, 2 125%, 3 150%, 4 175% (host/oot_text_size.c) */
    AKYNO_OPT_MOUSE_NATIVE,        /* the captured mouse turns the player camera's own angles (host/mouse_native.c) */
    AKYNO_OPT_CAM_NO_CENTERING,    /* the camera does not swing back behind Link by itself */
    /* (r13, Hookshot v2.1.0's HOS_OPT_HDR_NATIVE, _PEAK and _WHITE: host/nn_vi.c QueryDisplayHdrStatus and
       QueryDisplayHdrPaperWhite) whether the game is told its display is HDR10 (the HDR row at Native on an HDR10
       swapchain), and the peak and the paper white it is told, in nits */
    AKYNO_OPT_HDR_NATIVE,
    AKYNO_OPT_HDR_PEAK,
    AKYNO_OPT_HDR_WHITE,
    /* (0.4.5-test.1, unified: its hook in the lifted code, nx2/oot_patches.py patch_render_distance) */
    AKYNO_OPT_RENDER_DISTANCE      /* 0 the game's own far plane, else akyno_render_distance's metres (host/nn_vi.c) */
};

/* (r10, Hookshot v2.1.0's Mouse sensitivity row in fixed steps) The row's sensitivity in percent of the default, 0 for row 0:
   the - and = keys then keep setting it, as before. */
static inline int akyno_mouse_sens_percent(int row) {
    static const int steps[9] = {0, 25, 50, 75, 100, 125, 150, 200, 300};
    return steps[row >= 0 && row < 9 ? row : 0];
}

/* (0.4.5-test.1, unified) The Render distance row: the far plane of the game's cameras in metres, 0 for row 0 (the game's own). Rows
   go from the longest down, so each step right draws less and costs less. */
static inline int akyno_render_distance(int row) {
    static const int metres[9] = {0, 2500, 1200, 700, 400, 250, 150, 100, 60};
    return metres[row >= 1 && row < 9 ? row : 0];
}

/* (r10, Hookshot v2.1.0's DLSS model row) The row's DLSS preset (NVSDK_NGX_DLSS_Hint_Render_Preset_*: K 11, M 13, L 12,
   NVIDIA's default 0); -1 for row 0, Auto: K, or M at half the output's size and below (vk_fsr_sdk.cpp dlss_preset). */
static inline int akyno_dlss_model_preset(int row) {
    static const int presets[5] = {-1, 11, 13, 12, 0};
    return presets[row >= 0 && row < 5 ? row : 0];
}

/* (r10, Hookshot v2.1.0's Menu shortcut row) Which keys open the F1 panel: 0 F1, Insert or Ctrl+M; 1 F1 only (Insert is left
   to an overlay); 2 also Esc, as a PC game's pause menu. */
static inline int akyno_menu_opens(int row, int f1, int insert, int ctrl_m, int esc) {
    if (row == 1) return f1;
    return f1 || insert || ctrl_m || (row == 2 && esc);
}

/* A stick axis's value past the Stick dead zone row's cut (Hookshot v2.1.0, host/nn_hid.c hos_stick_axis), 0 inside it. */
static inline int akyno_stick_axis(int value, int zone) {
    static const int cut[6] = {7849, 1638, 3277, 4915, 6553, 9830};
    const int a = value < -32767 ? -32767 : value, t = cut[zone >= 0 && zone < 6 ? zone : 0];
    return (a > t || a < -t) ? a : 0;
}

/* The Rumble strength row over a motor's amplitude (0..65535). */
static inline unsigned akyno_rumble(unsigned amplitude, int percent) {
    const unsigned long long v = (unsigned long long)amplitude * (unsigned)(percent < 0 ? 0 : percent > 150 ? 150 : percent) / 100;
    return v > 65535 ? 65535u : (unsigned)v;
}

/* The Volume row's percent as a gain, on a squared curve so the slider's steps sound about even (Hookshot v2.1.0,
   host/nn_audio.c audio_volume_curve): 50% is a quarter, -12 dB. */
static inline float akyno_volume_gain(int percent) {
    const float v = (float)(percent < 0 ? 0 : percent > 100 ? 100 : percent) / 100.0f;
    return v * v;
}

/* The Game frame rate cap row (frame_rate_cap= in the options file, read by the host at the start): the rates. */
static inline int akyno_fps_cap(int row) {
    static const int caps[6] = {60, 90, 120, 144, 165, 240};
    return caps[row >= 0 && row < 6 ? row : 0];
}
