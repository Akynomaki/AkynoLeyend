// Frame interpolation (RX_VK_FRAMEGEN=1; off by default): frames made between the game's, from its last two, shown in
// between by a display thread, so a game at 60 fps is shown at 120 (RX_VK_FRAMEGEN_MULT=3: 180). The WebGPU
// renderer's (gpu/render/rx_framegen.cpp, whose comments explain it), on Vulkan:
//   1. each frame is copied (it may be drawn over next frame) and reduced to quarter-size luma;
//   2. block matching: a vector per 16x16 pixels within +-32 pixels (RX_VK_FRAMEGEN_RADIUS quarter texels, default
//      8), then a 3x3 median of them;
//   3. each in-between frame at time t blends the last frame moved back along t and the new one forward along 1 - t.
// Recorded into the present's own recording, after the game's work; the display thread shows the made frames and
// then the game's, evenly over the game's recent frame time, about one frame behind the game. Loading hitches
// (frames over 100 ms apart) are not interpolated.
// (AkynoLeyend 0.4.5-test.1) The row's "Dinâmica" (9): how many frames each game frame is shown as, chosen each game frame
// by fg_dynamic.h (MFG-Unlocker's controller, MIT) toward the refresh of the window's display or the Alvo row, up to the
// Máximo row; the sets are made for that most once, and the count changes with no wait. The display thread's line is
// fg_pacer.h's, and it waits for the GPU to make a batch before its first frame (a VkEvent per set; RX_VK_FG_READY=0: not).
// RX_VK_FG_TRACE=<file>: a CSV line per frame shown (tools/fg_trace_summary.py reads it).
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstring>
#include <deque>
#include <mutex>
#include <thread>

#include "fg_dynamic.h"
#include "fg_pacer.h"
#include "vk_framegen.h"
#include "vk_menu.h"
#include "vk_texture.h"
#include "present_crop.h"
#include "hdr10_pixels.h"

#include "shaders/fg_copy_comp_spv.h"
#include "shaders/fg_flow_comp_spv.h"
#include "shaders/fg_luma_comp_spv.h"
#include "shaders/fg_median_comp_spv.h"
#include "shaders/fg_scale_comp_spv.h"
#include "shaders/fg_synth_comp_spv.h"
#include "shaders/fsr_easu_comp_spv.h"
#include "shaders/fsr_rcas_comp_spv.h"
#include "shaders/hdr_encode_comp_spv.h"
#include "shaders/wide_sides_comp_spv.h"
#include "vk_work.h"   // Count GPU work after other headers have declared the Vulkan calls.

