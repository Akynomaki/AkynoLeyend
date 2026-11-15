// The F1 panel's r9 rows: what the host makes of each row's value (gpu/vk/menu_option_ids.h). No game or GPU.
#include <cassert>
#include <cmath>

#include "../../gpu/vk/menu_option_ids.h"

int main() {
    // Stick dead zone: row 0 is XInput's own 7849, the others a share of the axis
    assert(akyno_stick_axis(7849, 0) == 0 && akyno_stick_axis(7850, 0) == 7850 && akyno_stick_axis(-7850, 0) == -7850);
    assert(akyno_stick_axis(1638, 1) == 0 && akyno_stick_axis(1639, 1) == 1639);
    assert(akyno_stick_axis(9830, 5) == 0 && akyno_stick_axis(9831, 5) == 9831);
    assert(akyno_stick_axis(-32768, 0) == -32767);            // (no value past the other side's)
    assert(akyno_stick_axis(8000, 9) == 8000 && akyno_stick_axis(8000, -1) == 8000);   // (an unknown row: the default)

    // Rumble strength: percent of the game's, off at 0, never past the motor's range
    assert(akyno_rumble(40000, 100) == 40000 && akyno_rumble(40000, 0) == 0 && akyno_rumble(40000, 50) == 20000);
    assert(akyno_rumble(60000, 150) == 65535 && akyno_rumble(60000, 900) == 65535 && akyno_rumble(60000, -5) == 0);

    // Volume: the squared curve, full at 100
    assert(akyno_volume_gain(100) == 1.0f && akyno_volume_gain(0) == 0.0f && akyno_volume_gain(250) == 1.0f);
    assert(std::fabs(akyno_volume_gain(50) - 0.25f) < 1e-6f);

    // Game frame rate cap: the row's rates; anything else is the console's 60
    assert(akyno_fps_cap(0) == 60 && akyno_fps_cap(1) == 90 && akyno_fps_cap(2) == 120 && akyno_fps_cap(3) == 144);
    assert(akyno_fps_cap(4) == 165 && akyno_fps_cap(5) == 240 && akyno_fps_cap(6) == 60 && akyno_fps_cap(-1) == 60);

    // The ids stay clear of the ones already answered (0-3 the panel, 4-6 the upscalers' jitter)
    assert(AKYNO_OPT_PAD_BACKGROUND == 64 && AKYNO_OPT_MUTE_BACKGROUND == 71);
    return 0;
}
