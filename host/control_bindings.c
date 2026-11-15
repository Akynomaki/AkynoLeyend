/* Controller binding support adapted from Hookshot v2.0.14 (GPL-3.0).
   Defaults match the existing AkynoLeyend input layout. */
#include "hos.h"
#include "hos_paths.h"
#include "win_path.h"
#include "../gpu/vk/vk_api.h"
#include <stdlib.h>
#include <string.h>
#define fopen hos_path_fopen
static const char *const bind_names[HOS_KEY_N] = {"a", "b", "x", "y", "ls", "rs", "l", "r", "zl", "zr", "plus",
                                                  "minus", "left", "up", "right", "down", "move_up", "move_down",
                                                  "move_left", "move_right", "cam_up", "cam_down", "cam_left",
                                                  "cam_right"};
static const signed char pad_default[HOS_SW_N] = {
    HOS_PAD_EAST, HOS_PAD_SOUTH, HOS_PAD_NORTH, HOS_PAD_WEST, HOS_PAD_LSTICK, HOS_PAD_RSTICK, HOS_PAD_LSHOULDER,
    HOS_PAD_RSHOULDER, HOS_PAD_LTRIGGER, HOS_PAD_RTRIGGER, HOS_PAD_START, HOS_PAD_BACK, HOS_PAD_LEFT, HOS_PAD_UP,
    HOS_PAD_RIGHT, HOS_PAD_DOWN};
/* (the keys of totk-pc-recomp's docs/controls.md, github.com/valentderah/totk-pc-recomp, MIT; plus Enter for Plus; the
   mouse's left button Y, attack, and right button ZL, shield and lock-on, as before; WASD the left stick, the arrows or
   IJKL the camera) */
static const unsigned char key_default[HOS_KEY_N][2] = {
    {'E'}, {VK_SHIFT}, {VK_SPACE}, {VK_LBUTTON}, {VK_CONTROL}, {'C'}, {'Q'}, {'R'}, {'Z', VK_RBUTTON}, {'X', 'F'},
    {VK_TAB, VK_RETURN}, {'M'}, {'1'}, {'2'}, {'3'}, {'4'}, {'W'}, {'S'}, {'A'}, {'D'}, {VK_UP, 'I'}, {VK_DOWN, 'K'},
    {VK_LEFT, 'J'}, {VK_RIGHT, 'L'}};
static volatile LONG pad_bind[HOS_SW_N], key_bind[HOS_KEY_N][2];   /* (the menu changes them as the game reads them) */

static void binds_default(void) {
    for (int i = 0; i < HOS_KEY_N; i++) {
        if (i < HOS_SW_N) InterlockedExchange(&pad_bind[i], pad_default[i]);
        for (int k = 0; k < 2; k++) InterlockedExchange(&key_bind[i][k], key_default[i][k]);
    }
}

