// (AkynoLeyend 0.4.5-test.1) The F1 panel's Frame generation at "Dinâmica": how many frames to show per game frame, chosen
// each game frame by fg_dynamic_count.h (MFG-Unlocker's controller, MIT) so the frames shown follow a target, up to the
// "Máximo" row. The target is the "Alvo" row, or, at Monitor, just under the window's display refresh (138 at 144 Hz, 116
// at 120, 59 at 60), as MFG-Unlocker's xemfg_dynamic.h picks it. 1X (the game's frames alone) is allowed: when the game
// reaches the target by itself nothing is made. Nothing here calls Windows or Vulkan: tests/native/fg_dynamic_test.cpp.
#pragma once

#include <algorithm>
#include <cmath>

#include "fg_dynamic_count.h"

namespace fgdyn {

constexpr int kMaxFrames = 6;   // (the Máximo row: 2x to 6x)
constexpr int kTargetRows = 7;  // (the Alvo row: Monitor, then these rates)
inline int target_row_fps(int row) {
    static const int fps[kTargetRows] = {0, 60, 90, 120, 144, 165, 240};
    return fps[row >= 0 && row < kTargetRows ? row : 0];
}

/// The frames shown per second wanted: the Alvo row's, or at Monitor just under the refresh (60 Hz when it is unknown)
inline double target_fps(int row, double refresh_hz) {
    if (const int fps = target_row_fps(row)) return fps;
    const double r = refresh_hz > 0.0 ? refresh_hz : 60.0;
    return std::floor(r - r * r / 3600.0);
}

class Dynamic {
  public:
    /// One game frame: frame_ms since the one before. The frames to show for it (1: the game's alone, up to max_frames)
    int update(double now_ms, double frame_ms, double refresh_hz, int target_row, int max_frames) {
        const int most = std::clamp(max_frames, 2, kMaxFrames);
        if (frames_ <= 0) frames_ = most;   // (from the most frames, as MFG-Unlocker starts)
        frames_ = std::min(frames_, most);
        XeFG_DynamicCount::Sample s;
        s.nowMs = now_ms;
        s.frameMs = frame_ms;
        s.waitMs = 0.0;   // (what the game sleeps is the host's, nn_vi.c: not known here, so all of the frame counts as work)
        s.targetFps = target_fps(target_row, refresh_hz);
        s.refreshFps = refresh_hz;
        s.limitFps = 0.0;
        s.maxCount = most - 1;
        s.currentCount = frames_ - 1;
        s.rounding = 1;   // (nearest)
        s.minCount = 0;   // (1X allowed)
        target_ = s.targetFps;
        frames_ = count_.Update(s) + 1;
        return frames_;
    }
    /// Frame generation turned off and on, or the picture's size changed: the averages start over, what was learned stays
    void restart() { count_.Restart(); }
    /// The mode left: everything
    void reset() { count_.Reset(); frames_ = 0; }
    int frames() const { return frames_; }
    double target() const { return target_; }
    double presented() const { return count_.PresentedFps(); }
    /// Why the last update changed the count ("" when it did not)
    const char* reason() const {
        static const char* t[] = {"", "up", "down", "try down", "undo", "no gain, back"};
        return t[std::clamp(int(count_.LastReason()), 0, 5)];
    }

  private:
    XeFG_DynamicCount count_;
    int frames_ = 0;
    double target_ = 0.0;
};

} // namespace fgdyn
