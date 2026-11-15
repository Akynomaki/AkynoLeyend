// The Vulkan back end's start: vulkan-1.dll, the instance, the device (Vulkan 1.3 and the extensions the NVN replay
// wants where the GPU has them: mesh shaders, host memory import, graphics pipeline libraries), the window's
// swapchain, and the rx_* table (vk_api.h). The NVN replay itself is vk_replay.cpp.
#include "vk_loader.h"
#include "vk_shader.h"
#include "vk_draw.h"

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

#include "vk_api.h"
#include "vk_internal.h"
#include "boot_options.h"
#include "vk_antilag.h"
#include "vk_reflex.h"
#include "vk_menu.h"   // (AkynoLeyend r13: opts.hdr, the swapchain's surface)

namespace vkx {
#define VKX_DEFINE(f) PFN_##f f;
VKX_GLOBAL(VKX_DEFINE)
VKX_INSTANCE(VKX_DEFINE)
VKX_DEVICE(VKX_DEFINE)
VKX_DEVICE2(VKX_DEFINE)
VKX_DEVICE3(VKX_DEFINE)
#undef VKX_DEFINE

static PFN_vkGetInstanceProcAddr get_instance_proc;

bool load_global() {
    HMODULE m = LoadLibraryA("vulkan-1.dll");   // (linux: libvulkan.so.1, host/posix/win32_posix.c)
    if (!m) return false;
    get_instance_proc = (PFN_vkGetInstanceProcAddr)(void*)GetProcAddress(m, "vkGetInstanceProcAddr");
    if (!get_instance_proc) return false;
#define VKX_LOAD(f) f = (PFN_##f)get_instance_proc(nullptr, #f);
    VKX_GLOBAL(VKX_LOAD)
#undef VKX_LOAD
    return vkCreateInstance != nullptr;
}
PFN_vkGetInstanceProcAddr instance_proc_addr() { return get_instance_proc; }
void load_instance(VkInstance instance) {
#define VKX_LOAD(f) f = (PFN_##f)get_instance_proc(instance, #f);
    VKX_INSTANCE(VKX_LOAD)
#undef VKX_LOAD
}
void load_device(VkDevice device) {
#define VKX_LOAD(f) f = (PFN_##f)vkGetDeviceProcAddr(device, #f);
    VKX_DEVICE(VKX_LOAD)
    VKX_DEVICE2(VKX_LOAD)
    VKX_DEVICE3(VKX_LOAD)
#undef VKX_LOAD
}
} // namespace vkx

