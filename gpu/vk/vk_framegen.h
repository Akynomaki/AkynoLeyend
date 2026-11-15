// Frame interpolation (vk_framegen.cpp): made frames shown between the game's (in a window; RX_VK_FRAMEGEN=0: off).
#pragma once

#include "vk_internal.h"

namespace mkwvk {

bool framegen_on();
/// (0.4.5-test.1) The refresh of the display the game's window is on, Hz, as frame interpolation last read it (0: not yet)
int framegen_refresh_hz();
/// Records the frame's processing into the present's recording (src: the window texture's view, sw x sh, the crop
/// x, y, w, h); false when interpolation cannot run (the present goes to the window as without it)
bool framegen_record(VkCommandBuffer cmd, VkImageView src, uint32_t sw, uint32_t sh, const int crop[4]);
/// The first frame the last framegen_record made (null when it made none), w x h, GENERAL
VkImage framegen_made_image(uint32_t* w, uint32_t* h);
/// After that recording's submit (value): the display thread shows its frames
void framegen_queue(uint64_t value);
/// The window's present of an image (GENERAL, w x h; crop as above or null), vk_replay.cpp: the display thread's
// A non-null image must carry its sampled view even when interpolation is disabled.
void present_image(VkImage src, uint32_t w, uint32_t h, const int crop[4], VkImageView view);
/// The Insert menu's upscaling of a frame to the window (dw x dh), recorded: the image to show, or null when it is off
VkImage framegen_scale(VkCommandBuffer cmd, VkImageView src, VkImage image, uint32_t sw, uint32_t sh, const int crop[4], uint32_t dw, uint32_t dh);
/// (AkynoLeyend r13, Hookshot v2.1.0) Each present of the game's: ultrawide's menus, the sides to treat now (out of focus or
/// black while a menu shows)
void wide_sides_tick();
/// The picture (src: view and image, sw x sh, its crop or null) at dw x dh with those sides, GENERAL; null when no side shows
/// now or it cannot be made (then the picture as it is)
VkImage framegen_sides(VkCommandBuffer cmd, VkImageView src, VkImage image, uint32_t sw, uint32_t sh, const int crop[4], uint32_t dw, uint32_t dh);
/// (AkynoLeyend r13) The view of an image framegen_scale or framegen_sides returned; null for any other
VkImageView framegen_scaled_view(VkImage scaled);
/// (AkynoLeyend r13, Hookshot v2.1.0) The F1 panel's HDR: src's crop as a dw x dh HDR10 image (GENERAL) to copy into an HDR10
/// swapchain's image as the SDR picture is; null when it cannot be made
VkImage framegen_hdr(VkCommandBuffer cmd, VkImageView src, uint32_t sw, uint32_t sh, const int crop[4], uint32_t dw, uint32_t dh);

} // namespace mkwvk
