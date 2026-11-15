#pragma once

#include <string_view>

namespace mkwvk {

enum class Upscaler : int { Off, CatmullRom, Lanczos, Fsr1, Fsr31, Fsr31Native, Dlss, Dlaa, Fsr4, Fsr4Native, Count };

inline constexpr struct {
    std::string_view key;
    const char* label;
} upscalers[] = {
    {"off", "Off"}, {"catmull-rom", "Catmull-Rom"}, {"lanczos", "Lanczos"}, {"fsr", "AMD FSR 1"},
    {"fsr-temporal", "AMD FSR 3.1"}, {"fsr-native-aa", "FSR 3.1 Native AA"},
    {"dlss", "NVIDIA DLSS"}, {"dlaa", "NVIDIA DLAA"},
    {"fsr4", "AMD FSR 4"}, {"fsr4-native-aa", "FSR 4 Native AA"},
};
static_assert(sizeof(upscalers) / sizeof(upscalers[0]) == int(Upscaler::Count));

inline Upscaler parse_upscaler(std::string_view key, Upscaler default_mode) {
    for (int i = 0; i < int(Upscaler::Count); ++i)
        if (key == upscalers[i].key) return Upscaler(i);
    return default_mode;
}

inline bool is_temporal(Upscaler mode) { return mode >= Upscaler::Fsr31; }
inline bool is_fsr4(Upscaler mode) { return mode == Upscaler::Fsr4 || mode == Upscaler::Fsr4Native; }
inline bool is_native_aa(Upscaler mode) {
    return mode == Upscaler::Fsr31Native || mode == Upscaler::Dlaa || mode == Upscaler::Fsr4Native;
}
inline int window_filter(Upscaler mode) { return is_temporal(mode) ? int(Upscaler::Fsr1) : int(mode); }
inline int upscaler_scale(Upscaler mode, int resolution) {
    if (is_native_aa(mode)) return 1;  // 100%
    if (is_temporal(mode) && (resolution < 2 || resolution > 4)) return 4;  // 50%
    return resolution;
}

} // namespace mkwvk