namespace mkwvk {





const MkwVkHost* host;
int64_t prof_ns[PROF_COUNT];
Device dev;
std::string device_file_tag() {
    if (dev.auto_device) return "";
    char b[24];
    std::snprintf(b, sizeof b, "_gpu%04x%04x", (unsigned)(dev.props.vendorID & 0xFFFF), (unsigned)(dev.props.deviceID & 0xFFFF));
    return b;
}
PFN_vkGetInstanceProcAddr instance_proc() { return vkx::instance_proc_addr(); }

void logf(const char* fmt, ...) {
    char b[1024];
    std::va_list a;
    va_start(a, fmt);
    std::vsnprintf(b, sizeof b, fmt, a);
    va_end(a);
    if (host) host->log(b);
}

// (AkynoLeyend r9, from Hookshot v2.1.0) The Vulkan 1.3 devices by name, in the order the F1 panel's GPU device row lists them.
std::vector<std::string> gpu_device_names;
namespace {

bool has_extension(const std::vector<VkExtensionProperties>& all, const char* name) {
    for (const auto& e : all)
        if (!std::strcmp(e.extensionName, name)) return true;
    return false;
}

bool create_instance() {
    uint32_t version = VK_API_VERSION_1_0;
    if (vkEnumerateInstanceVersion) vkEnumerateInstanceVersion(&version);
    if (version < VK_API_VERSION_1_3) {
        logf("vk: the Vulkan loader is %u.%u: 1.3 is needed", VK_VERSION_MAJOR(version), VK_VERSION_MINOR(version));
        return false;
    }
#ifdef _WIN32
    const char* exts[] = {VK_KHR_SURFACE_EXTENSION_NAME, VK_KHR_WIN32_SURFACE_EXTENSION_NAME};
    const uint32_t n_exts = 2;
#else
    // (linux: every window system's surface the loader has, for whichever one SDL's window is on: X11 or Wayland)
    const char* exts[4] = {VK_KHR_SURFACE_EXTENSION_NAME};
    uint32_t n_exts = 1;
    {
        uint32_t n = 0;
        vkEnumerateInstanceExtensionProperties(nullptr, &n, nullptr);
        std::vector<VkExtensionProperties> all(n);
        vkEnumerateInstanceExtensionProperties(nullptr, &n, all.data());
        for (const char* want : {"VK_KHR_xlib_surface", "VK_KHR_xcb_surface", "VK_KHR_wayland_surface"})
            if (has_extension(all, want)) exts[n_exts++] = want;
    }
#endif
    VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};
    app.pApplicationName = "mkw-recomp";
    app.apiVersion = VK_API_VERSION_1_3;
    VkInstanceCreateInfo ci{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    ci.pApplicationInfo = &app;
    // (AkynoLeyend r13, Hookshot v2.1.0) the HDR10 colour space for the F1 panel's HDR (the panel's options are read after the
    // instance is made, so whenever the driver has it; the SDR choice in create_swapchain keeps to the 8-bit surface)
    std::vector<const char*> ext_list(exts, exts + n_exts);
    {
        uint32_t n = 0;
        vkEnumerateInstanceExtensionProperties(nullptr, &n, nullptr);
        std::vector<VkExtensionProperties> all(n);
        vkEnumerateInstanceExtensionProperties(nullptr, &n, all.data());
        if (has_extension(all, VK_EXT_SWAPCHAIN_COLOR_SPACE_EXTENSION_NAME))
            ext_list.push_back(VK_EXT_SWAPCHAIN_COLOR_SPACE_EXTENSION_NAME), dev.swapchain_colorspace = true;
    }
    ci.enabledExtensionCount = (uint32_t)ext_list.size();
    ci.ppEnabledExtensionNames = ext_list.data();
    // RX_VK_VALIDATION=1: the Khronos validation layer (when installed)
    const char* layer = "VK_LAYER_KHRONOS_validation";
    if (getenv("RX_VK_VALIDATION")) ci.enabledLayerCount = 1, ci.ppEnabledLayerNames = &layer;
    if (vkCreateInstance(&ci, nullptr, &dev.instance) != VK_SUCCESS) {
        logf("vk: vkCreateInstance failed");
        return false;
    }
    load_instance(dev.instance);
    return true;
}

bool pick_device() {
    uint32_t n = 0;
    vkEnumeratePhysicalDevices(dev.instance, &n, nullptr);
    std::vector<VkPhysicalDevice> all(n);
    vkEnumeratePhysicalDevices(dev.instance, &n, all.data());
    int best = -1, best_score = -1;
    std::vector<int> valid;
    gpu_device_names.clear();
    for (uint32_t i = 0; i < n; i++) {
        VkPhysicalDeviceProperties p;
        vkGetPhysicalDeviceProperties(all[i], &p);
        if (p.apiVersion < VK_API_VERSION_1_3) continue;
        logf("vk: device %d: %s", (int)valid.size(), p.deviceName);
        valid.push_back((int)i);
        gpu_device_names.push_back(p.deviceName);
        const int score = p.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU ? 2 :
                          p.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU ? 1 : 0;
        if (score > best_score) best = (int)i, best_score = score;
    }
    if (best < 0) {
        logf("vk: no Vulkan 1.3 GPU");
        return false;
    }
    const int auto_best = best;
    {   // (RX_VK_DEVICE=<n>, or the panel's GPU device row: that device as listed above; Auto: the best dedicated one)
        const char* e = getenv("RX_VK_DEVICE");
        const int row = e ? atoi(e) + 1 : boot_option("gpu_device", 0);
        const int k = boot_gpu_choice(row, (int)valid.size());
        if (k >= 0) {
            best = valid[k];
            logf("vk: device %d chosen (%s)", k, e ? "RX_VK_DEVICE" : "the panel's GPU device");
        } else if (row > 0) logf("vk: device %d asked for is not there: the best dedicated one is used", row - 1);
    }
    dev.physical = all[best];
    dev.auto_device = best == auto_best;
    vkGetPhysicalDeviceProperties(dev.physical, &dev.props);
    if (!dev.auto_device)
        logf("vk: %s is not the device Auto chooses: its shader and pipeline caches are files of their own (%s)",
             dev.props.deviceName, device_file_tag().c_str());
    vkGetPhysicalDeviceMemoryProperties(dev.physical, &dev.memory);
    return true;
}

bool create_device() {
    uint32_t n = 0;
    vkEnumerateDeviceExtensionProperties(dev.physical, nullptr, &n, nullptr);
    std::vector<VkExtensionProperties> exts(n);
    vkEnumerateDeviceExtensionProperties(dev.physical, nullptr, &n, exts.data());
    std::vector<const char*> want = {VK_KHR_SWAPCHAIN_EXTENSION_NAME};
    auto optional = [&](const char* name, bool& flag) {
        flag = has_extension(exts, name);
        if (flag) want.push_back(name);
    };
    // (AkynoLeyend r13, Hookshot v2.1.0 #1001) the F1 panel's Mesh shaders row, mesh_shaders= in AkynoLeyend_opts.ini, read as the
    // device is made: 0 Automatic (native where there are mesh shaders, the compute fallback where not and for the task + mesh
    // draws of Navi 22 on Windows), 1 Native (no fallback where there are mesh shaders), 2 Compute (the fallback on every GPU).
    // RX_VK_FORCE_MESH_FALLBACK=1, a test, is Compute over it
    static const int mesh_mode = [] {
        int v = boot_option("mesh_shaders", 0);
        if (const char* e = getenv("RX_VK_FORCE_MESH_FALLBACK")) v = atoi(e) != 0 ? 2 : v;
        return v >= 0 && v <= 2 ? v : 0;
    }();
    if (mesh_mode == 2) dev.mesh_shader = false;
    else optional(VK_EXT_MESH_SHADER_EXTENSION_NAME, dev.mesh_shader);
    optional(VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME, dev.external_memory_host);
    optional(VK_KHR_PIPELINE_LIBRARY_EXTENSION_NAME, dev.pipeline_library);
    if (dev.pipeline_library) optional(VK_EXT_GRAPHICS_PIPELINE_LIBRARY_EXTENSION_NAME, dev.graphics_pipeline_library);
    optional(VK_EXT_CUSTOM_BORDER_COLOR_EXTENSION_NAME, dev.custom_border_color);
    optional(VK_EXT_EXTENDED_DYNAMIC_STATE_3_EXTENSION_NAME, dev.dynamic_state3);
    optional(VK_EXT_DEPTH_CLIP_CONTROL_EXTENSION_NAME, dev.depth_clip_control);
    optional(VK_EXT_ROBUSTNESS_2_EXTENSION_NAME, dev.null_descriptor);
    optional(VK_EXT_INDEX_TYPE_UINT8_EXTENSION_NAME, dev.index_uint8);
    optional(VK_KHR_PUSH_DESCRIPTOR_EXTENSION_NAME, dev.push_descriptor);
    optional(VK_EXT_CONDITIONAL_RENDERING_EXTENSION_NAME, dev.conditional_rendering);
    optional(VK_EXT_PROVOKING_VERTEX_EXTENSION_NAME, dev.provoking_vertex);
    optional(VK_EXT_VERTEX_ATTRIBUTE_DIVISOR_EXTENSION_NAME, dev.vertex_divisor);
    optional(VK_EXT_SHADER_STENCIL_EXPORT_EXTENSION_NAME, dev.stencil_export);
    optional(VK_EXT_MEMORY_BUDGET_EXTENSION_NAME, dev.memory_budget);
    optional(VK_EXT_IMAGE_2D_VIEW_OF_3D_EXTENSION_NAME, dev.view_2d_of_3d);
    // (hookshot) on by default: with a marker before each draw and dispatch the device has not been lost (five
    // runs); without them it was, every run, shortly after OoT's first gameplay frames (nvlddmkm event 153; the
    // extension alone, RX_VK_CHECKPOINTS=ext, did not keep it). The race they hide is not found yet.
    // RX_VK_CHECKPOINTS=0: off
    if (!getenv("RX_VK_CHECKPOINTS") || strcmp(getenv("RX_VK_CHECKPOINTS"), "0") != 0)
        optional(VK_NV_DEVICE_DIAGNOSTIC_CHECKPOINTS_EXTENSION_NAME, dev.checkpoints);
    optional(VK_EXT_DEVICE_FAULT_EXTENSION_NAME, dev.device_fault);
    optional(VK_KHR_COOPERATIVE_MATRIX_EXTENSION_NAME, dev.coop_matrix);
    // (AkynoLeyend r13l) the float atomic add, for the translation's (mma_layout.h float_atomic_add_native): not asked for on NVIDIA,
    // whose device and SPIR-V stay as they were
    if (dev.props.vendorID != 0x10DE && !getenv("RX_VK_NO_FLOAT_ATOMIC_ADD"))
        optional(VK_EXT_SHADER_ATOMIC_FLOAT_EXTENSION_NAME, dev.float_atomic_add);
    reflex_device_extensions(want, exts);    // (AkynoLeyend r11, Hookshot v2.1.0: NVIDIA Reflex's, vk_reflex.cpp)
    antilag_device_extensions(want, exts);   // (AkynoLeyend r11, Hookshot v2.1.0: AMD Anti-Lag 2's, vk_antilag.cpp)
    {   // (Hookshot 2.1.0, NVIDIA DLSS: NGX's own extensions, with push descriptors and buffer device addresses enabled
        // above. Only when the launcher asked for DLSS: AKYNO_TEMPORAL_ENGINE=dlss)
        const char* engine = getenv("AKYNO_TEMPORAL_ENGINE");
        if (engine && !strcmp(engine, "dlss")) {
            bool nvx_binary = false, nvx_view = false;
            optional(VK_NVX_BINARY_IMPORT_EXTENSION_NAME, nvx_binary);
            optional(VK_NVX_IMAGE_VIEW_HANDLE_EXTENSION_NAME, nvx_view);
            if (!nvx_binary || !nvx_view) logf("vk: NVIDIA DLSS: this GPU has no NVX binary import / image view handle: no DLSS");
        }
    }

    // the queue: one family for graphics, compute and transfer
    vkGetPhysicalDeviceQueueFamilyProperties(dev.physical, &n, nullptr);
    std::vector<VkQueueFamilyProperties> families(n);
    vkGetPhysicalDeviceQueueFamilyProperties(dev.physical, &n, families.data());
    dev.queue_family = UINT32_MAX;
    for (uint32_t i = 0; i < n && dev.queue_family == UINT32_MAX; i++)
        if ((families[i].queueFlags & (VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT)) ==
            (VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_COMPUTE_BIT))
            dev.queue_family = i;
    if (dev.queue_family == UINT32_MAX) return false;
    const float priority = 1.0f;
    VkDeviceQueueCreateInfo q{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
    q.queueFamilyIndex = dev.queue_family;
    q.queueCount = 1;
    q.pQueuePriorities = &priority;

    // features: what the hardware has of what the replay uses (all of them on the GPUs MKW-class hardware maps to)
    VkPhysicalDeviceMeshShaderFeaturesEXT mesh{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MESH_SHADER_FEATURES_EXT};
    VkPhysicalDeviceRobustness2FeaturesEXT robust2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_ROBUSTNESS_2_FEATURES_EXT};
    VkPhysicalDeviceIndexTypeUint8FeaturesEXT u8{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_INDEX_TYPE_UINT8_FEATURES_EXT};
    VkPhysicalDeviceVulkan13Features f13{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES};
    VkPhysicalDeviceVulkan12Features f12{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES};
    VkPhysicalDeviceVulkan11Features f11{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_1_FEATURES};
    VkPhysicalDeviceFeatures2 f{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};
    f.pNext = &f11, f11.pNext = &f12, f12.pNext = &f13;
    VkPhysicalDeviceExtendedDynamicState3FeaturesEXT eds3{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTENDED_DYNAMIC_STATE_3_FEATURES_EXT};
    VkPhysicalDeviceCustomBorderColorFeaturesEXT border{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_CUSTOM_BORDER_COLOR_FEATURES_EXT};
    VkPhysicalDeviceDepthClipControlFeaturesEXT clip{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DEPTH_CLIP_CONTROL_FEATURES_EXT};
    VkPhysicalDeviceConditionalRenderingFeaturesEXT cond{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_CONDITIONAL_RENDERING_FEATURES_EXT};
    VkPhysicalDeviceProvokingVertexFeaturesEXT pv{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROVOKING_VERTEX_FEATURES_EXT};
    VkPhysicalDeviceGraphicsPipelineLibraryFeaturesEXT gpl{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_GRAPHICS_PIPELINE_LIBRARY_FEATURES_EXT};
    void** tail = &f13.pNext;
    if (dev.mesh_shader) *tail = &mesh, tail = &mesh.pNext;
    if (dev.null_descriptor) *tail = &robust2, tail = &robust2.pNext;
    if (dev.index_uint8) *tail = &u8, tail = &u8.pNext;
    if (dev.dynamic_state3) *tail = &eds3, tail = &eds3.pNext;
    if (dev.custom_border_color) *tail = &border, tail = &border.pNext;
    if (dev.depth_clip_control) *tail = &clip, tail = &clip.pNext;
    if (dev.conditional_rendering) *tail = &cond, tail = &cond.pNext;
    if (dev.provoking_vertex) *tail = &pv, tail = &pv.pNext;
    VkPhysicalDeviceVertexAttributeDivisorFeaturesEXT vdiv{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VERTEX_ATTRIBUTE_DIVISOR_FEATURES_EXT};
    if (dev.vertex_divisor) *tail = &vdiv, tail = &vdiv.pNext;
    if (dev.graphics_pipeline_library) *tail = &gpl, tail = &gpl.pNext;
    VkPhysicalDeviceFaultFeaturesEXT fault{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FAULT_FEATURES_EXT};
    if (dev.device_fault) *tail = &fault, tail = &fault.pNext;
    VkPhysicalDeviceImage2DViewOf3DFeaturesEXT v2d3d{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_2D_VIEW_OF_3D_FEATURES_EXT};
    if (dev.view_2d_of_3d) *tail = &v2d3d, tail = &v2d3d.pNext;
    VkPhysicalDeviceCooperativeMatrixFeaturesKHR coop{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_COOPERATIVE_MATRIX_FEATURES_KHR};
    if (dev.coop_matrix) *tail = &coop, tail = &coop.pNext;
    VkPhysicalDeviceShaderAtomicFloatFeaturesEXT afloat{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_ATOMIC_FLOAT_FEATURES_EXT};
    if (dev.float_atomic_add) *tail = &afloat, tail = &afloat.pNext;
    reflex_device_features(tail);    // (present ids, when NVIDIA Reflex's extensions are there)
    antilag_device_features(tail);   // (AMD Anti-Lag 2's, when its extension is there)
    vkGetPhysicalDeviceFeatures2(dev.physical, &f);
    dev.view_2d_of_3d = dev.view_2d_of_3d && v2d3d.sampler2DViewOf3D;
    coop.cooperativeMatrixRobustBufferAccess = VK_FALSE;
    dev.coop_matrix = dev.coop_matrix && coop.cooperativeMatrix;
    dev.float_atomic_add = dev.float_atomic_add && afloat.shaderBufferFloat32Atomics && afloat.shaderBufferFloat32AtomicAdd;
    {   // (r13l: only the storage buffer float add is asked for)
        const VkBool32 add = dev.float_atomic_add ? VK_TRUE : VK_FALSE;
        afloat = VkPhysicalDeviceShaderAtomicFloatFeaturesEXT{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_ATOMIC_FLOAT_FEATURES_EXT,
                                                              afloat.pNext};
        afloat.shaderBufferFloat32Atomics = afloat.shaderBufferFloat32AtomicAdd = add;
    }
    // (bounds-checked buffer access: an out-of-range access dropped instead of faulting the device. On by default now: the GPU
    // culling pass 53caac5f faulted the device while a save loaded, about one start in three, and the scene's lighting read garbage
    // for single frames (the black flashes); with it, neither in A/B runs at the same GPU time. Lichii's OoT branch keeps it on too.
    // RX_VK_ROBUST=0: off, null descriptors only)
    // (AkynoLeyend r9, from Hookshot v2.1.0: the panel's Robust buffers row, robust_buffers=: 0 Auto and 2 On are on, 1 Off;
    // the variable over it)
    static const bool robust = getenv("RX_VK_ROBUST") ? atoi(getenv("RX_VK_ROBUST")) != 0
                                                        : boot_robust(boot_option("robust_buffers", 0));
    const bool robust_ok = robust && robust2.robustBufferAccess2 && f.features.robustBufferAccess;
    robust2.robustBufferAccess2 = robust_ok ? VK_TRUE : VK_FALSE;
    robust2.robustImageAccess2 = VK_FALSE;
    dev.null_descriptor = dev.null_descriptor && robust2.nullDescriptor;
    pv.transformFeedbackPreservesProvokingVertex = VK_FALSE;
    dev.provoking_vertex = dev.provoking_vertex && pv.provokingVertexLast;
    dev.conditional_rendering = dev.conditional_rendering && cond.conditionalRendering;
    dev.custom_border_color = dev.custom_border_color && border.customBorderColors && border.customBorderColorWithoutFormat;
    dev.depth_clip_control = dev.depth_clip_control && clip.depthClipControl;
    dev.graphics_pipeline_library = dev.graphics_pipeline_library && gpl.graphicsPipelineLibrary;
    if (dev.graphics_pipeline_library) {
        VkPhysicalDeviceGraphicsPipelineLibraryPropertiesEXT lp{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_GRAPHICS_PIPELINE_LIBRARY_PROPERTIES_EXT};
        VkPhysicalDeviceProperties2 p2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2};
        p2.pNext = &lp;
        vkGetPhysicalDeviceProperties2(dev.physical, &p2);
        dev.graphics_pipeline_library = lp.graphicsPipelineLibraryFastLinking != VK_FALSE;
    }
    dev.eds3_polygon = dev.dynamic_state3 && eds3.extendedDynamicState3PolygonMode;
    dev.eds3_clamp = dev.dynamic_state3 && eds3.extendedDynamicState3DepthClampEnable;
    dev.eds3_blend = dev.dynamic_state3 && eds3.extendedDynamicState3ColorBlendEnable &&
                     eds3.extendedDynamicState3ColorBlendEquation && eds3.extendedDynamicState3ColorWriteMask;
    dev.eds3_a2c = dev.dynamic_state3 && eds3.extendedDynamicState3AlphaToCoverageEnable;
    dev.vk12 = f12;
    dev.vk13 = f13;
    {   // (hookshot, after TotK Recomp's vk_caps.c) NVN's programs are written for 32 lanes: the translator is told 32, and the lane
        // shuffles of OoT's networks and the lane masks of its mesh programs depend on it. NVIDIA's GPUs have no other size; AMD's
        // default to 64 where they like, and the networks' output came out as coloured noise (Hookshot issues 10 and 14)
        VkPhysicalDeviceDriverProperties driver{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
        VkPhysicalDeviceSubgroupSizeControlProperties sc{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SUBGROUP_SIZE_CONTROL_PROPERTIES};
        VkPhysicalDeviceSubgroupProperties sg{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SUBGROUP_PROPERTIES};
        sg.pNext = &sc;
        sc.pNext = &driver;
        VkPhysicalDeviceProperties2 p2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2};
        p2.pNext = &sg;
        vkGetPhysicalDeviceProperties2(dev.physical, &p2);
        dev.driver_id = driver.driverID;
        dev.subgroup_stages = sg.supportedStages;
        dev.subgroup_size = sg.subgroupSize;
        dev.subgroup_max = sc.maxSubgroupSize ? sc.maxSubgroupSize : sg.subgroupSize;
        logf("vk: driver %u: %s (%s)", (unsigned)driver.driverID, driver.driverName, driver.driverInfo);
        const bool pin = f13.subgroupSizeControl && sc.minSubgroupSize <= 32 && sc.maxSubgroupSize >= 32 && !getenv("RX_VK_NO_SUBGROUP_PIN");
        dev.sg32_stages = pin ? sc.requiredSubgroupSizeStages : 0;
        logf("vk: subgroups: default %u lanes, %u-%u, pinned to 32 on stages %#x", sg.subgroupSize, sc.minSubgroupSize, sc.maxSubgroupSize,
             (unsigned)dev.sg32_stages);
    }
    if (!f13.dynamicRendering || !f13.synchronization2 || !f12.timelineSemaphore) {
        logf("vk: the GPU lacks dynamic rendering, synchronization2 or timeline semaphores");
        return false;
    }
    mesh.multiviewMeshShader = mesh.primitiveFragmentShadingRateMeshShader = VK_FALSE;   // (not used)
    dev.mesh_shader = dev.mesh_shader && mesh.meshShader && mesh.taskShader;
    // (Hookshot 2.1.0) task and mesh shader counts in pipeline statistics are a feature of their own: RADV has it off on RDNA2,
    // and a query pool made with those counts all the same can hang the GPU
    dev.mesh_queries = dev.mesh_shader && mesh.meshShaderQueries;
    // (AkynoLeyend r13, Hookshot v2.1.0 issue 640) GPUs without mesh shaders (GTX 10xx, RX 5000 and older): task and mesh
    // programs run as compute shaders that write their vertices to buffers, drawn through an ordinary graphics pipeline. It
    // needs buffer device addresses. RX_VK_NO_MESH_FALLBACK=1: none (those draws left out, as before)
    dev.mesh_fallback = !dev.mesh_shader && f12.bufferDeviceAddress && !getenv("RX_VK_NO_MESH_FALLBACK");
    bool task_mesh_fallback = false;
#ifdef _WIN32
    // Navi 22 can time out on task + mesh draws in the AMD Windows driver (Hookshot issue 996).
    task_mesh_fallback = dev.props.vendorID == 0x1002 && dev.props.deviceID == 0x73df;
#endif
    if (mesh_mode == 1) task_mesh_fallback = false;   // (Native: the card's own mesh shaders for every draw)
    if (const char* e = getenv("RX_VK_TASK_MESH_FALLBACK")) task_mesh_fallback = atoi(e) != 0;
    dev.task_mesh_fallback = task_mesh_fallback && dev.mesh_shader && f12.bufferDeviceAddress && !getenv("RX_VK_NO_MESH_FALLBACK");
    logf("vk: mesh shaders: %s (%s); the panel's row: %s",
         dev.mesh_shader ? (dev.task_mesh_fallback ? "native, task + mesh draws on the compute path" : "native")
                         : dev.mesh_fallback ? "the compute path (task and mesh programs as compute shaders)" : "none",
         dev.mesh_shader ? (dev.mesh_queries ? "with their pipeline statistics" : "without their pipeline statistics")
                         : dev.mesh_fallback ? "issue 640 fallback" : "no buffer device addresses: mesh draws left out",
         mesh_mode == 2 ? "Compute" : mesh_mode == 1 ? "Native" : "Automatic");
    if (robust) logf("vk: robust buffer access %s", robust_ok ? "on" : "not supported");
    f.features.robustBufferAccess = robust_ok ? VK_TRUE : VK_FALSE;   // (off by default: the game's accesses stay in their buffers)
    dev.features = f.features;
    dev.sparse_images = (families[dev.queue_family].queueFlags & VK_QUEUE_SPARSE_BINDING_BIT) && f.features.sparseBinding &&
                        f.features.sparseResidencyImage2D && !(getenv("RX_VK_SPARSE") && !atoi(getenv("RX_VK_SPARSE")));
    VkDeviceCreateInfo ci{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
    ci.pNext = &f;
    ci.queueCreateInfoCount = 1;
    ci.pQueueCreateInfos = &q;
    ci.enabledExtensionCount = (uint32_t)want.size();
    ci.ppEnabledExtensionNames = want.data();
    if (vkCreateDevice(dev.physical, &ci, nullptr, &dev.device) != VK_SUCCESS) {
        logf("vk: vkCreateDevice failed");
        return false;
    }


    load_device(dev.device);
    vkGetDeviceQueue(dev.device, dev.queue_family, 0, &dev.queue);
    reflex_device_created();
    antilag_device_created();
    coopmat_init();
    if (dev.push_descriptor) {
        VkPhysicalDevicePushDescriptorPropertiesKHR pp{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PUSH_DESCRIPTOR_PROPERTIES_KHR};
        VkPhysicalDeviceProperties2 p2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2};
        p2.pNext = &pp;
        vkGetPhysicalDeviceProperties2(dev.physical, &p2);
        dev.max_push_descriptors = pp.maxPushDescriptors;
    }
    return true;
}

} // namespace

