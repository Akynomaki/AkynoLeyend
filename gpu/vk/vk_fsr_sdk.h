#pragma once

#include "vk_internal.h"
#include "upscale_mode.h"

namespace mkwvk {

struct Texture;

bool fsr_sdk_requested();
Upscaler fsr_sdk_active();
bool fsr_sdk_fsr4_available();
void fsr_sdk_scene(const Texture* color, Texture* depth, uint32_t width, uint32_t height,
                   uint64_t camera, uint64_t camera_size);
bool fsr_sdk_dispatch(VkCommandBuffer cmd, const Texture& input, VkImageView input_view,
                      Texture& output, VkImageView output_view, uint32_t output_level);
int fsr_sdk_jitter(int option);
void fsr_sdk_presented();
bool fsr_sdk_before_exit();   // (NGX shut down, the GPU idle: true when DLSS was running)

} // namespace mkwvk
