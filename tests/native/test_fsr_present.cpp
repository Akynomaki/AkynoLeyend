// Production present functions are extracted unchanged by tools/test_fsr_present.py.
// Only the device, memory allocator and fault-injection wrappers are supplied here.
#include <vulkan/vulkan.h>
#include <algorithm>
#include <cmath>
#include <condition_variable>
#include <cstdarg>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <deque>
#include <mutex>
#include <new>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include "present_crop.h"
#include "shaders/fg_copy_comp_spv.h"
#include "shaders/fg_flow_comp_spv.h"
#include "shaders/fg_luma_comp_spv.h"
#include "shaders/fg_median_comp_spv.h"
#include "shaders/fg_scale_comp_spv.h"
#include "shaders/fg_synth_comp_spv.h"
#include "shaders/fsr_easu_comp_spv.h"
#include "shaders/fsr_rcas_comp_spv.h"
#include "fsr_test_work.inc"

struct VmaAllocation_T { VkDeviceMemory memory; };
using VmaAllocation = VmaAllocation_T*;

namespace mkwvk {
std::atomic<bool> par_active{false};
struct TestDevice { VkDevice device{}; bool push_descriptor = true; std::mutex present_mu; } dev;
struct TestOptions { int upscale = 3, sharpness = 0, framegen = 0; } opts;
VkPhysicalDeviceMemoryProperties memory;
PFN_vkCmdPushDescriptorSetKHR push_descriptor;
int images = 0, views = 0, sets = 0, layouts = 0, pipes = 0, samplers = 0;
int fail_image_after = 0, fail_view_after = 0, fail_pipe_after = 0, fail_sampler_after = 0;
void require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
void checked(VkResult r) { if (r != VK_SUCCESS) throw std::runtime_error("Vulkan error " + std::to_string(r)); }
bool fail(int& after) { return after > 0 && --after == 0; }
void logf(const char* format, ...) {
    va_list ap; va_start(ap, format); std::vprintf(format, ap); va_end(ap); std::puts("");
}
uint32_t memory_type(uint32_t mask, VkMemoryPropertyFlags flags) {
    for (uint32_t i = 0; i < memory.memoryTypeCount; ++i)
        if ((mask & (1u << i)) && (memory.memoryTypes[i].propertyFlags & flags) == flags) return i;
    throw std::runtime_error("memory type unavailable");
}
bool create_image(const VkImageCreateInfo& ci, VkImage& image, VmaAllocation& allocation) {
    if (fail(fail_image_after)) return false;
    checked(vkCreateImage(dev.device, &ci, nullptr, &image));
    VkMemoryRequirements req{}; vkGetImageMemoryRequirements(dev.device, image, &req);
    VkMemoryAllocateInfo ai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
    ai.allocationSize = req.size; ai.memoryTypeIndex = memory_type(req.memoryTypeBits, 0);
    allocation = new VmaAllocation_T{};
    checked(vkAllocateMemory(dev.device, &ai, nullptr, &allocation->memory));
    checked(vkBindImageMemory(dev.device, image, allocation->memory, 0)); ++images; return true;
}
void destroy_image(VkImage image, VmaAllocation allocation) {
    vkDestroyImage(dev.device, image, nullptr); vkFreeMemory(dev.device, allocation->memory, nullptr);
    delete allocation; --images;
}

VkResult test_create_view(VkDevice d, const VkImageViewCreateInfo* c, const VkAllocationCallbacks* a, VkImageView* p) {
    if (fail(fail_view_after)) return VK_ERROR_OUT_OF_HOST_MEMORY;
    auto r = ::vkCreateImageView(d, c, a, p); if (r == VK_SUCCESS) ++views; return r;
}
void test_destroy_view(VkDevice d, VkImageView p, const VkAllocationCallbacks* a) { ::vkDestroyImageView(d, p, a); --views; }
VkResult test_create_set(VkDevice d, const VkDescriptorSetLayoutCreateInfo* c, const VkAllocationCallbacks* a, VkDescriptorSetLayout* p) {
    auto r = ::vkCreateDescriptorSetLayout(d, c, a, p); if (r == VK_SUCCESS) ++sets; return r;
}
void test_destroy_set(VkDevice d, VkDescriptorSetLayout p, const VkAllocationCallbacks* a) { ::vkDestroyDescriptorSetLayout(d, p, a); --sets; }
VkResult test_create_layout(VkDevice d, const VkPipelineLayoutCreateInfo* c, const VkAllocationCallbacks* a, VkPipelineLayout* p) {
    auto r = ::vkCreatePipelineLayout(d, c, a, p); if (r == VK_SUCCESS) ++layouts; return r;
}
void test_destroy_layout(VkDevice d, VkPipelineLayout p, const VkAllocationCallbacks* a) { ::vkDestroyPipelineLayout(d, p, a); --layouts; }
VkResult test_create_pipes(VkDevice d, VkPipelineCache cache, uint32_t n, const VkComputePipelineCreateInfo* c,
                           const VkAllocationCallbacks* a, VkPipeline* p) {
    require(n == 1, "unexpected pipeline batch");
    if (fail(fail_pipe_after)) return VK_ERROR_OUT_OF_HOST_MEMORY;
    auto r = ::vkCreateComputePipelines(d, cache, n, c, a, p); if (r == VK_SUCCESS) ++pipes; return r;
}
void test_destroy_pipe(VkDevice d, VkPipeline p, const VkAllocationCallbacks* a) { ::vkDestroyPipeline(d, p, a); --pipes; }
VkResult test_create_sampler(VkDevice d, const VkSamplerCreateInfo* c, const VkAllocationCallbacks* a, VkSampler* p) {
    if (fail(fail_sampler_after)) return VK_ERROR_OUT_OF_HOST_MEMORY;
    auto r = ::vkCreateSampler(d, c, a, p); if (r == VK_SUCCESS) ++samplers; return r;
}
void test_destroy_sampler(VkDevice d, VkSampler p, const VkAllocationCallbacks* a) { ::vkDestroySampler(d, p, a); --samplers; }

#define vkCmdPushDescriptorSetKHR push_descriptor
#define vkCreateImageView test_create_view
#define vkDestroyImageView test_destroy_view
#define vkCreateDescriptorSetLayout test_create_set
#define vkDestroyDescriptorSetLayout test_destroy_set
#define vkCreatePipelineLayout test_create_layout
#define vkDestroyPipelineLayout test_destroy_layout
#define vkCreateComputePipelines test_create_pipes
#define vkDestroyPipeline test_destroy_pipe
#define vkCreateSampler test_create_sampler
#define vkDestroySampler test_destroy_sampler
#include "fsr_present_production.inc"
#undef vkCmdPushDescriptorSetKHR
#undef vkCreateImageView
#undef vkDestroyImageView
#undef vkCreateDescriptorSetLayout
#undef vkDestroyDescriptorSetLayout
#undef vkCreatePipelineLayout
#undef vkDestroyPipelineLayout
#undef vkCreateComputePipelines
#undef vkDestroyPipeline
#undef vkCreateSampler
#undef vkDestroySampler

void reset() {
    checked(vkDeviceWaitIdle(dev.device));
    for (auto* p : {&fg.copy, &fg.luma, &fg.flow, &fg.median, &fg.synth, &fg.scale, &fg.fsr_easu, &fg.fsr_rcas}) drop_pipe(*p);
    for (auto* i : {&fg.cropped, &fg.scaled, &fg.fsr_color, &fg.fsr_sharpened}) drop_img(*i);
    for (auto* group : {fg.frames, fg.lumas, fg.flows}) for (int i = 0; i < 2; ++i) drop_img(group[i]);
    for (auto& set : fg.sets) for (auto& i : set.frame) drop_img(i);
    if (fg.nearest) test_destroy_sampler(dev.device, fg.nearest, nullptr);
    if (fg.linear) test_destroy_sampler(dev.device, fg.linear, nullptr);
    require(!images && !views && !sets && !layouts && !pipes && !samplers, "live resources after cleanup");
    fg.~State(); new (&fg) State; opts = {};
    fail_image_after = fail_view_after = fail_pipe_after = fail_sampler_after = 0;
}

struct Buffer { VkBuffer buffer{}; VkDeviceMemory memory{}; void* mapped{}; };
struct Fixture {
    VkInstance instance{}; VkPhysicalDevice gpu{}; VkQueue queue{}; VkCommandPool pool{};
    Fixture() {
        VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO}; app.apiVersion = VK_API_VERSION_1_3;
        VkInstanceCreateInfo ic{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO}; ic.pApplicationInfo = &app;
        checked(vkCreateInstance(&ic, nullptr, &instance));
        uint32_t count = 0; checked(vkEnumeratePhysicalDevices(instance, &count, nullptr));
        require(count != 0, "Vulkan device unavailable"); std::vector<VkPhysicalDevice> devices(count);
        checked(vkEnumeratePhysicalDevices(instance, &count, devices.data())); gpu = devices[0];
        VkPhysicalDeviceProperties props{}; vkGetPhysicalDeviceProperties(gpu, &props);
        std::printf("Production present test device: %s\n", props.deviceName);
        vkGetPhysicalDeviceMemoryProperties(gpu, &memory);
        vkGetPhysicalDeviceQueueFamilyProperties(gpu, &count, nullptr); std::vector<VkQueueFamilyProperties> families(count);
        vkGetPhysicalDeviceQueueFamilyProperties(gpu, &count, families.data());
        uint32_t family = 0; while (family < count && !(families[family].queueFlags & VK_QUEUE_COMPUTE_BIT)) ++family;
        require(family < count, "compute queue unavailable"); float priority = 1;
        VkDeviceQueueCreateInfo qi{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO}; qi.queueFamilyIndex = family;
        qi.queueCount = 1; qi.pQueuePriorities = &priority;
        VkPhysicalDeviceVulkan13Features v13{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES}; v13.synchronization2 = VK_TRUE;
        VkPhysicalDeviceFeatures features{}; features.shaderStorageImageExtendedFormats = VK_TRUE;
        const char* extension = VK_KHR_PUSH_DESCRIPTOR_EXTENSION_NAME;
        VkDeviceCreateInfo dc{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO}; dc.pNext = &v13;
        dc.queueCreateInfoCount = 1; dc.pQueueCreateInfos = &qi; dc.enabledExtensionCount = 1;
        dc.ppEnabledExtensionNames = &extension; dc.pEnabledFeatures = &features;
        checked(vkCreateDevice(gpu, &dc, nullptr, &dev.device)); vkGetDeviceQueue(dev.device, family, 0, &queue);
        push_descriptor = reinterpret_cast<PFN_vkCmdPushDescriptorSetKHR>(vkGetDeviceProcAddr(dev.device, "vkCmdPushDescriptorSetKHR"));
        require(push_descriptor != nullptr, "push descriptors unavailable");
        VkCommandPoolCreateInfo pc{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO}; pc.queueFamilyIndex = family;
        checked(vkCreateCommandPool(dev.device, &pc, nullptr, &pool));
    }
    Buffer buffer(VkDeviceSize size) {
        Buffer b; VkBufferCreateInfo ci{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO}; ci.size = size;
        ci.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT;
        checked(vkCreateBuffer(dev.device, &ci, nullptr, &b.buffer)); VkMemoryRequirements req{};
        vkGetBufferMemoryRequirements(dev.device, b.buffer, &req); VkMemoryAllocateInfo ai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
        ai.allocationSize = req.size; ai.memoryTypeIndex = memory_type(req.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
        checked(vkAllocateMemory(dev.device, &ai, nullptr, &b.memory)); checked(vkBindBufferMemory(dev.device, b.buffer, b.memory, 0));
        checked(vkMapMemory(dev.device, b.memory, 0, VK_WHOLE_SIZE, 0, &b.mapped)); return b;
    }
    void drop(Buffer b) {
        vkUnmapMemory(dev.device, b.memory); vkDestroyBuffer(dev.device, b.buffer, nullptr); vkFreeMemory(dev.device, b.memory, nullptr);
    }
    static float half(uint16_t v) {
        const int e = (v >> 10) & 31, m = v & 1023;
        if (e == 31) return NAN;
        const float f = e ? std::ldexp(1.0f + m / 1024.0f, e - 15) : std::ldexp(m / 1024.0f, -14);
        return v & 0x8000 ? -f : f;
    }
    std::vector<float> run(uint32_t sw, uint32_t sh, const int crop[4], uint32_t dw, uint32_t dh,
                           bool constant = false, int image_failure = 0, int view_failure = 0, bool direct = false) {
        Img input, destination;
        require(make_img(input, sw, sh, VK_FORMAT_R8G8B8A8_UNORM,
                         VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT), "input allocation failed");
        Buffer upload = buffer(size_t(sw) * sh * 4), readback = buffer(size_t(dw) * dh * 8);
        auto* bytes = static_cast<uint8_t*>(upload.mapped); std::memset(bytes, 255, size_t(sw) * sh * 4);
        PresentCrop rect;
        if (present_crop(sw, sh, crop, rect)) for (uint32_t y = 0; y < rect.height; ++y) for (uint32_t x = 0; x < rect.width; ++x) {
            const auto at = (size_t(rect.y + y) * sw + rect.x + x) * 4;
            bytes[at] = constant ? 51 : ((x / 5 + y / 5) & 1) ? 230 : 20;
            bytes[at + 1] = constant ? 102 : 80;
            bytes[at + 2] = constant ? 153 : uint8_t(x * 255 / std::max(rect.width - 1, 1u)); bytes[at + 3] = 255;
        }
        VkCommandBufferAllocateInfo ai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO}; ai.commandPool = pool;
        ai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY; ai.commandBufferCount = 1; VkCommandBuffer cmd{};
        checked(vkAllocateCommandBuffers(dev.device, &ai, &cmd)); VkCommandBufferBeginInfo bi{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
        checked(vkBeginCommandBuffer(cmd, &bi)); to_general(cmd, input.image);
        VkBufferImageCopy copy{}; copy.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}; copy.imageExtent = {sw, sh, 1};
        vkCmdCopyBufferToImage(cmd, upload.buffer, input.image, VK_IMAGE_LAYOUT_GENERAL, 1, &copy); full_barrier(cmd);
        fail_image_after = image_failure; fail_view_after = view_failure;
        VkImage output{}; bool fp16 = false;
        if (direct) {
            require(make_img(destination, dw, dh, VK_FORMAT_R8G8B8A8_UNORM,
                             VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT), "blit output allocation failed");
            to_general(cmd, destination.image);
            blit_crop(cmd, input.image, sw, sh, crop, destination.image, VK_IMAGE_LAYOUT_GENERAL, dw, dh); output = destination.image;
        } else {
            output = framegen_scale(cmd, input.view, input.image, sw, sh, crop, dw, dh);
            fp16 = output && (output == fg.fsr_color.image || output == fg.fsr_sharpened.image);
        }
        fail_image_after = fail_view_after = 0;
        if (output) {
            full_barrier(cmd); copy.imageExtent = {dw, dh, 1};
            vkCmdCopyImageToBuffer(cmd, output, VK_IMAGE_LAYOUT_GENERAL, readback.buffer, 1, &copy);
            VkMemoryBarrier2 host{VK_STRUCTURE_TYPE_MEMORY_BARRIER_2}; host.srcStageMask = VK_PIPELINE_STAGE_2_TRANSFER_BIT;
            host.srcAccessMask = VK_ACCESS_2_TRANSFER_WRITE_BIT; host.dstStageMask = VK_PIPELINE_STAGE_2_HOST_BIT; host.dstAccessMask = VK_ACCESS_2_HOST_READ_BIT;
            VkDependencyInfo dependency{VK_STRUCTURE_TYPE_DEPENDENCY_INFO}; dependency.memoryBarrierCount = 1; dependency.pMemoryBarriers = &host;
            vkCmdPipelineBarrier2(cmd, &dependency);
        }
        checked(vkEndCommandBuffer(cmd)); VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO}; submit.commandBufferCount = 1; submit.pCommandBuffers = &cmd;
        checked(vkQueueSubmit(queue, 1, &submit, VK_NULL_HANDLE)); checked(vkQueueWaitIdle(queue));
        std::vector<float> result;
        if (output) {
            result.resize(size_t(dw) * dh * 4);
            for (size_t k = 0; k < result.size(); ++k) {
                result[k] = fp16 ? half(static_cast<uint16_t*>(readback.mapped)[k]) : static_cast<uint8_t*>(readback.mapped)[k] / 255.0f;
                require(std::isfinite(result[k]), "nonfinite output pixel");
            }
        }
        vkFreeCommandBuffers(dev.device, pool, 1, &cmd); drop_img(input); drop_img(destination); drop(upload); drop(readback); return result;
    }
    ~Fixture() {
        if (!dev.device) return;
        vkDeviceWaitIdle(dev.device); vkDestroyCommandPool(dev.device, pool, nullptr);
        vkDestroyDevice(dev.device, nullptr); vkDestroyInstance(instance, nullptr);
    }
};