bool create_swapchain(uint32_t width, uint32_t height) {
    VkSurfaceCapabilitiesKHR caps;
    vkGetPhysicalDeviceSurfaceCapabilitiesKHR(dev.physical, dev.surface, &caps);
    if (caps.currentExtent.width != UINT32_MAX) width = caps.currentExtent.width, height = caps.currentExtent.height;
    if (!width || !height) return false;
    uint32_t n = 0;
    vkGetPhysicalDeviceSurfaceFormatsKHR(dev.physical, dev.surface, &n, nullptr);
    std::vector<VkSurfaceFormatKHR> formats(n);
    vkGetPhysicalDeviceSurfaceFormatsKHR(dev.physical, dev.surface, &n, formats.data());
    VkSurfaceFormatKHR fmt = formats[0];
    for (const auto& f : formats)   // (an UNORM target: the game's window textures are presented as they are)
        if (f.format == VK_FORMAT_B8G8R8A8_UNORM || f.format == VK_FORMAT_R8G8B8A8_UNORM) fmt = f;
    // (AkynoLeyend r13, Hookshot v2.1.0) the F1 panel's HDR: a 10-bit HDR10 surface when the display lists one (Windows: "Use
    // HDR" on in its display settings), the picture then written by framegen_hdr. Otherwise the SDR one above; said whenever
    // which of them it is changes (Hookshot says it once)
    dev.hdr = false;
    if (opts.hdr) {
        for (const auto& f : formats)
            if ((f.format == VK_FORMAT_A2B10G10R10_UNORM_PACK32 || f.format == VK_FORMAT_A2R10G10B10_UNORM_PACK32) &&
                f.colorSpace == VK_COLOR_SPACE_HDR10_ST2084_EXT)
                fmt = f, dev.hdr = true;
    }
    {
        static int told = 0;   // (0 SDR by choice, 1 HDR10, 2 asked for and not listed)
        const int now = dev.hdr ? 1 : opts.hdr ? 2 : 0;
        if (now != told) {
            if (now == 1)
                logf("vk: HDR: an HDR10 surface (format %d), paper white %d nits, peak %d nits", (int)fmt.format, opts.hdr_white,
                     opts.hdr_peak);
            else if (now == 2)
                logf("vk: HDR: the display lists no HDR10 surface%s: SDR",
                     dev.swapchain_colorspace ? " (is HDR on in the display settings?)" : " (no VK_EXT_swapchain_colorspace)");
            else
                logf("vk: HDR: off: the SDR surface");
            told = now;
        }
    }
    // immediate when there is one (the game paces itself: nn_vi.c), else FIFO
    vkGetPhysicalDeviceSurfacePresentModesKHR(dev.physical, dev.surface, &n, nullptr);
    std::vector<VkPresentModeKHR> modes(n);
    vkGetPhysicalDeviceSurfacePresentModesKHR(dev.physical, dev.surface, &n, modes.data());
    VkPresentModeKHR mode = VK_PRESENT_MODE_FIFO_KHR;
    for (auto m : modes)   // (RX_VK_FIFO=1: as on a card or driver with vsync forced, or no mailbox)
        if (m == VK_PRESENT_MODE_MAILBOX_KHR && !getenv("RX_VK_FIFO")) mode = m;
    // (hookshot) no mailbox (AMD's Windows driver has none): immediate before FIFO, which held anything under 60 fps to 30 (40 fps became 30 here)
    for (auto m : modes)
        if (m == VK_PRESENT_MODE_IMMEDIATE_KHR && (getenv("RX_VK_IMMEDIATE") || mode == VK_PRESENT_MODE_FIFO_KHR) && !getenv("RX_VK_FIFO")) mode = m;
    VkSwapchainCreateInfoKHR ci{VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR};
    ci.surface = dev.surface;
    ci.minImageCount = std::max(caps.minImageCount, 4u);   // (hookshot: mailbox with frame interpolation: an image always free)
    if (caps.maxImageCount) ci.minImageCount = std::min(ci.minImageCount, caps.maxImageCount);
    ci.imageFormat = fmt.format;
    ci.imageColorSpace = fmt.colorSpace;
    ci.imageExtent = {width, height};
    ci.imageArrayLayers = 1;
    ci.imageUsage = VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT |
                VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;   // (copied from, for RX_VK_DUMP)
    ci.preTransform = caps.currentTransform;
    ci.compositeAlpha = VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR;
    ci.presentMode = mode;
    ci.clipped = VK_TRUE;
    ci.oldSwapchain = dev.swapchain;
    reflex_swapchain_info(ci);   // (NVIDIA Reflex: latency mode on while its row is on)
    VkSwapchainKHR sc;
    if (vkCreateSwapchainKHR(dev.device, &ci, nullptr, &sc) != VK_SUCCESS) return false;
    if (dev.swapchain) {
        vkDeviceWaitIdle(dev.device);
        reflex_swapchain_destroyed();   // (no latency sleep or marker may use the destroyed chain)
        vkDestroySwapchainKHR(dev.device, dev.swapchain, nullptr);
    }
    dev.swapchain = sc;
    reflex_swapchain_created(sc);
    dev.swap_format = fmt.format;
    dev.swap_extent = {width, height};
    vkGetSwapchainImagesKHR(dev.device, sc, &n, nullptr);
    dev.swap_images.resize(n);
    vkGetSwapchainImagesKHR(dev.device, sc, &n, dev.swap_images.data());
    logf("vk: swapchain %ux%u, %u images, %s", width, height, n,
         mode == VK_PRESENT_MODE_MAILBOX_KHR ? "mailbox" : mode == VK_PRESENT_MODE_IMMEDIATE_KHR ? "immediate" : "fifo");
    return true;
}

