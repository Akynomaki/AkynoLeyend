// The F1 panel's r10 rows: what the host and the renderer make of each row's value (gpu/vk/menu_option_ids.h). No game or GPU.
#include <cassert>

#include "../../gpu/vk/menu_option_ids.h"

int main() {
    // Mouse sensitivity: row 0 leaves the - and = keys; the others are fixed percents
    assert(akyno_mouse_sens_percent(0) == 0 && akyno_mouse_sens_percent(4) == 100 && akyno_mouse_sens_percent(1) == 25);
    assert(akyno_mouse_sens_percent(8) == 300 && akyno_mouse_sens_percent(9) == 0 && akyno_mouse_sens_percent(-1) == 0);

    // DLSS model: Auto is the renderer's own choice (-1), then K, M, L and NVIDIA's default, by NGX's preset numbers
    assert(akyno_dlss_model_preset(0) == -1 && akyno_dlss_model_preset(1) == 11 && akyno_dlss_model_preset(2) == 13);
    assert(akyno_dlss_model_preset(3) == 12 && akyno_dlss_model_preset(4) == 0 && akyno_dlss_model_preset(7) == -1);

    // Menu shortcut: F1 always; Insert and Ctrl+M unless "F1 only"; Esc only with its row
    for (int row = 0; row < 3; ++row) assert(akyno_menu_opens(row, 1, 0, 0, 0));
    assert(akyno_menu_opens(0, 0, 1, 0, 0) && akyno_menu_opens(0, 0, 0, 1, 0) && !akyno_menu_opens(0, 0, 0, 0, 1));
    assert(!akyno_menu_opens(1, 0, 1, 0, 0) && !akyno_menu_opens(1, 0, 0, 1, 0) && !akyno_menu_opens(1, 0, 0, 0, 1));
    assert(akyno_menu_opens(2, 0, 0, 0, 1) && akyno_menu_opens(2, 0, 1, 0, 0));

    assert(AKYNO_OPT_MOUSE_SENS == 72);   // (after the r9 ids, still clear of the jitter's 4-6)
    return 0;
}