static void binds_load(void) {
    static volatile LONG state;   /* 0 not read, 1 being read, 2 read */
    if (state == 2) return;
    if (InterlockedCompareExchange(&state, 1, 0) != 0) {
        while (state != 2) Sleep(0);
        return;
    }
    binds_default();
    char path[HOS_FS_PATH_CAP];
    const DWORD len = hos_game_path_a(path, HOS_FS_PATH_CAP);
    char *slash = len ? (strrchr(path, 92) ? strrchr(path, 92) : strrchr(path, 47)) : NULL;   /* (linux: '/') */
    FILE *f = NULL;
    if (slash) {
        snprintf(slash + 1, (size_t)(path + HOS_FS_PATH_CAP - slash - 1), "AkynoLeyend_opts.ini");
        f = fopen(path, "r");
    }
    int changed = 0;
    if (f) {
        char line[80];
        int version = 0, had_keys = 0;   /* (options_version: 3 since the mouse's buttons are bindings) */
        while (fgets(line, sizeof line, f)) {
            char *eq = strchr(line, '=');
            if (!eq) continue;
            *eq = 0;
            if (!strcmp(line, "options_version")) version = atoi(eq + 1);
            const int pad = !strncmp(line, "pad_", 4), keys = !strncmp(line, "key_", 4);
            had_keys |= keys;
            for (int i = 0; (pad || keys) && i < HOS_KEY_N; i++) {
                if (strcmp(line + 4, bind_names[i]) || (pad && i >= HOS_SW_N)) continue;
                changed++;
                if (pad) {
                    const int v = atoi(eq + 1);
                    pad_bind[i] = v >= 0 && v < HOS_PAD_N ? v : -1;
                } else {
                    const char *comma = strchr(eq + 1, ',');
                    const int a = atoi(eq + 1), b = comma ? atoi(comma + 1) : 0;
                    key_bind[i][0] = a > 0 && a < 256 ? a : 0;
                    key_bind[i][1] = b > 0 && b < 256 ? b : 0;
                }
            }
        }
        fclose(f);
        /* An options file from before version 3 wrote key_y and key_zl without the mouse's buttons, which pressed Y and ZL
           by themselves then: they go into the second slot when it is empty and no other control has them */
        if (version < 3 && had_keys) {
            static const int mouse_to[2][2] = {{HOS_SW_Y, VK_LBUTTON}, {HOS_SW_ZL, VK_RBUTTON}};
            for (int m = 0; m < 2; m++) {
                int taken = 0;
                for (int i = 0; i < HOS_KEY_N; i++)
                    for (int k = 0; k < 2; k++) taken |= key_bind[i][k] == mouse_to[m][1];
                if (!taken && !key_bind[mouse_to[m][0]][1]) key_bind[mouse_to[m][0]][1] = mouse_to[m][1];
            }
        }
    }
    if (changed) hos_log("hid: %d controls from AkynoLeyend_opts.ini", changed);
    InterlockedExchange(&state, 2);
}
int hos_binding(int set, int button, int slot) {
    binds_load();
    if (button < 0 || button >= (set == HOS_BIND_PAD ? HOS_SW_N : HOS_KEY_N) || slot < 0 || slot > 1)
        return set == HOS_BIND_PAD ? -1 : 0;
    return set == HOS_BIND_PAD ? (slot ? -1 : (int)pad_bind[button]) : (int)key_bind[button][slot];
}
/* A gamepad input moved to another button gives that one this button's old input (one button an input, none left
   without); a key moved to it is taken from the others */
void hos_bind(int set, int button, int slot, int code) {
    binds_load();
    if (button < 0) {
        binds_default();
        return;
    }
    if (button >= (set == HOS_BIND_PAD ? HOS_SW_N : HOS_KEY_N) || slot < 0 || slot > 1) return;
    if (set == HOS_BIND_PAD) {
        if (slot || code < -1 || code >= HOS_PAD_N) return;
        const LONG old = pad_bind[button];
        for (int i = 0; i < HOS_SW_N; i++)
            if (i != button && code >= 0 && pad_bind[i] == code) InterlockedExchange(&pad_bind[i], old);
        InterlockedExchange(&pad_bind[button], code);
    } else {
        if (code < 0 || code > 255) return;
        for (int i = 0; i < HOS_KEY_N; i++)
            for (int k = 0; k < 2; k++)
                if (code && key_bind[i][k] == code) InterlockedExchange(&key_bind[i][k], 0);
        InterlockedExchange(&key_bind[button][slot], code);
    }
}


uint64_t hos_map_pad(uint64_t raw) {
    binds_load();
    uint64_t buttons = 0;
    for (int i = 0; i < HOS_SW_N; ++i) {
        const int code = (int)pad_bind[i];
        if (code >= 0 && code < HOS_PAD_N && (raw & (1ull << code))) buttons |= 1ull << i;
    }
    return buttons;
}
int hos_bound_key(int action, int (*down)(int)) {
    binds_load();
    if (action < 0 || action >= HOS_KEY_N || !down) return 0;
    return (key_bind[action][0] && down((int)key_bind[action][0])) ||
           (key_bind[action][1] && down((int)key_bind[action][1]));
}