namespace {

HWND main_window = nullptr;
bool started_up() {
    if (!replay_start()) return false;
    const bool prepare_only = getenv("RX_VK_PREPARE_ONLY") && atoi(getenv("RX_VK_PREPARE_ONLY")) != 0;
    if (precompile_wanted() || prepare_only) {   // (a release build, before the game: nothing to build during play)
        // (a console while it lasts: there is no window yet, and a long wait with nothing on screen looks like a hang)
        static HANDLE console = nullptr;
        static bool owns_console = false;
        const auto progress = [](size_t done, size_t total) {
            static bool tried = false;
            if (!total) return;
            static size_t last_percent = (size_t)-1, last_total = 0;
            const size_t percent = done * 100 / total;
            if (percent != last_percent || total != last_total || done == total) {
                last_percent = percent; last_total = total;
                std::fprintf(stderr, "@@shader_progress %zu %zu\n", done, total);
                std::fflush(stderr);
            }
            if (getenv("AKYNO_LAUNCHER_PROGRESS")) return;
            if (!tried) {
                tried = true;
                owns_console = AllocConsole() != 0;
                if (owns_console) {
                    SetConsoleTitleA("AkynoLeyend");
                }
                console = CreateFileA("CONOUT$", GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                      nullptr, OPEN_EXISTING, 0, nullptr);
                if (console == INVALID_HANDLE_VALUE) console = nullptr;
            }
            if (!console) return;
            char line[80];
            const int n = snprintf(line, sizeof line, "%cPreparing shaders: %zu of %zu (%zu%%)   ", 13, done, total, done * 100 / total);
            DWORD wrote = 0;
            WriteFile(console, line, (DWORD)n, &wrote, nullptr);
        };
        if (prepare_only && !seed_open()) {
            logf("vk: PREPARE_FAILED: shader seed absent or invalid; exit=71");
            std::fflush(nullptr);
            std::_Exit(71);
        }
        prepare_run(progress);
        precompile_run(progress);
        if (console) CloseHandle(console), console = nullptr;
        if (owns_console) FreeConsole(), owns_console = false;
        std::fprintf(stderr, "@@shader_ready\n");
        std::fflush(stderr);
        if (prepare_only) {
            pipeline_cache_save(true);
            logf("vk: PREPARE_COMPLETE: shader cache prepared; no gameplay started");
            std::fflush(nullptr);
            std::_Exit(0);
        }
    }
    return true;
}
int start(void* hwnd) {
#ifdef _WIN32
    if (hwnd) SetWindowTextA((HWND)hwnd, "AkynoLeyend");
#endif
    main_window = (HWND)hwnd;
    if (!hwnd) {   // (HOS_HEADLESS: no window; the frames are rendered all the same, RX_VK_SHOTS writes them out)
        dev.offscreen = true;
        dev.swap_extent = {1920, 1080};
        dev.swap_format = VK_FORMAT_R8G8B8A8_UNORM;
        logf("vk: no window: presents render offscreen (%ux%u)", dev.swap_extent.width, dev.swap_extent.height);
        return started_up() ? 1 : 0;
    }
#ifdef _WIN32
    VkWin32SurfaceCreateInfoKHR si{VK_STRUCTURE_TYPE_WIN32_SURFACE_CREATE_INFO_KHR};
    si.hinstance = GetModuleHandleA(nullptr);
    si.hwnd = (HWND)hwnd;
    if (vkCreateWin32SurfaceKHR(dev.instance, &si, nullptr, &dev.surface) != VK_SUCCESS) return 0;
    VkBool32 ok = VK_FALSE;
    vkGetPhysicalDeviceSurfaceSupportKHR(dev.physical, dev.queue_family, dev.surface, &ok);
    if (!ok) return 0;
    RECT r{};
    GetClientRect((HWND)hwnd, &r);
    if (!create_swapchain((uint32_t)(r.right - r.left), (uint32_t)(r.bottom - r.top))) return 0;
#else
    const MkwVkWindow* w = (const MkwVkWindow*)hwnd;
    if (w->version != MKWVK_WINDOW_VERSION || !w->create_surface(w->window, (void*)dev.instance, (void*)&dev.surface)) {
        logf("vk: the window's surface could not be made");
        return 0;
    }
    VkBool32 ok = VK_FALSE;
    vkGetPhysicalDeviceSurfaceSupportKHR(dev.physical, dev.queue_family, dev.surface, &ok);
    if (!ok) {
        logf("vk: the GPU's queue cannot present to the window");
        return 0;
    }
    int width = 0, height = 0;
    w->drawable_size(w->window, &width, &height);
    if (!create_swapchain((uint32_t)width, (uint32_t)height)) return 0;
#endif
    return started_up() ? 1 : 0;
}

// (the window's thread: only noted. The swapchain is remade by whoever presents next, in present_image: made here, it went from under a
// frame between its acquire and its submit, and the frame's commands named images of the swapchain just destroyed: a lost device)
void resize(int width, int height) {
    if (dev.offscreen || width <= 0 || height <= 0) return;
    dev.swap_resize.store((uint64_t)(uint32_t)width << 32 | (uint32_t)height, std::memory_order_release);
}

const char* describe() {
    static std::string d;
    d = std::string(dev.props.deviceName) + " (Vulkan, native)";
    return d.c_str();
}

MkwVkRenderer table;

} // namespace
} // namespace mkwvk

