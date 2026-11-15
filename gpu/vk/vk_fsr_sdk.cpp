// The game's gameplay upscale drawn by a temporal upscaler: AMD FidelityFX SDK 2.4 (FSR 3.1.6 / 4) or NVIDIA DLSS Super
// Resolution / DLAA. Camera capture and reprojection adapted from Hookshot v2.0.14 (vk_fsr3_inputs.cpp, GPL-3.0); NGX's
// start, the feature and its evaluation from Hookshot 2.1.0 (vk_dlss.cpp, GPL-3.0). Both engines take the same inputs
// (the prepare pass's colour, depth and camera motion, the jitter in render pixels) and write the same output.
//
// AKYNO_TEMPORAL_ENGINE=dlss or fsr4 selects a provider. AKYNO_FSR_TEMPORAL=1 alone requests FSR 3.1.
// NVIDIA's NGX SDK is not part of AkynoLeyend (NVIDIA's license): the build compiles DLSS in only when its headers are in
// third_party/nvidia-dlss-sdk (scripts/ngx_sdk.py fetches them). DLSS's runtime, nvngx_dlss.dll, is never distributed with
// the game: the launcher fetches it from NVIDIA's repository into %LOCALAPPDATA%\AkynoLeyend\ngx after the player accepts
// NVIDIA's license, and passes that folder as AKYNO_DLSS_DIR. NGX's core (_nvngx.dll) is the driver's.
#include "vk_fsr_sdk.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>
#include <windows.h>

#include "../../third_party/amd-fsr-sdk/api/include/vk/ffx_api_vk.h"
#include "../../third_party/amd-fsr-sdk/upscalers/include/ffx_upscale.h"
#if __has_include("../../third_party/nvidia-dlss-sdk/include/nvsdk_ngx_vk.h")
#define AKYNO_NGX 1
#include "../../third_party/nvidia-dlss-sdk/include/nvsdk_ngx_vk.h"
#include "../../third_party/nvidia-dlss-sdk/include/nvsdk_ngx_helpers.h"
#include "../../third_party/nvidia-dlss-sdk/include/nvsdk_ngx_helpers_vk.h"
#endif
#include "boot_options.h"
#include "dlss_math.h"
#include "fsr3_math.h"
#include "menu_option_ids.h"
#include "shaders/fsr_sdk_output_comp_spv.h"
#include "shaders/fsr_sdk_prepare_comp_spv.h"
#include "vk_draw.h"
#include "vk_fsr_options.h"
#include "vk_texture.h"
#include "vk_work.h"

