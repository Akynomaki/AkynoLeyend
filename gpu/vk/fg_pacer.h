// (AkynoLeyend 0.4.5-test.1) When the display thread shows each frame of a batch (the made frames, then the game's), out
// of vk_framegen.cpp so it can run without a GPU (tests/native/fg_pacer_test.cpp). Hookshot's line, kept: every frame has
// its place on an even line, the game's recent frame time apart, a frame early waiting for it, never more than about one
// game frame behind. Three rules after MFG-Unlocker's sdk_pacing_meter.h (ideas, not its code):
//   - an isolated long frame (2.5 times the average, at most two in a row) is left out of the average: one 60 ms frame
//     no longer drew the line apart for the next ten;
//   - the batch's first frame goes out when the GPU has made it (vk_framegen.cpp waits for that), and a line that fell
//     behind starts again from then, with no run of frames to catch up;
//   - how long the GPU takes to make a batch is measured, and the line may sit that much later, and half a shown frame
//     more: frames made late no longer met a line drawn as if they were ready at the hand-over, and went out bunched
//     (tests/native/fg_pacer_test.cpp measures it against 0.4.5's line). A line that sits later than it must (the
//     first frame of each batch made and waiting for its place) comes nearer by a quarter of that wait each batch:
//     without it, every late batch moved the line later and nothing brought it back, up to 16 ms later than needed.
// Times are steady_clock nanoseconds.
#pragma once

#include <algorithm>
#include <cstdint>

namespace fgpace {

class Pacer {
  public:
    static constexpr int64_t kMs = 1000000;

    /// A batch handed over at `at`, `shown` frames to show (made + 1)
    void batch(int64_t at, int shown) {
        if (last_at_) {
            const int64_t d = at - last_at_;
            if (d > 0 && d < 100 * kMs) {
                if (d > interval_ * 5 / 2 && hitch_run_ < 2)
                    hitch_run_++;
                else
                    hitch_run_ = 0, interval_ = (interval_ * 7 + std::clamp<int64_t>(d, 4 * kMs, 50 * kMs)) / 8;
            }
        }
        last_at_ = at;
        at_ = at;
        step_ = interval_ / std::max(shown, 1);
    }
    /// The GPU was done with the batch at `ready` (0: not known)
    void ready(int64_t ready) {
        if (!ready) return;
        const int64_t lag = ready - at_;
        if (lag >= 0 && lag < 50 * kMs) lag_ = (lag_ * 7 + lag) / 8;
    }
    /// When the next frame of the batch goes out, at `now` or later (pace off: now). first: the batch's first frame, asked
    /// once the GPU has made the batch: a line that waits for it is drawn a quarter of the wait nearer, batch by batch
    int64_t due(int64_t now, bool pace, bool first = false) const {
        int64_t d = pace ? next_show_ : now;
        const int64_t bound = at_ + lag_ + interval_ + step_ * 3 / 2;
        if (d > bound) d = bound;
        if (first && d > now) d -= (d - now) / 4;
        return d < now ? now : d;
    }
    /// A frame went out at t
    void shown(int64_t t) { next_show_ = t + step_; }

    int64_t interval() const { return interval_; }
    int64_t step() const { return step_; }
    int64_t lag() const { return lag_; }

  private:
    int64_t interval_ = 16666667, last_at_ = 0, at_ = 0, step_ = 16666667, lag_ = 0, next_show_ = 0;
    int hitch_run_ = 0;
};

} // namespace fgpace
