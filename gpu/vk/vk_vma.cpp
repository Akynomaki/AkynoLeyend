// Vulkan Memory Allocator (v3.3.0, from Eglantine's CPM cache: nx2/build.py adds its include path): images and
// device buffers are sub-allocated from large blocks (NVIDIA allows ~4096 allocations, and the imported pools
// already take about 2400 of them). Its Vulkan functions come from vkGetInstanceProcAddr / vkGetDeviceProcAddr.
#define VMA_IMPLEMENTATION
#define VMA_STATIC_VULKAN_FUNCTIONS 0
#define VMA_DYNAMIC_VULKAN_FUNCTIONS 1
#include "vk_internal.h"
#include "vram_policy.h"
#include <vk_mem_alloc.h>
#include <algorithm>
#include <cstdlib>
#include <unordered_map>

namespace mkwvk {

VmaAllocator vma;

bool vma_init(PFN_vkGetInstanceProcAddr gipa) {
    VmaVulkanFunctions f{};
    f.vkGetInstanceProcAddr = gipa;
    f.vkGetDeviceProcAddr = vkGetDeviceProcAddr;
    VmaAllocatorCreateInfo ci{};
    ci.flags = VMA_ALLOCATOR_CREATE_BUFFER_DEVICE_ADDRESS_BIT |
               (dev.memory_budget ? VMA_ALLOCATOR_CREATE_EXT_MEMORY_BUDGET_BIT : 0);
    ci.physicalDevice = dev.physical;
    ci.device = dev.device;
    ci.instance = dev.instance;
    ci.vulkanApiVersion = VK_API_VERSION_1_3;
    ci.pVulkanFunctions = &f;
    ci.preferredLargeHeapBlockSize = 64ull << 20;   // (64 MB blocks: Eglantine found 256 MB ones wasted VRAM)
    return vmaCreateAllocator(&ci, &vma) == VK_SUCCESS;
}

// Images come from a pool of 128 MB blocks: on their own, VMA gave most of them dedicated memory (the driver prefers it
// for render targets, and anything over half a default block), a vkAllocateMemory and a kernel call for each, and
// the dynamic resolution makes a new set of render targets every few frames. Images too large for a block, or of a
// memory type the pool's is not, are allocated as before.
// (AkynoLeyend 0.4.5-test.3) Two pools of the same memory type and block size: the textures the game's memory can make
// again (ImagePool::Textures) apart from everything else (render targets, the renderer's own images). In one pool, on an
// RTX 3060 Ti in Hyrule Field: 3919 render targets made in 5 minutes and 2 reused, 1.3-2.1 GB of holes in 3.0-3.4 GB of
// blocks, VRAM 7.5-7.8 GB used of 7.1 allowed, and the compaction (vk_texture.cpp) never ran once: it empties only blocks
// whose every image is an evictable texture, and every block held a target. Apart, a texture block holds textures only, and
// the targets made again and again take the holes their own kind left. RX_VK_IMAGE_POOLS=1: one pool, as before.
VmaPool image_pools[2] = {VK_NULL_HANDLE, VK_NULL_HANDLE};
bool image_pools_tried = false;
uint64_t kImageBlock = 128ull << 20;
// (AkynoLeyend r13e) the pool's images by block: what is allocated in each block, for the compaction (vk_texture.cpp)
std::mutex blocks_mu;
std::unordered_map<VmaAllocation, std::pair<uint64_t, uint64_t>> pool_allocs;   // (allocation -> its block, its size)
std::unordered_map<uint64_t, uint64_t> block_allocated;                          // (block -> bytes allocated in it)
std::unordered_map<uint64_t, int> block_pool;                                    // (block -> the pool it is in)

bool image_pools_split() {
    static const bool one = getenv("RX_VK_IMAGE_POOLS") && atoi(getenv("RX_VK_IMAGE_POOLS")) == 1;
    return !one;
}

uint64_t device_heap_bytes() {
    uint64_t vram = 0;
    for (uint32_t h = 0; h < dev.memory.memoryHeapCount; h++)
        if (dev.memory.memoryHeaps[h].flags & VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) vram = std::max(vram, (uint64_t)dev.memory.memoryHeaps[h].size);
    // (AkynoLeyend r13k) an integrated GPU's heap is the PC's RAM: the small class (vram_policy.h vram_class_bytes)
    static const bool as_large = getenv("RX_VK_IGPU_AS_LARGE") != nullptr;
    const bool integrated = dev.props.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU;
    const uint64_t seen = vram_class_bytes(vram, integrated, as_large);
    static bool said = false;
    if (seen != vram && !said) {
        said = true;
        logf("vk: integrated GPU: its %llu MB heap is the PC's RAM; textures and image blocks as on a card of %llu MB "
             "(64 MB blocks; fine ASTC still as RGBA8)", (unsigned long long)(vram >> 20), (unsigned long long)(seen >> 20));
    }
    return seen;
}

bool device_integrated() {
    return dev.props.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU;
}

uint64_t image_block_size() { return kImageBlock; }

uint64_t image_pool_block_of(VmaAllocation allocation, uint64_t* size) {
    std::lock_guard lk(blocks_mu);
    const auto it = pool_allocs.find(allocation);
    if (it == pool_allocs.end()) return 0;
    if (size) *size = it->second.second;
    return it->second.first;
}

void image_pool_blocks(std::unordered_map<uint64_t, uint64_t>& allocated) {
    std::lock_guard lk(blocks_mu);
    allocated = block_allocated;
}

VmaPool images_pool(ImagePool kind) {
    if (image_pools_tried) return image_pools[image_pools_split() && kind == ImagePool::Textures ? 0 : 1];
    image_pools_tried = true;
    VkImageCreateInfo rep{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};   // (a representative image: the pool's memory type)
    rep.imageType = VK_IMAGE_TYPE_2D;
    rep.format = VK_FORMAT_R8G8B8A8_UNORM;
    rep.extent = {256, 256, 1};
    rep.mipLevels = rep.arrayLayers = 1;
    rep.samples = VK_SAMPLE_COUNT_1_BIT;
    rep.usage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT;
    VmaAllocationCreateInfo ai{};
    ai.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE;
    ai.requiredFlags = VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT;
    uint32_t type = 0;
    if (vmaFindMemoryTypeIndexForImageInfo(vma, &rep, &ai, &type) != VK_SUCCESS) return VK_NULL_HANDLE;
    // (AkynoLeyend r13e) 64 MB blocks on cards of 8 GB and less (vram_policy.h); RX_VK_IMAGE_BLOCK_MB: that size
    if (const char* e = getenv("RX_VK_IMAGE_BLOCK_MB")) kImageBlock = (uint64_t)std::clamp(atoi(e), 16, 512) << 20;
    else kImageBlock = image_block_bytes(device_heap_bytes());
    VmaPoolCreateInfo pi{};
    pi.memoryTypeIndex = type;
    pi.blockSize = kImageBlock;
    for (int p = image_pools_split() ? 0 : 1; p < 2; p++)
        if (vmaCreatePool(vma, &pi, &image_pools[p]) != VK_SUCCESS) image_pools[p] = VK_NULL_HANDLE;
    if (image_pools_split() && !image_pools[0]) image_pools[0] = image_pools[1];   // (one made: both kinds there)
    if (image_pools_split() && !image_pools[1]) image_pools[1] = image_pools[0];
    logf("vk: images from %s of %llu MB blocks (memory type %u)%s",
         image_pools_split() ? "two pools (textures; targets and the rest)" : "one pool (RX_VK_IMAGE_POOLS=1)",
         (unsigned long long)(kImageBlock >> 20), type, image_pools[1] ? "" : ": not made");
    return image_pools[image_pools_split() && kind == ImagePool::Textures ? 0 : 1];
}

bool create_image(const VkImageCreateInfo& ci, VkImage& image, VmaAllocation& allocation, ImagePool kind) {
    VmaAllocationCreateInfo ai{};
    ai.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE;
    // (in VRAM or not at all: an image VMA puts in system memory when VRAM is full is read over PCIe every frame,
    // and takes the RAM the game and everything else on the machine need)
    ai.requiredFlags = VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT;
    if (dev.memory_budget) ai.flags = VMA_ALLOCATION_CREATE_WITHIN_BUDGET_BIT;
    static const bool no_pool = getenv("RX_VK_NO_IMAGE_POOL") != nullptr;
    if (VmaPool pool = no_pool ? VK_NULL_HANDLE : images_pool(kind)) {
        VmaAllocationCreateInfo pai = ai;
        pai.pool = pool;
        pai.usage = VMA_MEMORY_USAGE_UNKNOWN;
        VmaAllocationInfo info{};
        if (vmaCreateImage(vma, &ci, &pai, &image, &allocation, &info) == VK_SUCCESS) {
            const uint64_t block = (uint64_t)(uintptr_t)info.deviceMemory;
            std::lock_guard lk(blocks_mu);
            pool_allocs[allocation] = {block, info.size};
            block_allocated[block] += info.size;
            block_pool[block] = pool == image_pools[0] && image_pools[0] != image_pools[1] ? 0 : 1;
            return true;
        }
    }
    if (vmaCreateImage(vma, &ci, &ai, &image, &allocation, nullptr) == VK_SUCCESS) return true;
    // (hookshot) VRAM is full (a 4 GB card at a high resolution, #96): an image left unmade is a black screen, so it goes
    // to system memory instead, slow but drawn
    if (getenv("RX_VK_IMAGES_VRAM_ONLY")) return false;
    VmaAllocationCreateInfo sai{};
    sai.usage = VMA_MEMORY_USAGE_AUTO;
    if (vmaCreateImage(vma, &ci, &sai, &image, &allocation, nullptr) != VK_SUCCESS) return false;
    static std::atomic<int> told{0};
    if (told++ < 4) logf("vk: VRAM full: a %ux%u image (format %d) in system memory", ci.extent.width, ci.extent.height, (int)ci.format);
    return true;
}
void destroy_image(VkImage image, VmaAllocation allocation) {
    {
        std::lock_guard lk(blocks_mu);
        const auto it = pool_allocs.find(allocation);
        if (it != pool_allocs.end()) {
            const auto b = block_allocated.find(it->second.first);
            if (b != block_allocated.end() && (b->second -= std::min(b->second, it->second.second)) == 0) {
                block_pool.erase(b->first);
                block_allocated.erase(b);
            }
            pool_allocs.erase(it);
        }
    }
    vmaDestroyImage(vma, image, allocation);
}
bool create_buffer(uint64_t size, VkBufferUsageFlags usage, bool host_visible, VkBuffer& buffer,
                   VmaAllocation& allocation, void** mapped) {
    VkBufferCreateInfo bi{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
    bi.size = size;
    bi.usage = usage;
    VmaAllocationCreateInfo ai{};
    ai.usage = VMA_MEMORY_USAGE_AUTO;
    if (host_visible) ai.flags = VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT | VMA_ALLOCATION_CREATE_MAPPED_BIT;
    VmaAllocationInfo info{};
    if (vmaCreateBuffer(vma, &bi, &ai, &buffer, &allocation, &info) != VK_SUCCESS) return false;
    if (mapped) *mapped = info.pMappedData;
    return true;
}
/// A buffer in cached host memory, mapped: written on one thread, read back on the CPU too (the captures: the game's
/// threads copy pages into it, the replay reads texture pages out of it and the GPU copies the rest from it)
bool create_buffer_cached(uint64_t size, VkBufferUsageFlags usage, VkBuffer& buffer, VmaAllocation& allocation,
                          void** mapped) {
    VkBufferCreateInfo bi{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
    bi.size = size;
    bi.usage = usage;
    VmaAllocationCreateInfo ai{};
    ai.usage = VMA_MEMORY_USAGE_AUTO_PREFER_HOST;
    ai.flags = VMA_ALLOCATION_CREATE_HOST_ACCESS_RANDOM_BIT | VMA_ALLOCATION_CREATE_MAPPED_BIT;
    VmaAllocationInfo info{};
    if (vmaCreateBuffer(vma, &bi, &ai, &buffer, &allocation, &info) != VK_SUCCESS) return false;
    if (mapped) *mapped = info.pMappedData;
    return true;
}
void flush_mapped(VmaAllocation allocation, uint64_t size) {
    if (size) vmaFlushAllocation(vma, allocation, 0, size);
}
void flush_mapped_range(VmaAllocation allocation, uint64_t offset, uint64_t size) {
    if (size) vmaFlushAllocation(vma, allocation, offset, size);
}
void destroy_buffer(VkBuffer buffer, VmaAllocation allocation) {
    vmaDestroyBuffer(vma, buffer, allocation);
}
bool create_device_buffer(uint64_t size, VkBufferUsageFlags usage, VkBuffer& buffer, VmaAllocation& allocation) {
    VkBufferCreateInfo bi{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
    bi.size = size;
    bi.usage = usage;
    VmaAllocationCreateInfo ai{};
    ai.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE;
    ai.requiredFlags = VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT;
    if (dev.memory_budget) ai.flags = VMA_ALLOCATION_CREATE_WITHIN_BUDGET_BIT;
    return vmaCreateBuffer(vma, &bi, &ai, &buffer, &allocation, nullptr) == VK_SUCCESS;
}
/// (every heap: what VMA has in blocks and allocations there, what the process uses of it, its budget; one line)
void vma_log_heaps() {
    VmaBudget b[VK_MAX_MEMORY_HEAPS]{};
    vmaGetHeapBudgets(vma, b);
    char line[1024];
    int n = snprintf(line, sizeof line, "vk: memory heaps:");
    for (uint32_t h = 0; h < dev.memory.memoryHeapCount && n < 900; h++)
        n += snprintf(line + n, sizeof line - n, " heap %u%s: %u blocks %llu MB, %u allocations %llu MB; used %llu of %llu MB;", h,
                      (dev.memory.memoryHeaps[h].flags & VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) ? " (device)" : " (system)",
                      b[h].statistics.blockCount, (unsigned long long)(b[h].statistics.blockBytes >> 20),
                      b[h].statistics.allocationCount, (unsigned long long)(b[h].statistics.allocationBytes >> 20),
                      (unsigned long long)(b[h].usage >> 20), (unsigned long long)(b[h].budget >> 20));
    logf("%s", line);
    {   // (AkynoLeyend r13e) the image pool's blocks with images in them, and the holes they hold
        // (0.4.5-test.3: and by pool, textures and the rest)
        std::lock_guard lk(blocks_mu);
        uint64_t allocated = 0, by_alloc[2] = {}, by_blocks[2] = {};
        for (const auto& kv : block_allocated) {
            allocated += kv.second;
            const auto p = block_pool.find(kv.first);
            const int k = p == block_pool.end() ? 1 : p->second;
            by_alloc[k] += kv.second, by_blocks[k]++;
        }
        const uint64_t held = (uint64_t)block_allocated.size() * kImageBlock;
        const auto holes = [](uint64_t blocks, uint64_t bytes) { return (blocks * kImageBlock - std::min(blocks * kImageBlock, bytes)) >> 20; };
        logf("vk: image pool: %zu blocks of %llu MB (%llu MB), %llu MB of images, %llu MB of holes; textures %llu blocks (%llu MB "
             "of holes), targets and the rest %llu blocks (%llu MB of holes)", block_allocated.size(),
             (unsigned long long)(kImageBlock >> 20), (unsigned long long)(held >> 20), (unsigned long long)(allocated >> 20),
             (unsigned long long)((held - std::min(held, allocated)) >> 20), (unsigned long long)by_blocks[0],
             (unsigned long long)holes(by_blocks[0], by_alloc[0]), (unsigned long long)by_blocks[1],
             (unsigned long long)holes(by_blocks[1], by_alloc[1]));
    }
}
bool vram_usage(uint64_t* used, uint64_t* budget, uint64_t* block_free) {
    VmaBudget b[VK_MAX_MEMORY_HEAPS]{};
    vmaGetHeapBudgets(vma, b);
    uint64_t u = 0, t = 0, f = 0;
    for (uint32_t h = 0; h < dev.memory.memoryHeapCount; h++)
        if (dev.memory.memoryHeaps[h].flags & VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) {
            u += b[h].usage, t += b[h].budget;
            // (the free space in VMA's blocks: the driver counts it as the process's, new allocations take it first)
            f += b[h].statistics.blockBytes - std::min(b[h].statistics.blockBytes, b[h].statistics.allocationBytes);
        }
    *used = u, *budget = t;
    if (block_free) *block_free = f;
    return t != 0;
}

} // namespace mkwvk