namespace mkwvk {
extern std::atomic<uint32_t> present_kind;
HWND app_window();   // (vk_main.cpp: the game's window, for the display it is on)   // (vk_replay.cpp: the frame log's)
namespace {

constexpr int kMaxMult = 8;   // (up to 8x: players asked; the made frames are allocated for the multiplier chosen only)

struct Img {
    VkImage image = VK_NULL_HANDLE;
    VmaAllocation alloc = nullptr;
    VkImageView view = VK_NULL_HANDLE;
};
struct OutSet {
    Img frame[kMaxMult];
    int made = 0;   // (frame[0..made) are made frames; frame[made] is the game's)
    bool busy = false;
    VkEvent ready = VK_NULL_HANDLE;   // (0.4.5-test.1: set by the GPU once the set's frames are made)
    bool armed = false;               // (its setting recorded: the GPU sets it, then it may be reset)
};
struct Job {
    OutSet* set;
    int64_t at;
    uint64_t value;   // (the recording that makes its frames)
};
struct Pipe {
    VkDescriptorSetLayout set = VK_NULL_HANDLE;
    VkPipelineLayout layout = VK_NULL_HANDLE;
    VkPipeline pipe = VK_NULL_HANDLE;
};

struct State {
    bool init = false, failed = false;
    bool samplers_attempted = false, scale_attempted = false;
    uint32_t w = 0, h = 0;
    Pipe copy, luma, flow, median, synth, scale;
    Pipe fsr_easu, fsr_rcas;
    bool fsr_attempted = false, fsr_ready = false;
    Img fsr_color, fsr_sharpened;
    uint32_t fsr_w = 0, fsr_h = 0;
    Img cropped;
    uint32_t cropped_w = 0, cropped_h = 0;
    Img scaled;   // (the Insert menu's upscaling: at the window's size)
    uint32_t scaled_w = 0, scaled_h = 0;
    VkSampler nearest = VK_NULL_HANDLE, linear = VK_NULL_HANDLE;
    Img frames[2], lumas[2], flows[2];
    OutSet sets[3];   // (one shown, one waiting its place on the line, one being made: the pacer never holds the game back)
    int cur = 0, next_set = 0;
    bool have_prev = false;
    int64_t last_at = 0;
    std::mutex mu;
    std::condition_variable cv;
    std::deque<Job> jobs;
    bool thread_started = false;
    OutSet* recorded = nullptr;   // (the set the last framegen_record filled, for framegen_queue)
    int64_t recorded_at = 0;
    int mult = 0;   // (the multiplier the sets' frames were made for)
    // (0.4.5-test.1) the Dinâmica row
    fgdyn::Dynamic dyn;
    bool dyn_on = false;
    int dyn_frames = 0;                 // (frames shown per game frame, the controller's last answer)
    std::atomic<int> refresh_hz{0};     // (the window's display, the display thread's reading)
    std::atomic<int> shown_mult{0};     // (the multiplier of the last batch, for the log)
    std::atomic<int> dyn_target{0};     // (the controller's target, for the log)
} fg;

struct SidesState {   // (AkynoLeyend r13, Hookshot v2.1.0) ultrawide's menu sides (framegen_sides)
    bool init = false, failed = false;
    Pipe pipe;
    Img cropped, out, small;   // (small: the picture at 1/8, which the sides blur)
    uint32_t cropped_w = 0, cropped_h = 0, w = 0, h = 0, small_w = 0, small_h = 0;
} sides;

struct HdrState {   // (AkynoLeyend r13, Hookshot v2.1.0) the HDR10 pass (framegen_hdr)
    bool init = false, failed = false;
    Pipe pipe;
    Img out;
    uint32_t w = 0, h = 0;
} hdr;

int64_t now_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

int multiplier() { return std::clamp(opts.framegen, 1, kMaxMult); }   // (the Insert menu; 1: the game's frames alone)
constexpr int kDynamicRow = 9;   // (0.4.5-test.1: the row's Dinâmica)
bool dynamic() { return opts.framegen == kDynamicRow; }
/// The frames each set is made for: the multiplier, or the Máximo row's at Dinâmica
int allocated() { return dynamic() ? std::clamp(opts.fg_max, 2, fgdyn::kMaxFrames) : multiplier(); }

/// (0.4.5-test.1) The refresh of the display the game's window is on, Hz; 0 when it cannot be read
int read_refresh_hz() {
    HWND w = app_window();
    HMONITOR mon = MonitorFromWindow(w ? w : GetDesktopWindow(), MONITOR_DEFAULTTONEAREST);
    MONITORINFOEXW mi{};
    mi.cbSize = sizeof mi;
    if (!mon || !GetMonitorInfoW(mon, &mi)) return 0;
    DEVMODEW dm{};
    dm.dmSize = sizeof dm;
    if (!EnumDisplaySettingsW(mi.szDevice, ENUM_CURRENT_SETTINGS, &dm)) return 0;
    return dm.dmDisplayFrequency > 1 ? (int)dm.dmDisplayFrequency : 0;   // (0 and 1: the hardware's default)
}

void drop_pipe(Pipe& p) {
    if (p.pipe) vkDestroyPipeline(dev.device, p.pipe, nullptr);
    if (p.layout) vkDestroyPipelineLayout(dev.device, p.layout, nullptr);
    if (p.set) vkDestroyDescriptorSetLayout(dev.device, p.set, nullptr);
    p = {};
}

/// A compute pipeline over bindings of these types (push descriptors), push constants of push bytes
bool make_pipe(Pipe& p, const uint32_t* code, size_t bytes, std::initializer_list<VkDescriptorType> types, uint32_t push,
               const VkSpecializationInfo* spec = nullptr) {
    Pipe pending;
    const auto fail = [&] { drop_pipe(pending); return false; };
    std::vector<VkDescriptorSetLayoutBinding> b;
    for (VkDescriptorType t : types) b.push_back({(uint32_t)b.size(), t, 1, VK_SHADER_STAGE_COMPUTE_BIT, nullptr});
    VkDescriptorSetLayoutCreateInfo li{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
    li.flags = VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR;
    li.bindingCount = (uint32_t)b.size();
    li.pBindings = b.data();
    if (vkCreateDescriptorSetLayout(dev.device, &li, nullptr, &pending.set) != VK_SUCCESS) return fail();
    const VkPushConstantRange pr{VK_SHADER_STAGE_COMPUTE_BIT, 0, std::max(push, 4u)};
    VkPipelineLayoutCreateInfo pi{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
    pi.setLayoutCount = 1;
    pi.pSetLayouts = &pending.set;
    pi.pushConstantRangeCount = push ? 1 : 0;
    pi.pPushConstantRanges = &pr;
    if (vkCreatePipelineLayout(dev.device, &pi, nullptr, &pending.layout) != VK_SUCCESS) return fail();
    VkShaderModuleCreateInfo mi{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
    mi.codeSize = bytes;
    mi.pCode = code;
    VkShaderModule m = VK_NULL_HANDLE;
    if (vkCreateShaderModule(dev.device, &mi, nullptr, &m) != VK_SUCCESS) return fail();
    VkComputePipelineCreateInfo ci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
    ci.stage.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    ci.stage.stage = VK_SHADER_STAGE_COMPUTE_BIT;
    ci.stage.module = m;
    ci.stage.pName = "main";
    ci.stage.pSpecializationInfo = spec;
    ci.layout = pending.layout;
    const VkResult r = vkCreateComputePipelines(dev.device, VK_NULL_HANDLE, 1, &ci, nullptr, &pending.pipe);
    vkDestroyShaderModule(dev.device, m, nullptr);
    if (r != VK_SUCCESS) return fail();
    drop_pipe(p);
    p = pending;
    return true;
}

bool init_samplers() {
    if (fg.samplers_attempted) return fg.nearest && fg.linear;
    fg.samplers_attempted = true;
    if (!dev.push_descriptor || !vkCmdPushDescriptorSetKHR) return false;
    VkSamplerCreateInfo si{VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};
    si.addressModeU = si.addressModeV = si.addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    si.maxLod = 0.25f;
    if (vkCreateSampler(dev.device, &si, nullptr, &fg.nearest) != VK_SUCCESS) {
        logf("vk: ERROR: present sampler creation failed; scaling and interpolation unavailable");
        return false;
    }
    si.magFilter = si.minFilter = VK_FILTER_LINEAR;
    if (vkCreateSampler(dev.device, &si, nullptr, &fg.linear) != VK_SUCCESS) {
        vkDestroySampler(dev.device, fg.nearest, nullptr);
        fg.nearest = VK_NULL_HANDLE;
        logf("vk: ERROR: present sampler creation failed; scaling and interpolation unavailable");
        return false;
    }
    return true;
}

bool init_scale() {
    if (fg.scale_attempted) return fg.scale.pipe != VK_NULL_HANDLE;
    fg.scale_attempted = true;
    if (!init_samplers()) return false;
    const bool ok = make_pipe(fg.scale, FG_SCALE_COMP_SPV, sizeof FG_SCALE_COMP_SPV,
                              {VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE}, 8);
    if (!ok) logf("vk: ERROR: present scaling pipeline creation failed");
    return ok;
}

bool init() {
    if (fg.init) return !fg.failed;
    fg.init = true;
    fg.failed = true;
    if (!init_samplers()) return false;
    const VkDescriptorType S = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, I = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
    const int radius = getenv("RX_VK_FRAMEGEN_RADIUS") ? std::clamp(atoi(getenv("RX_VK_FRAMEGEN_RADIUS")), 1, 16) : 8;
    const VkSpecializationMapEntry me{0, 0, 4};
    const VkSpecializationInfo spec{1, &me, 4, &radius};
    if (!make_pipe(fg.copy, FG_COPY_COMP_SPV, sizeof FG_COPY_COMP_SPV, {S, I}, 16) ||
        !make_pipe(fg.luma, FG_LUMA_COMP_SPV, sizeof FG_LUMA_COMP_SPV, {S, I}, 0) ||
        !make_pipe(fg.flow, FG_FLOW_COMP_SPV, sizeof FG_FLOW_COMP_SPV, {S, S, I}, 0, &spec) ||
        !make_pipe(fg.median, FG_MEDIAN_COMP_SPV, sizeof FG_MEDIAN_COMP_SPV, {S, I}, 0) ||
        !make_pipe(fg.synth, FG_SYNTH_COMP_SPV, sizeof FG_SYNTH_COMP_SPV, {S, S, S, I}, 4)) {
        drop_pipe(fg.copy), drop_pipe(fg.luma), drop_pipe(fg.flow), drop_pipe(fg.median), drop_pipe(fg.synth);
        return false;
    }
    fg.failed = false;
    if (dynamic())
        logf("vk: frame interpolation ready: dynamic, up to %dx the game's frames (made from its last two, shown evenly)",
             allocated());
    else
        logf("vk: frame interpolation ready: %dx the game's frames (made from its last two, shown evenly)", multiplier());
    for (OutSet& set : fg.sets) {
        VkEventCreateInfo ei{VK_STRUCTURE_TYPE_EVENT_CREATE_INFO};
        if (!set.ready && vkCreateEvent(dev.device, &ei, nullptr, &set.ready) != VK_SUCCESS) set.ready = VK_NULL_HANDLE;
    }
    return true;
}

bool make_img(Img& i, uint32_t w, uint32_t h, VkFormat f, VkImageUsageFlags usage) {
    Img pending;
    VkImageCreateInfo ci{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
    ci.imageType = VK_IMAGE_TYPE_2D;
    ci.format = f;
    ci.extent = {w, h, 1};
    ci.mipLevels = ci.arrayLayers = 1;
    ci.samples = VK_SAMPLE_COUNT_1_BIT;
    ci.usage = usage;
    if (!create_image(ci, pending.image, pending.alloc)) return false;
    VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
    vi.image = pending.image;
    vi.viewType = VK_IMAGE_VIEW_TYPE_2D;
    vi.format = f;
    vi.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    if (vkCreateImageView(dev.device, &vi, nullptr, &pending.view) != VK_SUCCESS) {
        destroy_image(pending.image, pending.alloc);
        return false;
    }
    i = pending;
    return true;
}
void drop_img(Img& i) {
    if (i.view) vkDestroyImageView(dev.device, i.view, nullptr);
    if (i.image) destroy_image(i.image, i.alloc);
    i = {};
}

void to_general(VkCommandBuffer cmd, VkImage image) {
    VkImageMemoryBarrier2 b{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2};
    b.srcStageMask = b.dstStageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT;
    b.dstAccessMask = VK_ACCESS_2_MEMORY_READ_BIT | VK_ACCESS_2_MEMORY_WRITE_BIT;
    b.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    b.newLayout = VK_IMAGE_LAYOUT_GENERAL;
    b.srcQueueFamilyIndex = b.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    b.image = image;
    b.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    VkDependencyInfo d{VK_STRUCTURE_TYPE_DEPENDENCY_INFO};
    d.imageMemoryBarrierCount = 1;
    d.pImageMemoryBarriers = &b;
    vkCmdPipelineBarrier2(cmd, &d);
}

bool ensure_size(VkCommandBuffer cmd, uint32_t w, uint32_t h) {
    if (fg.w == w && fg.h == h && fg.mult == allocated()) return true;
    {   // (the display thread is done with the old sets first)
        std::unique_lock lk(fg.mu);
        fg.cv.wait(lk, [] { return fg.jobs.empty() && !fg.sets[0].busy && !fg.sets[1].busy && !fg.sets[2].busy; });
    }
    vkDeviceWaitIdle(dev.device);
    for (int i = 0; i < 2; i++) {
        drop_img(fg.frames[i]), drop_img(fg.lumas[i]), drop_img(fg.flows[i]);
    }
    for (OutSet& set : fg.sets)
        for (Img& t : set.frame) drop_img(t);
    fg.w = w, fg.h = h;
    const uint32_t qw = (w + 3) / 4, qh = (h + 3) / 4, cw = (qw + 3) / 4, ch = (qh + 3) / 4;
    const VkImageUsageFlags rw = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT;
    bool ok = true;
    for (int i = 0; i < 2; i++) {
        ok = ok && make_img(fg.frames[i], w, h, VK_FORMAT_R8G8B8A8_UNORM, rw | VK_IMAGE_USAGE_TRANSFER_SRC_BIT);
        ok = ok && make_img(fg.lumas[i], qw, qh, VK_FORMAT_R16_SFLOAT, rw);
        ok = ok && make_img(fg.flows[i], cw, ch, VK_FORMAT_R16G16B16A16_SFLOAT, rw);
    }
    fg.mult = allocated();
    for (OutSet& set : fg.sets)
        for (int k = 0; k < fg.mult; k++)
            ok = ok && make_img(set.frame[k], w, h, VK_FORMAT_R8G8B8A8_UNORM,
                                rw | VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT);
    if (!ok) {
        fg.failed = true;
        logf("vk: frame interpolation: its images (%ux%u) were not made: off", w, h);
        return false;
    }
    for (int i = 0; i < 2; i++) {
        to_general(cmd, fg.frames[i].image), to_general(cmd, fg.lumas[i].image), to_general(cmd, fg.flows[i].image);
    }
    for (OutSet& set : fg.sets)
        for (Img& t : set.frame)
            if (t.image) to_general(cmd, t.image);   // (only the multiplier's frames are made: a barrier on no image crashed the driver)
    fg.have_prev = false;
    if (dynamic()) fg.dyn.restart();   // (a new size: the frame times start over, what was learned stays)
    return true;
}

/// One pass: pipe over w x h in 8x8 groups, the bindings in order (a sampler when one is given: a sampled image)
void pass(VkCommandBuffer cmd, const Pipe& p, std::initializer_list<std::pair<VkImageView, VkSampler>> bindings,
          uint32_t w, uint32_t h, const void* push = nullptr, uint32_t push_bytes = 0) {
    VkDescriptorImageInfo ii[8];
    VkWriteDescriptorSet ws[8];
    uint32_t n = 0;
    for (const auto& [view, sampler] : bindings) {
        ii[n] = {sampler, view, VK_IMAGE_LAYOUT_GENERAL};
        ws[n] = {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};
        ws[n].dstBinding = n;
        ws[n].descriptorCount = 1;
        ws[n].descriptorType = sampler ? VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER : VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        ws[n].pImageInfo = &ii[n];
        n++;
    }
    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, p.pipe);
    vkCmdPushDescriptorSetKHR(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, p.layout, 0, n, ws);
    if (push_bytes) vkCmdPushConstants(cmd, p.layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, push_bytes, push);
    vkCmdDispatch(cmd, (w + 7) / 8, (h + 7) / 8, 1);
    full_barrier(cmd);
}

/// (0.4.5-test.1) Until the GPU has made the set's frames (its event), sleeping while that is expected later than `expect`;
/// the time it was seen made, or 0 when it is not known (no event, RX_VK_FG_READY=0, or not made within 100 ms)
int64_t wait_made(const OutSet& set, int64_t expect) {
    static const bool on = !getenv("RX_VK_FG_READY") || atoi(getenv("RX_VK_FG_READY")) != 0;
    if (!on || !set.ready) return 0;
    const int64_t start = now_ns();
    for (;;) {
        const VkResult st = vkGetEventStatus(dev.device, set.ready);
        const int64_t now = now_ns();
        if (st == VK_EVENT_SET) return now;
        if (st != VK_EVENT_RESET || now - start > 100000000) {
            static bool told;
            if (!told) told = true, logf("vk: frame interpolation: a batch not seen made in 100 ms (%d): shown without waiting", (int)st);
            return 0;
        }
        if (expect - now > 1500000)
            std::this_thread::sleep_for(std::chrono::nanoseconds(expect - now - 1000000));
        else if (now - std::max(expect, start) > 1000000)
            std::this_thread::sleep_for(std::chrono::microseconds(500));   // (later than expected: no spinning)
        else
            SwitchToThread();
    }
}

void display_main() {
    SetThreadDescription(GetCurrentThread(), L"mkw_vk display");
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_ABOVE_NORMAL);
    fgpace::Pacer pacer;
    struct { int on_time, late, skipped; int64_t since; } stat{};
    int64_t shown_at = 0, refresh_read = 0;
    int hist[6] = {}, mults[kMaxMult + 1] = {};
    // (RX_VK_FG_TRACE=<file>: a line per frame shown, milliseconds from the first batch)
    static FILE* trace = [] {
        const char* p = getenv("RX_VK_FG_TRACE");
        FILE* f = p && *p ? fopen(p, "w") : nullptr;
        if (f) fprintf(f, "batch,k,shown,at_ms,ready_ms,due_ms,shown_ms,interval_ms,lag_ms,dynamic,target_fps,refresh_hz\n");
        return f;
    }();
    int64_t trace_zero = 0;
    uint64_t batch = 0;
    for (;;) {
        Job j;
        {
            std::unique_lock lk(fg.mu);
            fg.cv.wait(lk, [] { return !fg.jobs.empty(); });
            j = fg.jobs.front();
            fg.jobs.pop_front();
        }
        if (j.at - refresh_read > 1000000000LL) {   // (the window may move to another display: read again each second)
            refresh_read = j.at;
            fg.refresh_hz.store(read_refresh_hz(), std::memory_order_relaxed);
        }
        if (!stat.since) stat.since = j.at;
        if (j.at - stat.since > 5000000000LL) {
            char counts[96] = "";
            if (dynamic()) {
                int n = snprintf(counts, sizeof counts, "; dynamic (target %d fps, %d Hz):", fg.dyn_target.load(std::memory_order_relaxed),
                                 fg.refresh_hz.load(std::memory_order_relaxed));
                for (int m = 1; m <= kMaxMult && n > 0 && n < (int)sizeof counts; m++)
                    if (mults[m]) n += snprintf(counts + n, sizeof counts - n, " %dx %d", m, mults[m]);
            }
            logf("vk: frame interpolation: %d frames shown on time, %d late (over 2 ms); shown apart: <7 ms %d, 7-9 %d, 9-12 %d, "
                 "12-17 %d, 17-25 %d, over 25 %d; made %.1f ms after the hand-over%s", stat.on_time, stat.late, hist[0], hist[1],
                 hist[2], hist[3], hist[4], hist[5], pacer.lag() / 1e6, counts);
            memset(hist, 0, sizeof hist);
            memset(mults, 0, sizeof mults);
            stat = {0, 0, 0, j.at};
            if (trace) fflush(trace);
        }
        // (hookshot) The pacer. The game hands over frames 12 to 28 ms apart around a mean of 19, and shown as they came that
        // was the stutter, whatever the frame rate. Every frame now has its place on an even line, the recent frame time
        // apart, a frame early waiting for it (fg_pacer.h). RX_VK_PACE=0: as they come.
        const bool pace = opts.pace != 0;
        const int shown = j.set->made + 1;
        mults[std::clamp(shown, 1, kMaxMult)]++;
        pacer.batch(j.at, shown);
        const int64_t ready = wait_made(*j.set, j.at + pacer.lag());
        pacer.ready(ready);
        if (!trace_zero) trace_zero = j.at;
        for (int k = 0; k <= j.set->made; k++) {
            const int64_t now = now_ns();
            const int64_t due = pacer.due(now, pace, k == 0);
            if (due - now > 1000000) {
                std::this_thread::sleep_for(std::chrono::nanoseconds(due - now - 1000000));
            }
            while (now_ns() < due) SwitchToThread();
            const int64_t t = now_ns();
            present_kind.store(k < j.set->made ? 1 : 0);
            present_image(j.set->frame[k].image, fg.w, fg.h, nullptr, j.set->frame[k].view);
            menu_note_frame(k == j.set->made);
            if (shown_at) {
                const int64_t d = t - shown_at;
                hist[d < 7000000 ? 0 : d < 9000000 ? 1 : d < 12000000 ? 2 : d < 17000000 ? 3 : d < 25000000 ? 4 : 5]++;
            }
            shown_at = t;
            pacer.shown(t);
            (t - due > 2000000 ? stat.late : stat.on_time)++;
            if (trace)
                fprintf(trace, "%llu,%d,%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%.1f,%d\n", (unsigned long long)batch, k, shown,
                        (j.at - trace_zero) / 1e6, ready ? (ready - trace_zero) / 1e6 : -1.0, (due - trace_zero) / 1e6,
                        (t - trace_zero) / 1e6, pacer.interval() / 1e6, pacer.lag() / 1e6, dynamic() ? 1 : 0,
                        dynamic() ? (double)fg.dyn_target.load(std::memory_order_relaxed) : 0.0,
                        fg.refresh_hz.load(std::memory_order_relaxed));
        }
        batch++;
        fg.shown_mult.store(shown, std::memory_order_relaxed);
        std::lock_guard lk(fg.mu);
        j.set->busy = false;
        fg.cv.notify_all();
    }
}

} // namespace

int framegen_refresh_hz() { return fg.refresh_hz.load(std::memory_order_relaxed); }

bool framegen_on() {
    // (RX_VK_FRAMEGEN=1: the game's ~50 fps shown at ~100. Off by default: block-matched frames flashed on fast
    // motion, the HUD and camera cuts)
    // (hookshot: available unless RX_VK_FRAMEGEN=0; the Insert menu turns it on, off by default)
    static const bool on = !getenv("RX_VK_FRAMEGEN") || atoi(getenv("RX_VK_FRAMEGEN")) != 0;
    return on && !dev.offscreen && !fg.failed;
}

VkImage framegen_scale(VkCommandBuffer cmd, VkImageView src, VkImage image, uint32_t sw, uint32_t sh, const int crop[4], uint32_t dw, uint32_t dh) {
    if (!opts.upscale && !opts.sharpness) return VK_NULL_HANDLE;
    PresentCrop rect;
    if (!src || !image || !dw || !dh || !present_crop(sw, sh, crop, rect)) return VK_NULL_HANDLE;
    const uint32_t input_w = rect.width, input_h = rect.height;
    // At 1:1 the game has already produced every pixel. With sharpening
    // off, present directly instead of filtering into another GPU image.
    if (input_w == dw && input_h == dh && !opts.sharpness) return VK_NULL_HANDLE;
    if (!init_samplers()) return VK_NULL_HANDLE;
    // (the game draws into part of its window textures, 2048 x 1152 of 2560 x 1440 here: the filter was given the whole texture, and the
    // picture came out in the top left corner of the window with black around it. The crop first, then the filter)
    if (rect.x || rect.y || input_w != sw || input_h != sh) {
        if (fg.cropped_w != input_w || fg.cropped_h != input_h) {
            {
                std::lock_guard qk(dev.present_mu);
                vkDeviceWaitIdle(dev.device);
            }
            drop_img(fg.cropped);
            fg.cropped_w = fg.cropped_h = 0;
            if (!make_img(fg.cropped, input_w, input_h, VK_FORMAT_R8G8B8A8_UNORM, VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT)) return VK_NULL_HANDLE;
            fg.cropped_w = input_w, fg.cropped_h = input_h;
            to_general(cmd, fg.cropped.image);
        }
        VkImageBlit b{};
        b.srcSubresource = b.dstSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
        b.srcOffsets[0] = {rect.x, rect.y, 0};
        b.srcOffsets[1] = {rect.x + (int)input_w, rect.y + (int)input_h, 1};
        b.dstOffsets[1] = {(int)input_w, (int)input_h, 1};
        vkCmdBlitImage(cmd, image, VK_IMAGE_LAYOUT_GENERAL, fg.cropped.image, VK_IMAGE_LAYOUT_GENERAL, 1, &b, VK_FILTER_NEAREST);
        full_barrier(cmd);
        src = fg.cropped.view;
    }
    // FSR 1 reconstructs an image at least as large as its input. Supersampled input uses Lanczos.
    if (opts.upscale == 3 && dw >= input_w && dh >= input_h) {
        if (!fg.fsr_attempted) {
            fg.fsr_attempted = true;
            const VkDescriptorType sample = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
            const VkDescriptorType store = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
            fg.fsr_ready = make_pipe(fg.fsr_easu, FSR_EASU_COMP_SPV, sizeof FSR_EASU_COMP_SPV, {sample, store}, 0) &&
                           make_pipe(fg.fsr_rcas, FSR_RCAS_COMP_SPV, sizeof FSR_RCAS_COMP_SPV, {sample, store}, 4);
            if (!fg.fsr_ready) drop_pipe(fg.fsr_easu), drop_pipe(fg.fsr_rcas);
            logf(fg.fsr_ready ? "vk: AMD FSR 1 ready: official EASU and separate RCAS" :
                               "vk: ERROR: FSR pipelines could not be created; FSR is NOT active");
        }
        if (!fg.fsr_ready) return VK_NULL_HANDLE;
        if (fg.fsr_w != dw || fg.fsr_h != dh) {
            std::lock_guard queue(dev.present_mu);
            vkDeviceWaitIdle(dev.device);
            drop_img(fg.fsr_color);
            drop_img(fg.fsr_sharpened);
            const VkImageUsageFlags usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
            if (!make_img(fg.fsr_color, dw, dh, VK_FORMAT_R16G16B16A16_SFLOAT, usage) ||
                !make_img(fg.fsr_sharpened, dw, dh, VK_FORMAT_R16G16B16A16_SFLOAT, usage)) {
                drop_img(fg.fsr_color);
                drop_img(fg.fsr_sharpened);
                fg.fsr_w = fg.fsr_h = 0;
                logf("vk: ERROR: FSR output allocation failed for %ux%u; FSR is NOT active", dw, dh);
                return VK_NULL_HANDLE;
            }
            fg.fsr_w = dw, fg.fsr_h = dh;
            to_general(cmd, fg.fsr_color.image);
            to_general(cmd, fg.fsr_sharpened.image);
            logf("vk: FSR output %ux%u, rgba16f, source %ux%u after crop", dw, dh, input_w, input_h);
        }
        pass(cmd, fg.fsr_easu, {{src, fg.linear}, {fg.fsr_color.view, VK_NULL_HANDLE}}, dw, dh);
        if (opts.sharpness <= 0) return fg.fsr_color.image;
        const float stops = 2.0f * (1.0f - std::clamp(opts.sharpness, 0, 100) / 100.0f);
        pass(cmd, fg.fsr_rcas, {{fg.fsr_color.view, fg.nearest}, {fg.fsr_sharpened.view, VK_NULL_HANDLE}}, dw, dh, &stops, sizeof stops);
        return fg.fsr_sharpened.image;
    }
    if (opts.upscale == 3) {
        static bool told = false;
        if (!told) logf("vk: FSR EASU bypassed for downsampling %ux%u to %ux%u; using Lanczos", input_w, input_h, dw, dh), told = true;
    }
    if (!init_scale()) return VK_NULL_HANDLE;
    if (fg.scaled_w != dw || fg.scaled_h != dh) {
        {
            std::lock_guard qk(dev.present_mu);   // (the queue is idle only while nothing else submits to it)
            vkDeviceWaitIdle(dev.device);
        }
        drop_img(fg.scaled);
        fg.scaled_w = fg.scaled_h = 0;
        // (r13: SAMPLED too, the HDR pass reads it through a sampler)
        if (!make_img(fg.scaled, dw, dh, VK_FORMAT_R8G8B8A8_UNORM,
                      VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT)) return VK_NULL_HANDLE;
        fg.scaled_w = dw, fg.scaled_h = dh;
        to_general(cmd, fg.scaled.image);
    }
    const struct { int mode; float sharp; } pc{opts.upscale == 3 ? 2 : opts.upscale, opts.sharpness / 100.0f};
    pass(cmd, fg.scale, {{src, fg.linear}, {fg.scaled.view, VK_NULL_HANDLE}}, dw, dh, &pc, sizeof pc);
    return fg.scaled.image;
}

// (AkynoLeyend r13, Hookshot v2.1.0) Ultrawide's menus (the panel's Ultrawide menus): which of nx2/oot_patches.py's keep-list
// screens keep the whole picture, asked by the game's side each frame (akyno_wide_menus, with its margin), and, while a menu
// shows, the sides of the middle 16:9 to show out of focus (1) or black (2), as fractions of the width. A menu's layout is set
// up once, when it is first opened: what tells one is that the frame draws no world (vk_draw.cpp world_drawn_at), as a pause,
// the map, a loading screen or a movie does not (3 presents' grace for a frame the world skips). The middle is centred: its
// right edge is 1 - x0. One 8-byte atomic: frame generation's display thread reads it while the replay thread writes it
extern std::atomic<int64_t> world_drawn_at, wheel_drawn_at;   // (vk_draw.cpp)
extern int64_t presents_now;                                  // (vk_replay.cpp)
struct WideSides { float x0 = 0.0f; int side = 0; };
std::atomic<float> wide_margin{0.0f};   // (the host's, each frame: 0 unless the picture is wider than 16:9)
std::atomic<WideSides> wide_now;        // (wide_sides_tick's, each present)
WideSides wide_sides() {
    WideSides w;
    const float margin = wide_margin.load(std::memory_order_relaxed);
    // (no world: a menu. But not the item wheel, whose background is the last frame of play over the whole picture, as on the
    // console: its sides are left as the game draws them)
    const bool no_world = presents_now - world_drawn_at.load(std::memory_order_relaxed) > 3 &&
                          presents_now - wheel_drawn_at.load(std::memory_order_relaxed) > 3;
    if (opts.wide_menus && margin > 0.0f && no_world) w.x0 = margin, w.side = std::clamp(opts.wide_menus, 1, 2);
    static int told = 0;
    if (w.side != told) {   // (each change logged: a report of blurred sides in play says when they came and went)
        logf("vk: ultrawide menu sides %s at present %lld (the world last drawn at present %lld)", w.side ? "on" : "off",
             (long long)presents_now, (long long)world_drawn_at.load(std::memory_order_relaxed));
        told = w.side;
    }
    return w;
}
void wide_sides_tick() { wide_now = wide_sides(); }

VkImage framegen_sides(VkCommandBuffer cmd, VkImageView src, VkImage image, uint32_t sw, uint32_t sh, const int crop[4], uint32_t dw, uint32_t dh) {
    const WideSides wide = wide_now.load(std::memory_order_relaxed);
    PresentCrop source;
    if (!wide.side || !src || !image || !dw || !dh || !present_crop(sw, sh, crop, source)) return VK_NULL_HANDLE;
    if (!sides.init) {
        sides.init = sides.failed = true;
        const VkDescriptorType S = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, I = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        if (init_samplers() && make_pipe(sides.pipe, WIDE_SIDES_COMP_SPV, sizeof WIDE_SIDES_COMP_SPV, {S, I, S}, 20))
            sides.failed = false;
        else
            logf("vk: ultrawide menu sides: the pass could not be made: the picture as it is");
    }
    if (sides.failed) return VK_NULL_HANDLE;
    const auto remake = [&](Img& img, uint32_t& w, uint32_t& h, uint32_t nw, uint32_t nh, VkImageUsageFlags usage) {
        if (w == nw && h == nh) return true;
        {
            std::lock_guard qk(dev.present_mu);   // (the queue is idle only while nothing else submits to it)
            vkDeviceWaitIdle(dev.device);
        }
        drop_img(img);
        w = h = 0;
        if (!make_img(img, nw, nh, VK_FORMAT_R8G8B8A8_UNORM, usage)) return false;
        w = nw, h = nh;
        to_general(cmd, img.image);
        return true;
    };
    // (the game draws into part of its window textures: the crop first, as the window's filter does; the pass reads all of src)
    if (source.x || source.y || source.width != sw || source.height != sh) {
        if (!remake(sides.cropped, sides.cropped_w, sides.cropped_h, source.width, source.height,
                    VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT)) return VK_NULL_HANDLE;
        VkImageBlit b{};
        b.srcSubresource = b.dstSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
        b.srcOffsets[0] = {source.x, source.y, 0};
        b.srcOffsets[1] = {source.x + (int)source.width, source.y + (int)source.height, 1};
        b.dstOffsets[1] = {(int)source.width, (int)source.height, 1};
        vkCmdBlitImage(cmd, image, VK_IMAGE_LAYOUT_GENERAL, sides.cropped.image, VK_IMAGE_LAYOUT_GENERAL, 1, &b, VK_FILTER_NEAREST);
        full_barrier(cmd);
        src = sides.cropped.view;
    }
    if (!remake(sides.out, sides.w, sides.h, dw, dh,
                VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT)) return VK_NULL_HANDLE;
    // (Hookshot's fg_scale.comp, its linear filter and no sharpening: the window's own filter has run or runs elsewhere)
    struct { int mode; float sharp; float x0, x1; int side; } pc{0, 0.0f, wide.x0, 1.0f - wide.x0, wide.side};
    if (wide.side == 1) {   // (the blurred sides: first the picture at 1/8, each pixel the mean of its 8 x 8, which they blur)
        if (!remake(sides.small, sides.small_w, sides.small_h, std::max(1u, source.width / 8), std::max(1u, source.height / 8),
                    VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT)) return VK_NULL_HANDLE;
        pc.side = 3;   // (the shader: make the small copy)
        pass(cmd, sides.pipe, {{src, fg.linear}, {sides.small.view, VK_NULL_HANDLE}, {src, fg.linear}}, sides.small_w, sides.small_h, &pc, sizeof pc);
        pc.side = 1;
    }
    pass(cmd, sides.pipe, {{src, fg.linear}, {sides.out.view, VK_NULL_HANDLE}, {wide.side == 1 ? sides.small.view : src, fg.linear}},
         dw, dh, &pc, sizeof pc);
    return sides.out.image;
}

VkImageView framegen_scaled_view(VkImage scaled) {
    if (!scaled) return VK_NULL_HANDLE;
    for (const Img* i : {&fg.fsr_sharpened, &fg.fsr_color, &fg.scaled, &sides.out})
        if (i->image == scaled) return i->view;
    return VK_NULL_HANDLE;
}

/// (AkynoLeyend r13, Hookshot v2.1.0) The F1 panel's HDR: src's crop to a dw x dh HDR10 image (PQ, Rec. 2020, 10 bits), to be
/// copied into an HDR10 swapchain's image as the SDR picture is (shaders/hdr_encode.comp); null when it cannot be made (then
/// the SDR picture)
VkImage framegen_hdr(VkCommandBuffer cmd, VkImageView src, uint32_t sw, uint32_t sh, const int crop[4], uint32_t dw, uint32_t dh) {
    PresentCrop source;
    if (!src || !dw || !dh || !present_crop(sw, sh, crop, source)) return VK_NULL_HANDLE;
    if (!hdr.init) {
        hdr.init = hdr.failed = true;
        const VkDescriptorType S = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, I = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        if (init_samplers() && make_pipe(hdr.pipe, HDR_ENCODE_COMP_SPV, sizeof HDR_ENCODE_COMP_SPV, {S, I}, 32))
            hdr.failed = false;
        else
            logf("vk: HDR: the HDR pass could not be made: SDR");
    }
    if (hdr.failed) return VK_NULL_HANDLE;
    if (hdr.w != dw || hdr.h != dh) {
        {
            std::lock_guard qk(dev.present_mu);   // (the queue is idle only while nothing else submits to it)
            vkDeviceWaitIdle(dev.device);
        }
        drop_img(hdr.out);
        hdr.w = hdr.h = 0;
        if (!make_img(hdr.out, dw, dh, VK_FORMAT_A2B10G10R10_UNORM_PACK32, VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT)) {
            static bool told;
            if (!told) told = true, logf("vk: HDR: no 10-bit storage image on this GPU: SDR");
            return VK_NULL_HANDLE;
        }
        hdr.w = dw, hdr.h = dh;
        to_general(cmd, hdr.out.image);
        logf("vk: HDR: the picture as HDR10 at %ux%u (the SDR picture expanded: white %d nits, highlights to %d)", dw, dh,
             akyno_hdr_white(opts.hdr_white), akyno_hdr_peak(opts.hdr_peak));
    }
    const float x0 = source.x / (float)sw, y0 = source.y / (float)sh;
    const float x1 = (source.x + source.width) / (float)sw, y1 = (source.y + source.height) / (float)sh;
    const struct { float uv[4]; float white, peak, knee, pad; } pc{{x0, y0, x1, y1}, (float)akyno_hdr_white(opts.hdr_white),
                                                                   (float)akyno_hdr_peak(opts.hdr_peak), 0.6f, 0.0f};
    pass(cmd, hdr.pipe, {{src, fg.linear}, {hdr.out.view, VK_NULL_HANDLE}}, dw, dh, &pc, sizeof pc);
    return hdr.out.image;
}

VkImage framegen_made_image(uint32_t* w, uint32_t* h) {
    if (!fg.recorded || !fg.recorded->made) return VK_NULL_HANDLE;
    *w = fg.w, *h = fg.h;
    return fg.recorded->frame[0].image;
}

bool framegen_record(VkCommandBuffer cmd, VkImageView src, uint32_t sw, uint32_t sh, const int crop[4]) {
    PresentCrop rect;
    if (!src || !present_crop(sw, sh, crop, rect) || !init() || !ensure_size(cmd, rect.width, rect.height)) return false;
    if (!fg.thread_started) {
        fg.thread_started = true;
        std::thread(display_main).detach();
    }
    const int64_t now = now_ns();
    const bool gap = fg.last_at && now - fg.last_at > 100000000;   // (a loading hitch: nothing to blend)
    const int64_t prev_at = fg.last_at;
    fg.last_at = now;
    OutSet* set;
    {
        std::unique_lock lk(fg.mu);
        fg.cv.wait(lk, [] { return !fg.sets[fg.next_set].busy; });
        set = &fg.sets[fg.next_set];
        set->busy = true;
        fg.next_set = (fg.next_set + 1) % 3;
    }
    // (0.4.5-test.1) the set's event again unset. The display thread waited for its last setting before it let the set go,
    // up to 100 ms: a GPU later than that is waited for here, as an event may not be reset while its setting is pending
    if (set->ready) {
        for (int i = 0; set->armed && i < 2000 && vkGetEventStatus(dev.device, set->ready) == VK_EVENT_RESET; i++)
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        vkResetEvent(dev.device, set->ready);
        set->armed = false;
    }
    // (0.4.5-test.1) Dinâmica: the controller's count for this game frame, from the time since the last one
    if (dynamic() != fg.dyn_on) {
        fg.dyn_on = dynamic();
        fg.dyn.reset();
        fg.dyn_frames = allocated();
    }
    if (fg.dyn_on && prev_at) {
        const int was = fg.dyn_frames;
        fg.dyn_frames = fg.dyn.update(now / 1e6, (now - prev_at) / 1e6, fg.refresh_hz.load(std::memory_order_relaxed),
                                      opts.fg_target, allocated());
        fg.dyn_target.store((int)fg.dyn.target(), std::memory_order_relaxed);
        static int told;
        if (fg.dyn_frames != was && told < 300) {
            told++;
            logf("vk: frame interpolation: dynamic %dx -> %dx (%s; shown %.0f fps, target %.0f)", was, fg.dyn_frames,
                 fg.dyn.reason(), fg.dyn.presented(), fg.dyn.target());
        }
    }
    const int cur = fg.cur, prev = cur ^ 1, m = fg.dyn_on ? std::clamp(fg.dyn_frames, 1, fg.mult) : multiplier();
    const bool blend = fg.have_prev && !gap;
    const uint32_t uw = rect.width, uh = rect.height;
    const uint32_t qw = (uw + 3) / 4, qh = (uh + 3) / 4, cw = (qw + 3) / 4, ch = (qh + 3) / 4;
    full_barrier(cmd);
    const int32_t pc[4] = {rect.x, rect.y, (int32_t)uw, (int32_t)uh};
    pass(cmd, fg.copy, {{src, fg.nearest}, {fg.frames[cur].view, VK_NULL_HANDLE}}, uw, uh, pc, sizeof pc);
    pass(cmd, fg.luma, {{fg.frames[cur].view, fg.nearest}, {fg.lumas[cur].view, VK_NULL_HANDLE}}, qw, qh);
    set->made = 0;
    if (blend && m > 1) {
        pass(cmd, fg.flow, {{fg.lumas[prev].view, fg.nearest}, {fg.lumas[cur].view, fg.nearest},
                            {fg.flows[0].view, VK_NULL_HANDLE}}, cw, ch);
        pass(cmd, fg.median, {{fg.flows[0].view, fg.nearest}, {fg.flows[1].view, VK_NULL_HANDLE}}, cw, ch);
        for (int k = 1; k < m; k++) {
            const float t = (float)k / (float)m;
            pass(cmd, fg.synth, {{fg.frames[prev].view, fg.linear}, {fg.frames[cur].view, fg.linear},
                                 {fg.flows[1].view, fg.nearest}, {set->frame[k - 1].view, VK_NULL_HANDLE}},
                 uw, uh, &t, 4);
        }
        set->made = m - 1;
    }
    const VkImageCopy c{{VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}, {0, 0, 0}, {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}, {0, 0, 0},
                        {uw, uh, 1}};
    vkCmdCopyImage(cmd, fg.frames[cur].image, VK_IMAGE_LAYOUT_GENERAL, set->frame[set->made].image,
                   VK_IMAGE_LAYOUT_GENERAL, 1, &c);
    full_barrier(cmd);
    if (set->ready) vkCmdSetEvent(cmd, set->ready, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT), set->armed = true;   // (wait_made)
    fg.have_prev = true;
    fg.cur = prev;
    fg.recorded = set;
    fg.recorded_at = now;
    return true;
}

void framegen_queue(uint64_t value) {
    if (!fg.recorded) return;
    std::lock_guard lk(fg.mu);
    fg.jobs.push_back({fg.recorded, fg.recorded_at, value});
    fg.recorded = nullptr;
    fg.cv.notify_all();
}

} // namespace mkwvk

// (AkynoLeyend r13, Hookshot v2.1.0's MkwVkHost.wide_menus as an export of its own, like akyno_before_exit: vk_api.h stays as
// it is) The game's side, each frame, with ultrawide's margin (of the width, each side): which of nx2/oot_patches.py's keep-list
// screens keep the whole picture. 1 and 3 are the pause and map menus; 0, the item wheel's background, and 2, the fades, always
// cover it all.
extern "C" __declspec(dllexport) uint32_t akyno_wide_menus(float margin) {
    mkwvk::wide_margin.store(margin > 0.0f && margin < 0.5f ? margin : 0.0f, std::memory_order_relaxed);
    return mkwvk::opts.wide_menus ? 0xfu & ~0xau : 0xfu;
}
