// (AkynoLeyend r13h) Samples-passed counters from Vulkan occlusion queries (vk_occlusion.cpp).
#pragma once

#include <cstdint>

#include "vk_internal.h"

namespace mkwvk {

/// Whether the replay counts samples passed with occlusion queries: the device has host query resets and the pool was
/// made. RX_VK_OCCLUSION=0: no (the old synthetic count, 16 a draw). Made at the first call.
bool occlusion_on();
/// A samples-passed RESET_COUNTER in the recording whose submission signals `value`: the count runs from here
void occlusion_reset(VkCommandBuffer cmd, uint64_t value);
/// A samples-passed REPORT_COUNTER to addr: {count, timestamp} goes there once the GPU is done with `value`
void occlusion_report(VkCommandBuffer cmd, uint64_t value, uint64_t addr, uint64_t timestamp);
/// A draw in the open pass (vk_draw.cpp, after begin_pass): its pass gets a query when the count runs
void occlusion_draw_in_pass(VkCommandBuffer cmd);
/// The open pass ends (vk_draw.cpp end_pass, before vkCmdEndRendering): its query with it
void occlusion_pass_end(VkCommandBuffer cmd);
/// A draw the count should have seen went unrecorded (left out, no pipeline yet): the report counts at least 1
void occlusion_draw_lost();
/// Whether a report to addr is still to be written (render conditions: an unknown count renders)
bool occlusion_pending(uint64_t addr);
/// The reports of submissions up to `done` written to guest memory, in stream order (any thread)
void occlusion_collect(uint64_t done);

} // namespace mkwvk