namespace mkwvk {
namespace {

constexpr VkImageUsageFlags kImageUsage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_STORAGE_BIT;
constexpr VkImageSubresourceRange kColorRange{VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
constexpr auto kRead = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
constexpr auto kGeneral = VK_IMAGE_LAYOUT_GENERAL;
constexpr auto kSample = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
constexpr auto kStore = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;

struct Image {
    VkImage image = VK_NULL_HANDLE;
    VkImageView view = VK_NULL_HANDLE;
    VmaAllocation allocation = nullptr;
    VkImageCreateInfo info{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};

    bool create(VkFormat format, uint32_t w, uint32_t h) {
        info.imageType = VK_IMAGE_TYPE_2D;
        info.format = format;
        info.extent = {w, h, 1};
        info.mipLevels = info.arrayLayers = 1;
        info.samples = VK_SAMPLE_COUNT_1_BIT;
        info.tiling = VK_IMAGE_TILING_OPTIMAL;
        info.usage = kImageUsage;
        if (!create_image(info, image, allocation)) return false;
        VkImageViewCreateInfo ci{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
        ci.image = image;
        ci.viewType = VK_IMAGE_VIEW_TYPE_2D;
        ci.format = format;
        ci.subresourceRange = kColorRange;
        return vkCreateImageView(dev.device, &ci, nullptr, &view) == VK_SUCCESS;
    }

    void destroy() {
        if (view) vkDestroyImageView(dev.device, view, nullptr);
        if (image) destroy_image(image, allocation);
        *this = {};
    }

    FfxApiResource resource(uint32_t state) const {
        return ffxApiGetResourceVK(reinterpret_cast<void*>(image),
                                   ffxApiGetImageResourceDescriptionVK(image, info, 0), state);
    }

    void transition(VkCommandBuffer cmd, VkImageLayout before, VkImageLayout after) const {
        VkImageMemoryBarrier2 barrier{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2};
        barrier.oldLayout = before;
        barrier.newLayout = after;
        barrier.srcStageMask = before == VK_IMAGE_LAYOUT_UNDEFINED ? VK_PIPELINE_STAGE_2_NONE : VK_PIPELINE_STAGE_2_COMPUTE_SHADER_BIT;
        barrier.srcAccessMask = before == VK_IMAGE_LAYOUT_UNDEFINED ? 0 : VK_ACCESS_2_SHADER_READ_BIT | VK_ACCESS_2_SHADER_WRITE_BIT;
        barrier.dstStageMask = VK_PIPELINE_STAGE_2_COMPUTE_SHADER_BIT;
        barrier.dstAccessMask = VK_ACCESS_2_SHADER_READ_BIT | VK_ACCESS_2_SHADER_WRITE_BIT;
        barrier.srcQueueFamilyIndex = barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.image = image;
        barrier.subresourceRange = kColorRange;
        VkDependencyInfo dependency{VK_STRUCTURE_TYPE_DEPENDENCY_INFO};
        dependency.imageMemoryBarrierCount = 1;
        dependency.pImageMemoryBarriers = &barrier;
        vkCmdPipelineBarrier2(cmd, &dependency);
    }
};

struct ComputePass {
    VkDescriptorSetLayout set = VK_NULL_HANDLE;
    VkPipelineLayout layout = VK_NULL_HANDLE;
    VkPipeline pipeline = VK_NULL_HANDLE;

    bool create(const uint32_t* code, size_t bytes, uint32_t samples, uint32_t stores, uint32_t push_bytes) {
        VkDescriptorSetLayoutBinding bindings[5]{};
        for (uint32_t i = 0; i < samples + stores; ++i)
            bindings[i] = {i, i < samples ? kSample : kStore, 1, VK_SHADER_STAGE_COMPUTE_BIT, nullptr};
        VkDescriptorSetLayoutCreateInfo si{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
        si.flags = VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR;
        si.bindingCount = samples + stores;
        si.pBindings = bindings;
        if (vkCreateDescriptorSetLayout(dev.device, &si, nullptr, &set) != VK_SUCCESS) return false;
        const VkPushConstantRange range{VK_SHADER_STAGE_COMPUTE_BIT, 0, push_bytes};
        VkPipelineLayoutCreateInfo li{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
        li.setLayoutCount = li.pushConstantRangeCount = 1;
        li.pSetLayouts = &set;
        li.pPushConstantRanges = &range;
        if (vkCreatePipelineLayout(dev.device, &li, nullptr, &layout) != VK_SUCCESS) return false;
        VkShaderModuleCreateInfo mi{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};
        mi.pCode = code;
        mi.codeSize = bytes;
        VkShaderModule module = VK_NULL_HANDLE;
        if (vkCreateShaderModule(dev.device, &mi, nullptr, &module) != VK_SUCCESS) return false;
        VkComputePipelineCreateInfo ci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
        ci.stage = {VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, nullptr, 0, VK_SHADER_STAGE_COMPUTE_BIT, module, "main", nullptr};
        ci.layout = layout;
        const VkResult result = vkCreateComputePipelines(dev.device, VK_NULL_HANDLE, 1, &ci, nullptr, &pipeline);
        vkDestroyShaderModule(dev.device, module, nullptr);
        return result == VK_SUCCESS;
    }

    void record(VkCommandBuffer cmd, const VkDescriptorImageInfo* info, uint32_t samples, uint32_t stores,
                const void* push, uint32_t push_bytes, uint32_t w, uint32_t h) const {
        VkWriteDescriptorSet writes[5]{};
        for (uint32_t i = 0; i < samples + stores; ++i) {
            writes[i] = {VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET};
            writes[i].dstBinding = i;
            writes[i].descriptorCount = 1;
            writes[i].descriptorType = i < samples ? kSample : kStore;
            writes[i].pImageInfo = &info[i];
        }
        vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline);
        vkCmdPushDescriptorSetKHR(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, layout, 0, samples + stores, writes);
        vkCmdPushConstants(cmd, layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, push_bytes, push);
        vkCmdDispatch(cmd, (w + 7) / 8, (h + 7) / 8, 1);
    }
};

struct CameraCapture {
    float view_projection[16]{};
    float jitter[2]{};
    fsr3_math::Camera camera{};
    Texture* depth = nullptr;
    uint64_t generation = 0, frame = 0;
    uint32_t width = 0, height = 0;
};

struct PrepareConstants {
    float reproject[16]{};
    float jitter[2]{};
    int32_t size[2]{};
    int32_t flags = 0;
};
static_assert(sizeof(PrepareConstants) == 84);

enum class Engine { None, Fsr, Fsr4, Dlss };

/// Which temporal upscaler this run asked for (the launcher's environment, read once)
Engine engine() {
    static const Engine e = [] {
        const char* async = std::getenv("RX_VK_ASYNC");
        if (async && std::atoi(async) != 0) return Engine::None;   // (the recording must be serial for the capture)
        const char* which = std::getenv("AKYNO_TEMPORAL_ENGINE");
        if (which && std::strcmp(which, "dlss") == 0) return Engine::Dlss;
        const char* mode = std::getenv("AKYNO_FSR_TEMPORAL");
        const char* sdk = std::getenv("AKYNO_FSR_SDK_DIR");
        if (!mode || std::strcmp(mode, "1") != 0 || !sdk || !*sdk) return Engine::None;
        return which && std::strcmp(which, "fsr4") == 0 ? Engine::Fsr4 : Engine::Fsr;
    }();
    return e;
}

#ifdef AKYNO_NGX
struct Ngx {
    bool tried = false, ok = false;
    NVSDK_NGX_Parameter* caps = nullptr;
    NVSDK_NGX_Parameter* params = nullptr;
    NVSDK_NGX_Handle* feature = nullptr;
    unsigned preset = 0;
    uint64_t made = 0;
};
#endif

// Recording is serial when this mode is requested. The host reads only the
// atomic jitter values, on the threads that build camera uniforms.
struct FfxApi {
    PfnFfxCreateContext create = nullptr;
    PfnFfxDestroyContext destroy = nullptr;
    PfnFfxQuery query = nullptr;
    PfnFfxDispatch dispatch = nullptr;
    uint64_t fsr31 = 0, fsr4 = 0;
};

struct State {
    CameraCapture capture;
    Image color, depth, motion, output;
    ComputePass prepare, resolve;
    VkSampler point = VK_NULL_HANDLE;
    ffxContext context = nullptr;
    // AMD requires the create descriptor chain to live as long as its context.
    ffxOverrideVersion version{};
    ffxCreateContextDescUpscaleVersion headers{};
    ffxCreateBackendVKDesc backend{};
    ffxCreateContextDescUpscale create{};
    bool fsr4_active = false, fsr4_disabled = false;
    std::string provider_name;
#ifdef AKYNO_NGX
    Ngx ngx;
#endif
    uint32_t rw = 0, rh = 0, ow = 0, oh = 0;
    bool infinite_depth = false, initialized = false, failed = false;
    uint64_t last_frame = 0, logged_frames = 0, rejected_frame = UINT64_MAX;
    std::chrono::steady_clock::time_point last_time{};
    float previous_vp[16]{}, previous_jitter[2]{};
    std::atomic<uint32_t> jitter_size{0};
    std::atomic<int> jitter_phases{8};
    Upscaler recorded_upscaler = Upscaler::Off;
    const char* fallback = nullptr;
};
State state;
std::atomic<Upscaler> shown_upscaler{Upscaler::Off};

const char* engine_name() {
    if (engine() == Engine::Dlss) return "NVIDIA DLSS";
    return engine() == Engine::Fsr4 ? "AMD FSR 4" : "AMD FSR SDK";
}

bool fallback(const char* why, bool terminal = false) {
    if (state.fallback != why) logf("vk: %s fallback: %s", engine_name(), why);
    state.fallback = why;
    state.jitter_size.store(0);
    state.last_frame = 0;
    if (terminal) state.failed = true;
    return false;
}

FfxApi load_providers() {
    const wchar_t* root = _wgetenv(L"AKYNO_FSR_SDK_DIR");
    if (!root || !*root) return {};
    const std::wstring path = std::wstring(root) + L"\\amd_fidelityfx_loader_vk.dll";
    // The verified pair is kept together in the SDK folder. Never load the
    // loader from the current working directory or from PATH.
    HMODULE module = LoadLibraryExW(path.c_str(), nullptr,
                                    LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!module) {
        logf("vk: AMD FSR SDK loader error %lu", (unsigned long)GetLastError());
        return {};
    }
    const std::wstring effect = std::wstring(root) + L"\\amd_fidelityfx_upscaler_vk.dll";
    if (!LoadLibraryExW(effect.c_str(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32)) {
        logf("vk: AMD FSR SDK upscaler DLL error %lu", (unsigned long)GetLastError());
        FreeLibrary(module);
        return {};
    }
    FfxApi api;
    api.create = reinterpret_cast<PfnFfxCreateContext>(GetProcAddress(module, "ffxCreateContext"));
    api.destroy = reinterpret_cast<PfnFfxDestroyContext>(GetProcAddress(module, "ffxDestroyContext"));
    api.query = reinterpret_cast<PfnFfxQuery>(GetProcAddress(module, "ffxQuery"));
    api.dispatch = reinterpret_cast<PfnFfxDispatch>(GetProcAddress(module, "ffxDispatch"));
    if (!api.create || !api.destroy || !api.query || !api.dispatch) return {};
    VkDeviceContext device{dev.device, dev.physical, vkGetDeviceProcAddr};
    uint64_t count = 0;
    ffxQueryDescGetVersions versions{{FFX_API_QUERY_DESC_TYPE_GET_VERSIONS, nullptr},
                                    FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE, &device, &count, nullptr, nullptr};
    if (api.query(nullptr, &versions.header) != FFX_API_RETURN_OK || !count || count > 32) return {};
    std::array<uint64_t, 32> ids{};
    std::array<const char*, 32> names{};
    versions.versionIds = ids.data();
    versions.versionNames = names.data();
    if (api.query(nullptr, &versions.header) != FFX_API_RETURN_OK || count > ids.size()) return {};
    for (size_t i = 0; i < count; ++i) {
        if (!names[i] || !ids[i]) continue;
        if (!api.fsr31 && std::strstr(names[i], "3.1.6")) api.fsr31 = ids[i];
        if (!api.fsr4 && dev.props.vendorID == 0x1002 && std::atoi(names[i]) == 4) api.fsr4 = ids[i];
    }
    return api;
}

const FfxApi& ffx_api() {
    static const FfxApi api = load_providers();
    return api;
}

bool make_passes() {
    if (state.point) return true;
    if (!dev.push_descriptor || !vkCmdPushDescriptorSetKHR || !dev.features.shaderStorageImageExtendedFormats) return false;
    if (!state.prepare.create(FSR_SDK_PREPARE_COMP_SPV, sizeof FSR_SDK_PREPARE_COMP_SPV, 2, 3, sizeof(PrepareConstants)) ||
        !state.resolve.create(FSR_SDK_OUTPUT_COMP_SPV, sizeof FSR_SDK_OUTPUT_COMP_SPV, 1, 1, 8)) return false;
    VkSamplerCreateInfo si{VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};
    si.magFilter = si.minFilter = VK_FILTER_NEAREST;
    si.addressModeU = si.addressModeV = si.addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;
    return vkCreateSampler(dev.device, &si, nullptr, &state.point) == VK_SUCCESS;
}

#ifdef AKYNO_NGX
namespace fs = std::filesystem;

std::string utf8(const fs::path& p) {
    const std::wstring& w = p.native();
    const int n = WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    std::string s(n > 0 ? n : 0, '\0');
    if (n > 0) WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), s.data(), n, nullptr, nullptr);
    return s;
}

/// NGX on this device, once (Hookshot 2.1.0's ngx_init): false when DLSS cannot run here, the reason logged
bool ngx_init() {
    Ngx& n = state.ngx;
    if (n.tried) return n.ok;
    n.tried = true;
    // where nvngx_dlss.dll is looked for (NGX takes the newest it finds): the launcher's folder, then the game's ngx folder
    std::vector<fs::path> dirs;
    if (const wchar_t* e = _wgetenv(L"AKYNO_DLSS_DIR"); e && *e) dirs.emplace_back(e);
    std::wstring exe(32768, L'\0');
    const DWORD len = GetModuleFileNameW(nullptr, exe.data(), (DWORD)exe.size());
    if (!len || len >= exe.size()) {
        logf("vk: NVIDIA DLSS: the game's folder could not be found: no DLSS");
        return false;
    }
    exe.resize(len);
    const fs::path game = fs::path(exe).parent_path();
    dirs.push_back(game / L"ngx");
    std::vector<std::wstring> wdirs;
    for (const auto& d : dirs) wdirs.push_back(d.native());
    std::vector<const wchar_t*> paths;
    for (const auto& d : wdirs) paths.push_back(d.c_str());
    // (NGX's own files and logs: the folder the runtime came from when the launcher gave one, else the game's ngx folder)
    const fs::path data = dirs.front();
    std::error_code made;   // (not the throwing overload: a folder that cannot be made must not end the game)
    fs::create_directories(data, made);
    NVSDK_NGX_FeatureCommonInfo info{};
    info.PathListInfo.Path = paths.data();
    info.PathListInfo.Length = (unsigned)paths.size();
    info.LoggingInfo.MinimumLoggingLevel = NVSDK_NGX_LOGGING_LEVEL_OFF;
    // (a project id of AkynoLeyend's own: NGX wants one with the custom engine type, any GUID)
    NVSDK_NGX_Result r = NVSDK_NGX_VULKAN_Init_with_ProjectID("3f6c1d2a-8b4e-4f7a-9c21-5e0d7a6b4c18", NVSDK_NGX_ENGINE_TYPE_CUSTOM,
                                                              "1.0", data.c_str(), dev.instance, dev.physical, dev.device,
                                                              instance_proc(), vkGetDeviceProcAddr, &info);
    if (NVSDK_NGX_FAILED(r)) {
        logf("vk: NVIDIA DLSS: NGX did not start (%#x): not an NVIDIA GPU, or its driver has no NGX", (unsigned)r);
        return false;
    }
    if (NVSDK_NGX_FAILED(NVSDK_NGX_VULKAN_GetCapabilityParameters(&n.caps)) || !n.caps) {
        logf("vk: NVIDIA DLSS: NGX has no capabilities for this device");
        return false;
    }
    // (NGX's C functions, not NVSDK_NGX_Parameter's virtual ones: its object comes from NVIDIA's MSVC-built library, whose
    // vtable order is not the Itanium ABI's that llvm-mingw calls with)
    int available = 0, needs_driver = 0;
    unsigned major = 0, minor = 0;
    NVSDK_NGX_Parameter_GetI(n.caps, NVSDK_NGX_Parameter_SuperSampling_Available, &available);
    NVSDK_NGX_Parameter_GetI(n.caps, NVSDK_NGX_Parameter_SuperSampling_NeedsUpdatedDriver, &needs_driver);
    NVSDK_NGX_Parameter_GetUI(n.caps, NVSDK_NGX_Parameter_SuperSampling_MinDriverVersionMajor, &major);
    NVSDK_NGX_Parameter_GetUI(n.caps, NVSDK_NGX_Parameter_SuperSampling_MinDriverVersionMinor, &minor);
    std::string where;
    for (const auto& d : dirs) where += (where.empty() ? "" : ", ") + utf8(d);
    if (!available) {
        bool runtime = false;
        std::error_code ec;
        for (const auto& d : dirs)
            runtime |= fs::is_regular_file(d / L"nvngx_dlss.dll", ec);
        int init = 0;
        NVSDK_NGX_Parameter_GetI(n.caps, NVSDK_NGX_Parameter_SuperSampling_FeatureInitResult, &init);
        if (needs_driver) logf("vk: NVIDIA DLSS: needs NVIDIA's driver %u.%u or newer", major, minor);
        else if (!runtime) logf("vk: NVIDIA DLSS: not available: no nvngx_dlss.dll in %s (the launcher fetches it)", where.c_str());
        else logf("vk: NVIDIA DLSS: not available on this GPU (%#x): DLSS needs an NVIDIA RTX GPU", (unsigned)init);
        return false;
    }
    if (NVSDK_NGX_FAILED(NVSDK_NGX_VULKAN_AllocateParameters(&n.params)) || !n.params) return false;
    logf("vk: NVIDIA DLSS: NGX started (DLSS's runtime: the newest nvngx_dlss.dll in %s)", where.c_str());
    n.ok = true;
    return true;
}

/// DLSS's preset: AKYNO_DLSS_PRESET=<K|L|M|0> over the default, NVIDIA's own for the mode (the SDK's notes: K for DLAA and
/// the quality modes, M, the second transformer, for Performance at half the output's size and below)
unsigned dlss_preset(uint32_t rw, uint32_t ow) {
    if (const char* e = std::getenv("AKYNO_DLSS_PRESET"); e && *e) {
        const char c = (char)(*e & ~0x20);
        if (*e == '0') return NVSDK_NGX_DLSS_Hint_Render_Preset_Default;
        if (c >= 'A' && c <= 'O') return unsigned(c - 'A' + 1);
    }
    // (AkynoLeyend r10, from Hookshot v2.1.0) The F1 panel's DLSS model row, dlss_model= in the options file, read at the start
    // like the other rows that need one: Auto keeps the choice below
    static const int model = akyno_dlss_model_preset(boot_option("dlss_model", 0));
    if (model >= 0) return unsigned(model);
    return 2 * uint64_t(rw) <= uint64_t(ow) ? NVSDK_NGX_DLSS_Hint_Render_Preset_M : NVSDK_NGX_DLSS_Hint_Render_Preset_K;
}

void dlss_release_feature() {
    if (state.ngx.feature) NVSDK_NGX_VULKAN_ReleaseFeature(state.ngx.feature);
    state.ngx.feature = nullptr;
}

/// DLSS's feature for render size rw x rh and output ow x oh (cmd: its creation's work), as Hookshot 2.1.0's prepare: the
/// quality mode whose range of render sizes holds this one, DLAA when they are the same
bool dlss_feature(VkCommandBuffer cmd, uint32_t rw, uint32_t rh, uint32_t ow, uint32_t oh, bool inverted) {
    Ngx& n = state.ngx;
    static const NVSDK_NGX_PerfQuality_Value scaled[] = {NVSDK_NGX_PerfQuality_Value_MaxQuality, NVSDK_NGX_PerfQuality_Value_Balanced,
                                                        NVSDK_NGX_PerfQuality_Value_MaxPerf,
                                                        NVSDK_NGX_PerfQuality_Value_UltraPerformance};
    const bool aa = rw == ow && rh == oh;
    NVSDK_NGX_PerfQuality_Value mode = NVSDK_NGX_PerfQuality_Value_DLAA;
    unsigned max_w = ow, max_h = oh;
    bool found = aa;
    // (of the modes whose range of render sizes holds this one, the one whose own render size is nearest: Performance at
    // half the output's size, Quality at two thirds. The ranges overlap: the first that held 50% was Quality)
    uint32_t nearest = UINT32_MAX;
    for (const NVSDK_NGX_PerfQuality_Value m : scaled) {
        if (aa) break;
        unsigned w = 0, h = 0, xw = 0, xh = 0, nw = 0, nh = 0;
        float sharp = 0;
        if (NVSDK_NGX_FAILED(NGX_DLSS_GET_OPTIMAL_SETTINGS(n.caps, ow, oh, m, &w, &h, &xw, &xh, &nw, &nh, &sharp)) || !w) continue;
        const uint32_t distance = w > rw ? w - rw : rw - w;
        if (rw >= nw && rh >= nh && rw <= xw && rh <= xh && distance < nearest)
            nearest = distance, mode = m, max_w = rw, max_h = rh, found = true;
    }
    if (!found) return fallback("no DLSS mode takes this render size", true);
    n.preset = dlss_preset(rw, ow);
    for (const char* k : {NVSDK_NGX_Parameter_DLSS_Hint_Render_Preset_DLAA, NVSDK_NGX_Parameter_DLSS_Hint_Render_Preset_Quality,
                          NVSDK_NGX_Parameter_DLSS_Hint_Render_Preset_Balanced, NVSDK_NGX_Parameter_DLSS_Hint_Render_Preset_Performance,
                          NVSDK_NGX_Parameter_DLSS_Hint_Render_Preset_UltraPerformance,
                          NVSDK_NGX_Parameter_DLSS_Hint_Render_Preset_UltraQuality})
        NVSDK_NGX_Parameter_SetUI(n.params, k, n.preset);
    NVSDK_NGX_DLSS_Create_Params cp{};
    cp.Feature.InWidth = max_w, cp.Feature.InHeight = max_h, cp.Feature.InTargetWidth = ow, cp.Feature.InTargetHeight = oh;
    cp.Feature.InPerfQualityValue = mode;
    // (the same inputs AMD's engine gets: LDR colour with no exposure, motion at the render size and not jittered, depth as
    // the prepare pass writes it, inverted as AMD's context is told)
    cp.InFeatureCreateFlags = NVSDK_NGX_DLSS_Feature_Flags_MVLowRes | (inverted ? NVSDK_NGX_DLSS_Feature_Flags_DepthInverted : 0);
    const auto t0 = std::chrono::steady_clock::now();
    const NVSDK_NGX_Result r = NGX_VULKAN_CREATE_DLSS_EXT(cmd, 1, 1, &n.feature, n.params, &cp);
    note_work();   // (NGX's own commands, which vk_work.h does not see: the next full_barrier is not left out)
    const double made_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
    if (NVSDK_NGX_FAILED(r) || !n.feature) {
        logf("vk: NVIDIA DLSS: its feature was not made (%#x) for %ux%u -> %ux%u", (unsigned)r, rw, rh, ow, oh);
        n.feature = nullptr;
        return fallback("its feature was not made", true);
    }
    n.made++;
    const char letter = n.preset ? char('A' + n.preset - 1) : '0';
    logf("vk: NVIDIA DLSS: feature %llu made (%.1f ms of CPU): %ux%u -> %ux%u, %s, preset %c%s",
         (unsigned long long)n.made, made_ms, rw, rh, ow, oh, aa ? "DLAA" : mode == NVSDK_NGX_PerfQuality_Value_MaxPerf ? "Performance" :
         mode == NVSDK_NGX_PerfQuality_Value_Balanced ? "Balanced" : mode == NVSDK_NGX_PerfQuality_Value_MaxQuality ? "Quality" :
         "Ultra Performance", letter, std::getenv("AKYNO_DLSS_PRESET") ? " (AKYNO_DLSS_PRESET)" : "");
    return true;
}

NVSDK_NGX_Resource_VK ngx_resource(const Image& im, bool write) {
    return NVSDK_NGX_Create_ImageView_Resource_VK(im.view, im.image, kColorRange, im.info.format, im.info.extent.width,
                                                  im.info.extent.height, write);
}
#endif

bool engine_built(Engine e) {
#ifdef AKYNO_NGX
    return e != Engine::None;
#else
    return e == Engine::Fsr || e == Engine::Fsr4;
#endif
}

void release_size_resources() {
#ifdef AKYNO_NGX
    dlss_release_feature();
#endif
    if (state.context) ffx_api().destroy(&state.context, nullptr);
    state.context = nullptr;
    state.fsr4_active = false;
    state.color.destroy();
    state.depth.destroy();
    state.motion.destroy();
    state.output.destroy();
    state.initialized = false;
}

bool ready_for(uint32_t rw, uint32_t rh, uint32_t ow, uint32_t oh, bool infinite) {
#ifdef AKYNO_NGX
    const bool made = engine() == Engine::Dlss ? state.ngx.feature != nullptr : state.context != nullptr;
#else
    const bool made = state.context != nullptr;
#endif
    return made && !(state.fsr4_active && state.fsr4_disabled) &&
           state.rw == rw && state.rh == rh && state.ow == ow && state.oh == oh && state.infinite_depth == infinite;
}

bool make_images(uint32_t rw, uint32_t rh, uint32_t ow, uint32_t oh) {
    if (!state.color.create(VK_FORMAT_R16G16B16A16_SFLOAT, rw, rh) ||
        !state.depth.create(VK_FORMAT_R32_SFLOAT, rw, rh) ||
        !state.motion.create(VK_FORMAT_R16G16_SFLOAT, rw, rh) ||
        !state.output.create(VK_FORMAT_R16G16B16A16_SFLOAT, ow, oh)) {
        release_size_resources();
        return fallback("image allocation failed", true);
    }
    state.rw = rw;
    state.rh = rh;
    state.ow = ow;
    state.oh = oh;
    state.last_frame = 0;
    state.jitter_phases.store(dlss_jitter_phases(rw, rh, ow, oh));
    return true;
}

const char* create_fsr_context(uint64_t provider, bool fsr4, uint32_t rw, uint32_t rh, uint32_t ow, uint32_t oh, bool infinite) {
    const FfxApi& api = ffx_api();
    state.version = {{FFX_API_DESC_TYPE_OVERRIDE_VERSION, nullptr}, provider};
    state.headers = {{FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE_VERSION, &state.version.header}, FFX_UPSCALER_VERSION};
    state.backend = {{FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_VK, &state.headers.header},
                     {dev.device, dev.physical, vkGetDeviceProcAddr}};
    uint32_t flags = FFX_UPSCALE_ENABLE_DEPTH_INVERTED | FFX_UPSCALE_ENABLE_AUTO_EXPOSURE;
    if (infinite) flags |= FFX_UPSCALE_ENABLE_DEPTH_INFINITE;
    state.create = {{FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE, &state.backend.header}, flags, {rw, rh}, {ow, oh}, nullptr};
    FfxApiEffectMemoryUsage estimate{};
    ffxQueryDescUpscaleGetGPUMemoryUsageV2 memory{{FFX_API_QUERY_DESC_TYPE_UPSCALE_GPU_MEMORY_USAGE_V2, &state.version.header},
                                                 &state.backend.deviceContext, {rw, rh}, {ow, oh}, flags, &estimate};
    const bool estimated = api.query(nullptr, &memory.header) == FFX_API_RETURN_OK;
    uint64_t used = 0, budget = 0;
    if (vram_usage(&used, &budget) && budget) {
        const uint64_t staging = uint64_t(rw) * rh * 16 + uint64_t(ow) * oh * 8;
        const uint64_t available = budget > used ? budget - used : 0;
        if (staging > available || (estimated && estimate.totalUsageInBytes > available - staging))
            return "estimated FSR allocations exceed the available VRAM budget";
    }
    const ffxReturnCode_t result = api.create(&state.context, &state.create.header, nullptr);
    if (result != FFX_API_RETURN_OK || !state.context) {
        logf("vk: AMD FSR SDK CreateContext returned %u", (unsigned)result);
        if (state.context) api.destroy(&state.context, nullptr);
        state.context = nullptr;
        return "context creation failed";
    }
    ffxQueryGetProviderVersion current{{FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION, nullptr}, 0, nullptr};
    const bool named = api.query(&state.context, &current.header) == FFX_API_RETURN_OK && current.versionName;
    if (fsr4 ? (!named || std::atoi(current.versionName) != 4)
             : (named && !std::strstr(current.versionName, "3.1.6"))) {
        api.destroy(&state.context, nullptr);
        state.context = nullptr;
        return "the loader returned a different upscaler";
    }
    state.fsr4_active = fsr4;
    state.provider_name = fsr4 ? current.versionName : "3.1.6";
    logf("vk: AMD FSR SDK 2.4 context: %s, %ux%u -> %ux%u, estimated SDK VRAM %.1f MiB",
         state.provider_name.c_str(), rw, rh, ow, oh, estimate.totalUsageInBytes / 1048576.0);
    return nullptr;
}

bool setup(VkCommandBuffer cmd, uint32_t rw, uint32_t rh, uint32_t ow, uint32_t oh, bool infinite) {
    if (ready_for(rw, rh, ow, oh, infinite)) return true;
    if (!engine_built(engine())) return fallback("this build has no NVIDIA DLSS (NVIDIA's SDK was not in the build)", true);
#ifdef AKYNO_NGX
    if (engine() == Engine::Dlss && !ngx_init()) return fallback("NGX or DLSS unavailable on this PC", true);
#endif
    if (!make_passes()) return fallback("Vulkan input/output pipelines unavailable", true);
    if (state.context || state.color.image) {
        std::lock_guard lock(dev.present_mu);
        if (vkDeviceWaitIdle(dev.device) != VK_SUCCESS) return fallback("Vulkan device could not drain before resize", true);
        release_size_resources();
    }
#ifdef AKYNO_NGX
    if (engine() == Engine::Dlss) {
        // (the images' estimate against the room left, as AMD's below; NGX's own memory is read back after the feature)
        uint64_t used = 0, budget = 0;
        const uint64_t staging = uint64_t(rw) * rh * 16 + uint64_t(ow) * oh * 8;
        if (vram_usage(&used, &budget) && budget && staging > (budget > used ? budget - used : 0))
            return fallback("estimated DLSS images exceed the available VRAM budget", true);
        if (!dlss_feature(cmd, rw, rh, ow, oh, true)) return false;
        state.infinite_depth = infinite;
        if (!make_images(rw, rh, ow, oh)) return false;
        unsigned long long ngx_bytes = 0;
        NGX_DLSS_GET_STATS(state.ngx.caps, &ngx_bytes);
        logf("vk: NVIDIA DLSS context: %ux%u -> %ux%u, NGX VRAM %.1f MiB", rw, rh, ow, oh, ngx_bytes / 1048576.0);
        return true;
    }
#endif
    (void)cmd;
    const FfxApi& api = ffx_api();
    if (engine() == Engine::Fsr4 && !state.fsr4_disabled) {
        const char* problem = api.fsr4 ? create_fsr_context(api.fsr4, true, rw, rh, ow, oh, infinite)
                                      : "the driver exposes no FSR 4 provider";
        if (problem) {
            logf("vk: AMD FSR 4 unavailable (%s); trying FSR 3.1", problem);
            state.fsr4_disabled = true;
        }
    }
    if (!state.context) {
        if (!api.fsr31) return fallback("provider FSR 3.1.6 unavailable", true);
        if (const char* problem = create_fsr_context(api.fsr31, false, rw, rh, ow, oh, infinite))
            return fallback(problem, true);
    }
    if (!make_images(rw, rh, ow, oh)) return false;
    state.infinite_depth = infinite;
    return true;
}

} // namespace

bool fsr_sdk_requested() {
    return engine() != Engine::None;
}

Upscaler fsr_sdk_active() {
    return shown_upscaler.load(std::memory_order_relaxed);
}

bool fsr_sdk_fsr4_available() {
    return dev.props.vendorID == 0x1002 && ffx_api().fsr4 != 0;
}

void fsr_sdk_scene(const Texture* color, Texture* depth, uint32_t w, uint32_t h, uint64_t address, uint64_t bytes) {
    if (!fsr_sdk_requested() || state.failed || !color || color->format != VK_FORMAT_B10G11R11_UFLOAT_PACK32 ||
        !depth || !(depth->aspect & VK_IMAGE_ASPECT_DEPTH_BIT) || !(depth->usage & VK_IMAGE_USAGE_SAMPLED_BIT) ||
        depth->width != w || depth->height != h || depth->layers != 1 || depth->samples != VK_SAMPLE_COUNT_1_BIT ||
        !address || bytes < 0x230 || w < 640 || h < 360) return;
    const uint64_t frame = texture_frame_no();
    if (state.capture.frame == frame && uint64_t(w) * h <= uint64_t(state.capture.width) * state.capture.height) return;
    float uniform[0x230 / 4];
    if (!memory_read_as_submitted(address, uniform, sizeof uniform) ||
        uniform[0x120 / 4] != float(w) || uniform[0x124 / 4] != float(h)) return;
    CameraCapture capture;
    if (!fsr3_math::camera_from_projection(uniform + 0x70 / 4, capture.camera)) return;
    std::memcpy(capture.view_projection, uniform + 0x30 / 4, sizeof capture.view_projection);
    if (!std::all_of(std::begin(capture.view_projection), std::end(capture.view_projection),
                     [](float x) { return std::isfinite(x); })) return;
    capture.jitter[0] = -uniform[0x78 / 4];
    capture.jitter[1] = -uniform[0x88 / 4];
    if (!std::isfinite(capture.jitter[0]) || !std::isfinite(capture.jitter[1])) return;
    capture.depth = depth;
    capture.generation = texture_destroy_generation();
    capture.frame = frame;
    capture.width = w;
    capture.height = h;
    state.capture = capture;
}

bool fsr_sdk_dispatch(VkCommandBuffer cmd, const Texture& in, VkImageView input_view, Texture& out,
                      VkImageView output_view, uint32_t level) {
    if (!fsr_sdk_requested() || state.failed || !input_view || !output_view ||
        in.image == out.image || in.format != VK_FORMAT_B10G11R11_UFLOAT_PACK32 || out.format != in.format ||
        in.samples != VK_SAMPLE_COUNT_1_BIT || out.samples != VK_SAMPLE_COUNT_1_BIT ||
        in.layers != 1 || out.layers != 1 || level != 0 || out.width < in.width || out.height < in.height) return false;
    const CameraCapture& capture = state.capture;
    const uint64_t frame = texture_frame_no();
    if (frame == state.last_frame || frame == state.rejected_frame || capture.width != in.width || capture.height != in.height) return false;
    if (!capture.depth || capture.frame != frame || capture.generation != texture_destroy_generation())
        return fallback("no valid scene depth/camera for this frame");
    Texture* depth = texture_touch(capture.depth, true);
    if (!depth) return fallback("scene depth is no longer resident");
    nvn_tex depth_info{};
    depth_info.d = depth->d;
    const VkImageView depth_view = texture_view(depth, &depth_info, nullptr, VK_IMAGE_VIEW_TYPE_2D, ViewUse::Sample);
    if (!depth_view) return fallback("scene depth view unavailable");
    if (!setup(cmd, in.width, in.height, out.width, out.height, capture.camera.far_plane == FLT_MAX)) return false;

    PrepareConstants constants;
    constants.size[0] = int32_t(in.width);
    constants.size[1] = int32_t(in.height);
    std::copy_n(capture.jitter, 2, constants.jitter);
    float previous[16];
    std::copy_n(state.previous_vp, 16, previous);
    dlss_math::unjitter(previous, state.previous_jitter);
    const bool continuous = state.last_frame && frame == state.last_frame + 1 &&
                            dlss_math::reprojection(capture.view_projection, previous, constants.reproject);
    constants.flags = (continuous ? 1 : 0) | (capture.camera.flip_depth ? 2 : 0);

    const auto time = std::chrono::steady_clock::now();
    ffxDispatchDescUpscale dispatch{};
    dispatch.header.type = FFX_API_DISPATCH_DESC_TYPE_UPSCALE;
    dispatch.commandList = cmd;
    dispatch.color = state.color.resource(FFX_API_RESOURCE_STATE_COMPUTE_READ);
    dispatch.depth = state.depth.resource(FFX_API_RESOURCE_STATE_COMPUTE_READ);
    dispatch.motionVectors = state.motion.resource(FFX_API_RESOURCE_STATE_COMPUTE_READ);
    dispatch.output = state.output.resource(FFX_API_RESOURCE_STATE_UNORDERED_ACCESS);
    float jitter[2];
    dlss_math::jitter_to_pixels(capture.jitter, in.width, in.height, jitter);
    dispatch.jitterOffset = {jitter[0], jitter[1]};
    dispatch.motionVectorScale = {1.0f, 1.0f};
    dispatch.renderSize = {in.width, in.height};
    dispatch.upscaleSize = {out.width, out.height};
    dispatch.frameTimeDelta = continuous ? std::clamp(std::chrono::duration<float, std::milli>(time - state.last_time).count(),
                                                     1.0f, 250.0f) : 16.667f;
    dispatch.preExposure = 1.0f;
    dispatch.reset = !continuous;
    dispatch.cameraNear = capture.camera.near_plane;
    dispatch.cameraFar = capture.camera.far_plane;
    dispatch.cameraFovAngleVertical = capture.camera.fov_y;
    dispatch.viewSpaceToMetersFactor = 1.0f;

    if (!state.initialized) {
        for (const Image* image : {&state.color, &state.depth, &state.motion, &state.output})
            image->transition(cmd, VK_IMAGE_LAYOUT_UNDEFINED, kGeneral);
        state.initialized = true;
    }
    full_barrier(cmd);
    const VkDescriptorImageInfo prepare_info[] = {{state.point, input_view, kGeneral}, {state.point, depth_view, kGeneral},
        {VK_NULL_HANDLE, state.color.view, kGeneral}, {VK_NULL_HANDLE, state.depth.view, kGeneral},
        {VK_NULL_HANDLE, state.motion.view, kGeneral}};
    state.prepare.record(cmd, prepare_info, 2, 3, &constants, sizeof constants, in.width, in.height);
#ifdef AKYNO_NGX
    if (engine() == Engine::Dlss) {
        // (NVIDIA's evaluation reads and writes the images in the general layout, as Hookshot's: no transitions)
        full_barrier(cmd);
        NVSDK_NGX_Resource_VK color = ngx_resource(state.color, false), depth_in = ngx_resource(state.depth, false),
                              motion = ngx_resource(state.motion, false), output = ngx_resource(state.output, true);
        NVSDK_NGX_VK_DLSS_Eval_Params ep{};
        ep.Feature.pInColor = &color, ep.Feature.pInOutput = &output;
        ep.pInDepth = &depth_in, ep.pInMotionVectors = &motion;
        ep.InJitterOffsetX = jitter[0], ep.InJitterOffsetY = jitter[1];   // (render pixels, x right and y down)
        ep.InRenderSubrectDimensions = {in.width, in.height};
        ep.InReset = continuous ? 0 : 1;
        ep.InMVScaleX = ep.InMVScaleY = 1.0f;
        ep.InFrameTimeDeltaInMsec = dispatch.frameTimeDelta;
        const NVSDK_NGX_Result r = NGX_VULKAN_EVALUATE_DLSS_EXT(cmd, state.ngx.feature, state.ngx.params, &ep);
        note_work();   // (NGX's own commands: the barrier after them is recorded)
        descriptors_disturbed();
        if (NVSDK_NGX_FAILED(r)) {
            full_barrier(cmd);
            logf("vk: NVIDIA DLSS: its evaluation failed (%#x)", (unsigned)r);
            return fallback("upscale evaluation failed", true);
        }
        full_barrier(cmd);
    } else
#endif
    {
        for (const Image* image : {&state.color, &state.depth, &state.motion}) image->transition(cmd, kGeneral, kRead);
        const ffxReturnCode_t result = ffx_api().dispatch(&state.context, &dispatch.header);
        descriptors_disturbed();
        if (result != FFX_API_RETURN_OK) {
            // Only our scratch images were passed to the SDK. The original pass can
            // still write its own target, and recorded SDK work retains its resources.
            full_barrier(cmd);
            logf("vk: AMD FSR SDK Dispatch returned %u", (unsigned)result);
            if (state.fsr4_active) {
                state.fsr4_disabled = true;
                state.rejected_frame = frame;   // the failed dispatch can still be in this frame's recording
                return fallback("upscale dispatch failed; trying FSR 3.1 on the next frame");
            }
            return fallback("upscale dispatch failed", true);
        }
        for (const Image* image : {&state.color, &state.depth, &state.motion}) image->transition(cmd, kRead, kGeneral);
        full_barrier(cmd);
    }
    const VkDescriptorImageInfo output_info[] = {{state.point, state.output.view, kGeneral},
                                                 {VK_NULL_HANDLE, output_view, kGeneral}};
    const int32_t size[] = {int32_t(out.width), int32_t(out.height)};
    state.resolve.record(cmd, output_info, 1, 1, size, sizeof size, out.width, out.height);
    full_barrier(cmd);
    texture_written(&out);
    state.last_frame = frame;
    const bool native = in.width == out.width && in.height == out.height;
    if (engine() == Engine::Dlss) state.recorded_upscaler = native ? Upscaler::Dlaa : Upscaler::Dlss;
    else if (state.fsr4_active) state.recorded_upscaler = native ? Upscaler::Fsr4Native : Upscaler::Fsr4;
    else state.recorded_upscaler = native ? Upscaler::Fsr31Native : Upscaler::Fsr31;
    state.last_time = time;
    std::copy_n(capture.view_projection, 16, state.previous_vp);
    std::copy_n(capture.jitter, 2, state.previous_jitter);
    state.jitter_size.store((in.width << 16) | in.height);
    if (++state.logged_frames == 1 || state.logged_frames % 600 == 0 || state.fallback) {
        if (engine() == Engine::Dlss)
            logf("vk: NVIDIA %s frames=%llu %ux%u -> %ux%u, jitter %+.3f,%+.3f px, camera motion, preset %c",
                 in.width == out.width && in.height == out.height ? "DLAA" : "DLSS", (unsigned long long)state.logged_frames,
                 in.width, in.height, out.width, out.height, jitter[0], jitter[1],
#ifdef AKYNO_NGX
                 state.ngx.preset ? char('A' + state.ngx.preset - 1) : '0'
#else
                 '-'
#endif
            );
        else
            logf("vk: AMD FSR %s SDK frames=%llu %ux%u -> %ux%u, jitter %+.3f,%+.3f px, camera motion%s",
                 state.provider_name.c_str(), (unsigned long long)state.logged_frames, in.width, in.height,
                 out.width, out.height, jitter[0], jitter[1], native ? ", Native AA" : "");
    }
    state.fallback = nullptr;
    return true;
}

int fsr_sdk_jitter(int option) {
    const uint32_t size = state.jitter_size.load();
    if (!size) return 0;
    if (option == HOS_OPT_FSR_JITTER_W) return int(size >> 16);
    if (option == HOS_OPT_FSR_JITTER_H) return int(size & 0xffff);
    if (option == HOS_OPT_FSR_JITTER_PHASES) return state.jitter_phases.load();
    return 0;
}

void fsr_sdk_presented() {
    if (!fsr_sdk_requested()) return;
    const uint64_t frame = texture_frame_no();
    shown_upscaler.store(state.last_frame && frame == state.last_frame ? state.recorded_upscaler : Upscaler::Off,
                         std::memory_order_relaxed);
    if (state.last_frame && frame != state.last_frame) state.jitter_size.store(0);
    if (frame == 600 && !state.logged_frames && !state.failed)
        logf("vk: %s requested; waiting for a supported gameplay upscale pass and its scene inputs", engine_name());
}

/// The game is exiting and the GPU has finished every submission (akyno_before_exit): NGX's feature, parameters and
/// instance released here, before Windows unloads the DLLs. Left to the process's end, a window closed with DLSS on
/// faulted the GPU (nvlddmkm 153, a TDR at the close, a driver that never recovered, the PC down)
bool fsr_sdk_before_exit() {
    if (state.context) {
        ffx_api().destroy(&state.context, nullptr);
        state.context = nullptr;
    }
#ifdef AKYNO_NGX
    Ngx& n = state.ngx;
    if (!n.ok) return false;
    dlss_release_feature();
    if (n.params) NVSDK_NGX_VULKAN_DestroyParameters(n.params);
    if (n.caps) NVSDK_NGX_VULKAN_DestroyParameters(n.caps);
    n.params = n.caps = nullptr;
    NVSDK_NGX_VULKAN_Shutdown1(dev.device);
    n.ok = false;
    return true;
#else
    return false;
#endif
}

} // namespace mkwvk
