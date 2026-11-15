// (0.4.5-test.1) The dynamic frame generation count (gpu/vk/fg_dynamic.h) against simulated games: a game's frame takes its
// work plus what each made frame costs the GPU, at least its frame rate cap's time. No GPU: none of this says the mode was
// tried in the game.
#include <algorithm>
#include <cmath>
#include <cstdio>

#include "fg_dynamic.h"

namespace {

struct Game {
    double work_ms;   // the game's own frame (CPU or GPU)
    double gen_ms;    // each made frame's GPU time (and as much again for the flow, once frames are made)
    double cap_fps;   // the game's frame rate cap (0: none)
    double hitch_every_s = 0, hitch_ms = 0;
};

unsigned rng = 12345;
double noise() {   // (-1..1, deterministic)
    rng = rng * 1103515245u + 12345u;
    return ((rng >> 8) & 0xffff) / 32767.5 - 1.0;
}

struct Run {
    int frames = 0, changes_late = 0, min_late = 99, max_late = 0;
    double late_ms = 0, late_at = 0;   // (time after settling, and of it at the final count)
};

Run run(const Game& g, double refresh, int target_row, int most, double seconds, double settle_s, int last_want) {
    fgdyn::Dynamic d;
    Run r;
    double now = 0, next_hitch = g.hitch_every_s * 1000;
    int frames = most, last = most;
    while (now < seconds * 1000) {
        double ms = g.work_ms * (1.0 + 0.04 * noise()) + (frames > 1 ? g.gen_ms * frames : 0.0);
        if (g.cap_fps > 0) ms = std::max(ms, 1000.0 / g.cap_fps * (1.0 + 0.01 * noise()));
        if (g.hitch_every_s > 0 && now >= next_hitch) ms += g.hitch_ms, next_hitch += g.hitch_every_s * 1000;
        now += ms;
        frames = d.update(now, ms, refresh, target_row, most);
        if (now > settle_s * 1000) {
            if (frames != last) r.changes_late++;
            r.min_late = std::min(r.min_late, frames), r.max_late = std::max(r.max_late, frames);
            r.late_ms += ms;
            if (frames == last_want) r.late_at += ms;
        }
        last = frames;
    }
    r.frames = frames;
    return r;
}

int failures = 0;
// (the controller tries one step less now and then and takes it back when it does not hold: a few changes stay, and the
// count wanted has to hold 90% of the time once settled)
void expect(const char* name, const Run& r, int want, int most_changes) {
    const double share = r.late_ms > 0 ? r.late_at / r.late_ms : 0;
    const bool ok = r.frames == want && r.changes_late <= most_changes && share >= 0.9;
    printf("%-44s %dx (want %dx), %.0f%% of the time at it, changes %d (at most %d), range %dx-%dx: %s\n", name, r.frames,
           want, share * 100, r.changes_late, most_changes, r.min_late, r.max_late, ok ? "ok" : "FAIL");
    failures += !ok;
}

} // namespace

int main() {
    // Targets: the Monitor row is just under the refresh
    if (fgdyn::target_fps(0, 144) != 138 || fgdyn::target_fps(0, 120) != 116 || fgdyn::target_fps(0, 60) != 59 ||
        fgdyn::target_fps(0, 0) != 59 || fgdyn::target_fps(3, 144) != 120) {
        printf("target_fps: FAIL\n");
        return 1;
    }
    // GPU bound at 40 fps, 1 ms a made frame: 4X shows ~133 at 144 Hz (3X ~106, 5X ~161)
    expect("40 fps, 144 Hz, up to 4x", run({25, 1, 0}, 144, 0, 4, 90, 30, 4), 4, 4);
    expect("40 fps, 144 Hz, up to 6x", run({25, 1, 0}, 144, 0, 6, 90, 30, 4), 4, 4);
    // Held at 60 by the game: at 60 Hz the game's frames alone; at 120 and 144 Hz 2X
    expect("60 fps cap, 60 Hz, up to 4x", run({8, 1, 60}, 60, 0, 4, 90, 30, 1), 1, 4);
    expect("60 fps cap, 120 Hz, up to 4x", run({8, 1, 60}, 120, 0, 4, 90, 30, 2), 2, 4);
    expect("60 fps cap, 144 Hz, up to 4x", run({8, 1, 60}, 144, 0, 4, 90, 30, 2), 2, 4);
    // 20 fps (heavy scenes on a small card): the most frames
    expect("20 fps, 144 Hz, up to 4x", run({50, 1.5, 0}, 144, 0, 4, 90, 30, 4), 4, 4);
    // The Alvo row at 120, from 40 fps at 144 Hz: 3X
    expect("40 fps, 144 Hz, target 120, up to 6x", run({25, 1, 0}, 144, 3, 6, 90, 30, 3), 3, 4);
    // A 300 ms hitch every 7 s (a shader compiled, a load) changes nothing
    expect("40 fps, 144 Hz, up to 4x, hitch every 7 s", run({25, 1, 0, 7, 300}, 144, 0, 4, 120, 30, 4), 4, 4);
    expect("60 fps cap, 120 Hz, hitch every 7 s", run({8, 1, 60, 7, 300}, 120, 0, 4, 120, 30, 2), 2, 4);
    return failures ? 1 : 0;
}
