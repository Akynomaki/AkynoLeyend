/* (AkynoLeyend r13) The F1 panel's and the FPS counter's pixels on an HDR10 swapchain (the panel's HDR row, Hookshot v2.1.0's).
   Both are drawn by the CPU as 8-bit sRGB and copied over the window's image; on an HDR10 image (PQ, Rec. 2020, 10 bits a
   channel) the same bytes would be read as PQ codes. Each pixel is encoded as shaders/hdr_encode.comp encodes the picture,
   without the highlights' expansion: sRGB to linear, Rec. 709's primaries to Rec. 2020's (ITU-R BT.2087), white at the paper
   white, PQ (SMPTE ST 2084). No Vulkan here: tests compile it alone. */
#pragma once
#include <math.h>
#include <stdint.h>

static inline float akyno_hdr10_srgb_to_linear(float c) {
    return c <= 0.04045f ? c / 12.92f : powf((c + 0.055f) / 1.055f, 2.4f);
}

/* nits (0 to 10000) as a PQ signal, 0 to 1 */
static inline float akyno_hdr10_pq(float nits) {
    const float m1 = 0.1593017578125f, m2 = 78.84375f, c1 = 0.8359375f, c2 = 18.8515625f, c3 = 18.6875f;
    float l = nits / 10000.0f;
    l = powf(l < 0.0f ? 0.0f : l > 1.0f ? 1.0f : l, m1);
    return powf((c1 + c2 * l) / (1.0f + c3 * l), m2);
}

static inline uint32_t akyno_hdr10_code(float linear, float white_nits) {
    const float v = akyno_hdr10_pq((linear < 0.0f ? 0.0f : linear) * white_nits) * 1023.0f + 0.5f;
    return v >= 1023.0f ? 1023u : (uint32_t)v;
}

/* An 8-bit sRGB pixel as a 10:10:10:2 HDR10 word with its white at white_nits: red in the low bits
   (VK_FORMAT_A2B10G10R10_UNORM_PACK32) when red_low, else blue (VK_FORMAT_A2R10G10B10_UNORM_PACK32). */
static inline uint32_t akyno_hdr10_pixel(unsigned r, unsigned g, unsigned b, float white_nits, int red_low) {
    const float lr = akyno_hdr10_srgb_to_linear((float)r / 255.0f), lg = akyno_hdr10_srgb_to_linear((float)g / 255.0f),
                lb = akyno_hdr10_srgb_to_linear((float)b / 255.0f);
    const uint32_t cr = akyno_hdr10_code(0.6274f * lr + 0.3293f * lg + 0.0433f * lb, white_nits);
    const uint32_t cg = akyno_hdr10_code(0.0691f * lr + 0.9195f * lg + 0.0114f * lb, white_nits);
    const uint32_t cb = akyno_hdr10_code(0.0164f * lr + 0.0880f * lg + 0.8956f * lb, white_nits);
    return 3u << 30 | (red_low ? cb << 20 | cg << 10 | cr : cr << 20 | cg << 10 | cb);
}

/* The paper white and the peak the HDR rows may hold, in nits (the shader's and the game's limits) */
static inline int akyno_hdr_white(int nits) { return nits < 80 ? 80 : nits > 500 ? 500 : nits; }
static inline int akyno_hdr_peak(int nits) { return nits < 400 ? 400 : nits > 10000 ? 10000 : nits; }