void same(const std::vector<float>& a, const std::vector<float>& b) {
    require(!a.empty() && a == b, "cropped pixels differ from standalone source");
}
void constant_color(const std::vector<float>& v) {
    require(!v.empty(), "missing constant image");
    for (size_t k = 0; k < v.size(); ++k) {
        const float expected = (k & 3) == 3 ? 1.0f : float((k & 3) + 1) * 0.2f;
        require(std::abs(v[k] - expected) < 0.002f, "constant image changed");
    }
}
void tests(Fixture& f) {
    {
        VkCommandBufferAllocateInfo ai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
        ai.commandPool = f.pool; ai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY; ai.commandBufferCount = 1;
        VkCommandBuffer cmd{}; checked(vkAllocateCommandBuffers(dev.device, &ai, &cmd));
        VkCommandBufferBeginInfo bi{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
        checked(vkBeginCommandBuffer(cmd, &bi));
        const auto before_made = st_barriers_made.load(), before_left = st_barriers_left_out.load();
        full_barrier(cmd); full_barrier(cmd);
        const bool disabled = getenv("RX_VK_BARRIER_DEDUPE_OFF") != nullptr;
        require(st_barriers_made == before_made + (disabled ? 2 : 1), "adjacent empty barrier count wrong");
        require(st_barriers_left_out == before_left + (disabled ? 0 : 1), "empty barrier skip count wrong");
        const auto before_other_thread = st_barriers_made.load();
        std::thread([] { note_work(); }).join(); full_barrier(cmd);
        require(st_barriers_made == before_other_thread + 1, "other thread's work did not invalidate barrier reuse");
        par_active = true; const auto before_parallel = st_barriers_made.load();
        full_barrier(cmd); full_barrier(cmd); par_active = false;
        require(st_barriers_made == before_parallel + 2, "parallel recording reused a barrier");
        checked(vkEndCommandBuffer(cmd)); checked(vkResetCommandPool(dev.device, f.pool, 0));
        checked(vkBeginCommandBuffer(cmd, &bi)); const auto before_reuse = st_barriers_made.load(); full_barrier(cmd);
        require(st_barriers_made == before_reuse + 1, "new recording reused an old barrier");
        checked(vkEndCommandBuffer(cmd)); vkFreeCommandBuffers(dev.device, f.pool, 1, &cmd);
        std::puts("PASS barrier reuse: empty duplicate only, cross-thread work, parallel recording and command-buffer reuse");
    }
    auto plain = f.run(48, 32, nullptr, 113, 71);
    require(!plain.empty() && !fg.init && !fg.copy.pipe && !fg.scale.pipe && pipes == 2, "FSR initialized unrelated pipelines");
    opts.sharpness = 60; auto sharp = f.run(48, 32, nullptr, 113, 71);
    size_t changed = 0; for (size_t k = 0; k < sharp.size(); ++k) { if (std::abs(sharp[k] - plain[k]) > 1e-4f) ++changed; }
    require(changed > 100, "production RCAS has no effect");
    std::printf("PASS production EASU and RCAS; %zu sharpened channels; no FG initialization\n", changed);
    const int crop[]{7, 4, 48, 32}, negative[]{-3, 4, 51, 32};
    same(sharp, f.run(80, 48, crop, 113, 71)); same(sharp, f.run(80, 48, negative, 113, 71));
    const int oversized[]{60, 32, 99, 99};
    same(f.run(20, 16, nullptr, 113, 71), f.run(80, 48, oversized, 113, 71));
    std::puts("PASS positive, negative and oversized crop: bit-identical to standalone source");
    auto old = f.run(80, 48, crop, 113, 71); const int resized[]{7, 4, 44, 30};
    require(f.run(80, 48, resized, 113, 71, false, 1).empty(), "crop allocation fault ignored");
    require(!fg.cropped.image && !fg.cropped_w && !fg.cropped_h, "failed crop retained old dimensions");
    same(old, f.run(80, 48, crop, 113, 71));
    const int count = images;
    require(f.run(80, 48, resized, 113, 71, false, 0, 1).empty(), "image view fault ignored");
    require(images == count - 1, "image leaked after view creation failure");
    same(old, f.run(80, 48, crop, 113, 71));
    std::puts("PASS crop allocation/view failure cleanup and retry at previous dimensions");
    require(f.run(48, 32, nullptr, 117, 73, false, 2).empty(), "second FSR allocation fault ignored");
    require(!fg.fsr_color.image && !fg.fsr_sharpened.image && !fg.fsr_w && !fg.fsr_h, "partial FSR output retained");
    same(sharp, f.run(48, 32, nullptr, 113, 71));
    std::puts("PASS partial FSR output failure cleanup and resize retry");
    constant_color(f.run(640, 360, nullptr, 3840, 2160, true));
    constant_color(f.run(48, 32, nullptr, 113, 71, true));
    std::puts("PASS production 4K output and resize back: finite pixels, constant color and alpha");
    require(!fg.init && !fg.copy.pipe && !fg.scale.pipe, "scaling created FG or unused Lanczos");
    constant_color(f.run(48, 32, nullptr, 24, 16, true));
    require(fg.scale.pipe && !fg.init, "downsampling fallback unavailable");
    require(f.run(48, 32, nullptr, 25, 17, true, 1).empty(), "Lanczos allocation fault ignored");
    require(!fg.scaled.image && !fg.scaled_w && !fg.scaled_h, "failed Lanczos retained old dimensions");
    constant_color(f.run(48, 32, nullptr, 24, 16, true));
    std::puts("PASS explicit downsampling path and allocation failure recovery");
    const int outside[]{100, 100, 5, 5};
    require(f.run(48, 32, outside, 24, 16).empty(), "invalid source crop filtered");
    const auto black = f.run(48, 32, outside, 24, 16, false, 0, 0, true);
    require(!black.empty() && std::all_of(black.begin(), black.end(), [](float v) { return v == 0; }), "invalid blit crop was not cleared");
    std::puts("PASS invalid crop rejected by scaler and cleared by present blit"); reset();
    fail_pipe_after = 2;
    require(!init() && fg.failed && !pipes && !sets && !layouts, "failed FG retained partial pipeline");
    constant_color(f.run(48, 32, nullptr, 113, 71, true));
    require(fg.failed && fg.fsr_ready, "FSR unavailable after FG failure");
    std::puts("PASS FSR remains available after interpolation pipeline failure"); reset();
    fail_pipe_after = 2;
    require(f.run(48, 32, nullptr, 113, 71).empty(), "partial FSR pipeline fault ignored");
    require(!pipes && !sets && !layouts && !fg.fsr_ready, "partial FSR pipeline leaked");
    opts.upscale = 2; constant_color(f.run(48, 32, nullptr, 113, 71, true));
    std::puts("PASS partial FSR pipeline cleanup; other filter remains available"); reset();
    fail_sampler_after = 2;
    require(!init_samplers() && !samplers && !fg.nearest && !fg.linear, "failed sampler pair retained resources");
    require(!init_samplers(), "failed sampler pair reported ready"); reset();
    std::puts("PASS sampler failure cleanup; no remaining test resources");
}
} // namespace mkwvk

int main() {
    try { mkwvk::Fixture fixture; mkwvk::tests(fixture); return 0; }
    catch (const std::exception& e) { std::fprintf(stderr, "FAIL: %s\n", e.what()); return 1; }
}
