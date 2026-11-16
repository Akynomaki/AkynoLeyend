// (AkynoLeyend 0.4.9) Decorative vegetation and effects left out: the launcher's Graphics > "Vegetação e efeitos" (AKYNO_LITE_SCENE=1,
// akynoleyend/graphics.py), read once when the game starts, so a change applies at the next start. Unset or any other
// value: every draw as before, nothing else is looked at.
//
// The programs are the game's GPU-culled foliage: indirect mesh draws whose instances a compute pass lays out, each group
// drawn in two or three passes (shadow, depth, colour) with its own program per pass, so the shadows go with the plants.
// Catalogued on 2026-11-15 with RX_VK_DRAW_STATS and RX_VK_SKIP_FILE in Hyrule Field and the Kokiri Forest, the EXE lifted
// by 0.4.8: grass, ferns, ground plants, tufts and moss. Trees, trunks, rocks, fences, houses, characters and the light
// trail are other programs and stayed in both places. Not yet checked in play: the grass and bushes that can be cut.
// Kept out on purpose (they are tree crowns: the trees were left bare):
//   6b4dea601798c255 e28434e1afe8321a (broad trees), 3b8c07f2eb4bb7d9 f93c1d64658c850b (the Kokiri's small trees).
// Effects, catalogued the same day in the Kokiri Forest with the draw stats' blend, depth and instance columns: the
// falling leaves and the fireflies (trail and glow); Link, Navi, the ground mist, the light and the interface stayed.
// Kept out on purpose: 701ae221d88b2908, the ground mist (without it the ground shows white patches).
// C and C++.
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

static const uint64_t akyno_lite_scene_keys[] = {
    // near grass carpet
    0x02ee95fbf9e0050dULL, 0x6afe3fda3f4b1752ULL, 0xd905f52b7517c681ULL,
    0x739acd678ae08655ULL, 0xa6a688bae3c9b80cULL, 0xb0b3b40244c71ec7ULL,
    0x3bde059fb051af1fULL, 0x6b7f79e2ff3a2746ULL, 0xd4abbcb4c2140609ULL,
    // distant grass
    0x68642bb810ee3e7cULL, 0xcb71f79f6129aab8ULL,
    0x3cb7682790143836ULL, 0x4f0c0b40ab3a32cdULL,
    0x42fe74fc522a042bULL, 0x586ceacc2986610aULL, 0xee79bf7bb9467172ULL,
    // ferns, ground plants and moss (most of the Kokiri Forest's floor)
    0x9d8403e2e566c773ULL, 0xc36a4f3f667c886aULL, 0x22063ecfa481a731ULL, 0x879fe82ef602ab53ULL, 0xd8e59341cf4f629cULL,
    0x50f7cddcf3bb96bdULL, 0x5ba7cf23d6857836ULL, 0x89ca750f9852b7caULL,
    0x3e56f2fd4b0c4e1aULL,
    0xccf4f709e0deeac1ULL,
    0x28dd2baa17ba10e1ULL, 0x8e2f7af4245747efULL, 0x51183fe750d5d0c8ULL,
    0x2918fc795610b2d4ULL,
    0x43ec86f35fd937b9ULL, 0x8a8304edb7bdf4bfULL,
    // effects: falling leaves (shadow and depth, colour), fireflies (trail, glow)
    0xa37e5fc5f233e1baULL, 0x5bea5f63bbd3d665ULL,
    0xcd9e931fd94b96d8ULL, 0xbd375eeff1343782ULL,
};

/// Whether a draw of this program is left out with the option on.
static inline int akyno_lite_scene_key(uint64_t key) {
    for (size_t i = 0; i < sizeof akyno_lite_scene_keys / sizeof akyno_lite_scene_keys[0]; i++)
        if (akyno_lite_scene_keys[i] == key) return 1;
    return 0;
}

/// AKYNO_LITE_SCENE's value as the option: exactly "1" is on.
static inline int akyno_lite_scene_value(const char* value) {
    return value && value[0] == '1' && value[1] == 0;
}
