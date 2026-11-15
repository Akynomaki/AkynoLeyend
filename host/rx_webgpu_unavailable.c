/* AkynoLeyend: explicit failure for a Vulkan-only distribution.
 * SPDX-License-Identifier: MIT
 */
#include "hos.h"
#include "../gpu/render/rx_nvn.h"

int wgr_start(void *window) {
    (void)window;
    hos_fatal(NULL, "Vulkan could not start. This build has no WebGPU fallback; see the preceding loader/device error.");
    return 0;
}
void wgr_resize(int width, int height) { (void)width; (void)height; }
const char *wgr_describe(void) { return "Vulkan unavailable"; }
void wgr_stats(int64_t *draws, int64_t *skipped, int64_t *pipelines) { *draws = *skipped = *pipelines = 0; }
void wgr_nvn_submit(const uint64_t *handles, int count) { (void)handles; (void)count; }
uint64_t wgr_nvn_fence(void) { return 0; }
uint64_t wgr_nvn_pushed(void) { return 0; }
uint64_t wgr_nvn_replayed(void) { return 0; }
int wgr_nvn_wait(uint64_t fence, uint64_t timeout) { (void)fence; (void)timeout; return 0; }
void wgr_wait_writebacks_reading(const void *pointer, uint64_t size) { (void)pointer; (void)size; }
void wgr_nvn_finish(void) {}
void wgr_nvn_present(const nvn_tex *texture, const int crop[4]) { (void)texture; (void)crop; }
void wgr_nvn_register_texture(int id, const nvn_tex *texture, const nvn_view *view) { (void)id; (void)texture; (void)view; }
void wgr_nvn_register_sampler(int id, const nvn_samp_par *sampler) { (void)id; (void)sampler; }
void wgr_nvn_set_texture_pool_size(int count) { (void)count; }
void wgr_nvn_texture_released(const nvn_tex *texture) { (void)texture; }
void wgr_nvn_program_released(const nvn_prog *program) { (void)program; }
void wgr_nvn_read_texels(const nvn_tex *texture, unsigned level, unsigned layer, const NVNcopyRegion *region,
                         uint8_t *destination, uint64_t row, uint64_t image) {
    (void)texture; (void)level; (void)layer; (void)region; (void)destination; (void)row; (void)image;
}
void wgr_nvn_write_texels(const nvn_tex *texture, unsigned level, unsigned layer, const NVNcopyRegion *region,
                          const uint8_t *source, uint64_t row, uint64_t image) {
    (void)texture; (void)level; (void)layer; (void)region; (void)source; (void)row; (void)image;
}
void wgr_nvn_invalidate(uint64_t address, uint64_t size) { (void)address; (void)size; }
