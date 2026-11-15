// (AkynoLeyend r9) A row of the F1 panel read from AkynoLeyend_opts.ini before the panel itself has loaded it: the rows
// that decide how the device is made (GPU device, Robust buffers), as Hookshot v2.1.0 reads its own in gpu/vk/vk_main.cpp.
#pragma once
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "../../host/hos_paths.h"

namespace mkwvk {
inline int boot_option(const char* key, int otherwise) {
    FILE* f = hos_game_file("AkynoLeyend_opts.ini", "r");
    if (!f) return otherwise;
    char line[80];
    const size_t n = strlen(key);
    while (fgets(line, sizeof line, f))
        if (!strncmp(line, key, n) && line[n] == '=') otherwise = atoi(line + n + 1);
    fclose(f);
    return otherwise;
}
/// The GPU device row: 0 Auto (-1 here), else the listed device row - 1 while there is one.
inline int boot_gpu_choice(int row, int count) { return row >= 1 && row <= count ? row - 1 : -1; }
/// The Robust buffers row: 0 Auto and 2 On are on, 1 Off.
inline bool boot_robust(int row) { return row != 1; }
/// The Quality preset row's limits in MB, 0 none: textures, then the buffer mirrors (Hookshot v2.1.0 sync_preset_budgets).
inline int preset_vram_mb(int preset) {
    static const int mb[] = {0, 2200, 3600, 4800, 7500, 11000};
    return preset >= 0 && preset < 6 ? mb[preset] : 0;
}
inline int preset_mirror_mb(int preset) {
    static const int mb[] = {0, 256, 512, 1024, 2048, 3072};
    return preset >= 0 && preset < 6 ? mb[preset] : 0;
}
/// The Anisotropic filtering row: 0 the game's own, else at least 2x to 16x.
inline unsigned anisotropy_times(int row) {
    static const unsigned times[] = {0, 2, 4, 8, 16};
    return row >= 0 && row < 5 ? times[row] : 0;
}
} // namespace mkwvk
