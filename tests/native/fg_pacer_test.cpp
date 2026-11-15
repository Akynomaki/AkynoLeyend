// (0.4.5-test.1) The display thread's pacer (gpu/vk/fg_pacer.h) against a simulated game and GPU, beside the pacer of
// 0.4.5 (Hookshot's, kept here as it was in vk_framegen.cpp display_main). The display thread takes each batch when it is
// handed over; with the new pacer it waits for the GPU to make it, as vk_framegen.cpp now does; the old one handed the
// present over at once, and the GPU showed it when the batch was made. A present costs 0.3 ms. No GPU: none of this
// says the frames looked even on a screen.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

#include "fg_pacer.h"

namespace {

constexpr int64_t kMs = fgpace::Pacer::kMs;
unsigned rng = 777;
double noise() {
    rng = rng * 1103515245u + 12345u;
    return ((rng >> 8) & 0xffff) / 32767.5 - 1.0;
}

/// 0.4.5's pacer: the interval's average over every frame under 100 ms, and the line bounded by the hand-over alone
struct OldPacer {
    int64_t interval = 16666667, last_at = 0, at = 0, step = 16666667, next_show = 0;
    void batch(int64_t a, int shown) {
        if (last_at) {
            const int64_t d = a - last_at;
            if (d > 0 && d < 100 * kMs) interval = (interval * 7 + std::clamp<int64_t>(d, 4 * kMs, 50 * kMs)) / 8;
        }
        last_at = at = a;
        step = interval / shown;
    }
    int64_t due(int64_t now) const {
        int64_t d = next_show;
        if (d < now) d = now;
        if (d > at + interval + step) d = at + interval + step;
        return d;
    }
};

struct Result {
    double sd_ms;     // spacing of the frames on screen: its standard deviation
    int bunched;      // frames on screen under a third of the step after the one before
    double mean_ms;
    double latency_ms;   // from the hand-over to the screen, on average
    double least_ms;     // the least an even line can have: the GPU's time to make the batch, then the frames a step apart
};

struct Case {
    double mean, jitter, gpu_lag;
    int shown, hitch_every = 0;
    double hitch_ms = 0;
};

Result run(const Case& c, bool old, int frames = 3000) {
    rng = 777;   // (the same game for both pacers)
    fgpace::Pacer p;
    OldPacer o;
    int64_t at = 0, t = 0, last_screen = 0;
    std::vector<double> gaps;
    int bunched = 0;
    double latency = 0, made = 0;
    int counted = 0, batches = 0;
    for (int i = 0; i < frames; i++) {
        double ms = c.mean + c.jitter * noise();
        if (c.hitch_every && i % c.hitch_every == c.hitch_every - 1) ms += c.hitch_ms;
        at += (int64_t)(ms * kMs);
        const int64_t ready = at + (int64_t)(c.gpu_lag * (1.0 + 0.3 * noise()) * kMs);
        t = std::max(t, at);
        if (i > 50) made += (ready - at) / (double)kMs, batches++;
        if (old) {
            o.batch(at, c.shown);
        } else {
            p.batch(at, c.shown);
            t = std::max(t, ready);
            p.ready(ready);
        }
        for (int k = 0; k < c.shown; k++) {
            t = std::max(t, old ? o.due(t) : p.due(t, true, k == 0));
            const int64_t screen = std::max(t, ready);   // (the GPU shows it once the batch is made)
            if (last_screen && i > 50) {
                const double g = (screen - last_screen) / (double)kMs;
                gaps.push_back(g);
                if (g < (old ? o.step : p.step()) / (3.0 * kMs)) bunched++;
            }
            last_screen = screen;
            if (i > 50) latency += (screen - at) / (double)kMs, counted++;
            if (old) o.next_show = t + o.step;
            else p.shown(t);
            t += kMs * 3 / 10;
        }
    }
    double sum = 0, sq = 0;
    for (double g : gaps) sum += g;
    const double m = sum / gaps.size();
    for (double g : gaps) sq += (g - m) * (g - m);
    return {std::sqrt(sq / gaps.size()), bunched, m, latency / counted, made / batches + (c.shown - 1) / 2.0 * m};
}

int failures = 0;
/// The new pacer at least as even as the old one (5% of slack on the deviation), no more bunched, at the same rate, and on
/// average at most one shown frame later than the least an even line can have (0.4.5's could be earlier only by showing a
/// late batch's frames at once)
void compare(const char* name, const Case& c) {
    const Result n = run(c, false), o = run(c, true);
    const bool ok = n.sd_ms <= o.sd_ms * 1.05 + 0.05 && n.bunched <= o.bunched &&
                    std::fabs(n.mean_ms - o.mean_ms) < 0.05 * o.mean_ms && n.latency_ms <= std::max(o.latency_ms, n.least_ms) + n.mean_ms;
    printf("%-38s new: sd %.2f ms, bunched %4d, latency %4.1f ms (least %4.1f) | 0.4.5: sd %.2f, bunched %4d, latency %4.1f | %s\n", name,
           n.sd_ms, n.bunched, n.latency_ms, n.least_ms, o.sd_ms, o.bunched, o.latency_ms, ok ? "ok" : "FAIL");
    failures += !ok;
}

} // namespace

int main() {
    // Hookshot's case: frames 12 to 28 ms apart around 19
    compare("19 +- 8 ms, GPU 3 ms, 2x", {19, 8, 3, 2});
    compare("19 +- 8 ms, GPU 3 ms, 3x", {19, 8, 3, 3});
    // GPU bound: each batch made 10 to 14 ms after the hand-over
    compare("16.7 ms steady, GPU 12 ms, 2x", {16.667, 0.3, 12, 2});
    compare("16.7 ms steady, GPU 12 ms, 4x", {16.667, 0.3, 12, 4});
    compare("25 +- 3 ms, GPU 18 ms, 4x", {25, 3, 18, 4});
    // 40 fps with a 60 ms frame every 50 (streaming): the average keeps out of it
    compare("25 +- 2 ms, 60 ms frame every 50, 4x", {25, 2, 6, 4, 50, 60});
    compare("25 +- 2 ms, 120 ms hitch every 200, 4x", {25, 2, 6, 4, 200, 120});
    {   // An isolated long frame stays out of the average
        fgpace::Pacer p;
        int64_t at = 0;
        for (int i = 0; i < 100; i++) p.batch(at += 20 * kMs, 2);
        p.batch(at += 90 * kMs, 2);
        const bool ok = std::llabs(p.interval() - 20 * kMs) < kMs / 2;
        printf("%-40s interval %.2f ms after a 90 ms frame: %s\n", "isolated hitch", p.interval() / (double)kMs,
               ok ? "ok" : "FAIL");
        failures += !ok;
    }
    return failures ? 1 : 0;
}