extern "C"
#ifdef _WIN32
__declspec(dllexport)
#else
__attribute__((visibility("default")))
#endif
const MkwVkRenderer* mkwvk_init(const MkwVkHost* h) {
    using namespace mkwvk;
    if (!h || h->version != MKWVK_API_VERSION) return nullptr;
    host = h;
    if (!load_global()) {
        logf("vk: vulkan-1.dll not found");
        return nullptr;
    }
    if (!create_instance() || !pick_device() || !create_device()) return nullptr;
    logf("vk: %s, Vulkan %u.%u, driver %#x; mesh shaders %s, host memory import %s, pipeline libraries %s",
         dev.props.deviceName, VK_VERSION_MAJOR(dev.props.apiVersion), VK_VERSION_MINOR(dev.props.apiVersion),
         dev.props.driverVersion, dev.mesh_shader ? "yes" : "no", dev.external_memory_host ? "yes" : "no",
         dev.graphics_pipeline_library ? "yes" : "no");
    table.version = MKWVK_API_VERSION;
    table.start = start;
    table.resize = resize;
    table.describe = describe;
    fill_replay_table(table);
    return &table;
}

namespace mkwvk {
HWND app_window() { return main_window; }   // (hookshot: the Insert menu's Fullscreen row)
} // namespace mkwvk
