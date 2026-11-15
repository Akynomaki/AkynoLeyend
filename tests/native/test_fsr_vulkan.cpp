// Execute the production SPIR-V filters with synthetic SDR images. No game data or physical GPU required.
#include <vulkan/vulkan.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>
#include "shaders/fsr_easu_comp_spv.h"
#include "shaders/fsr_rcas_comp_spv.h"

void checked(VkResult r){if(r!=VK_SUCCESS)throw std::runtime_error("Vulkan error "+std::to_string(r));}
struct Buffer{VkBuffer b{};VkDeviceMemory mem{};void* map{};};
struct Image{VkImage im{};VkImageView view{};VkDeviceMemory mem{};};
struct Fixture{
 VkInstance instance{};VkPhysicalDevice gpu{};VkDevice dev{};VkQueue queue{};VkCommandPool pool{};
 VkPhysicalDeviceMemoryProperties props{};VkDescriptorSetLayout set{};VkPipelineLayout layout{};VkSampler sampler{};
 VkPipeline easu{},rcas{};PFN_vkCmdPushDescriptorSetKHR push{};std::vector<Buffer> buffers;std::vector<Image> images;
 Fixture(){
  VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};app.apiVersion=VK_API_VERSION_1_3;
  VkInstanceCreateInfo ci{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};ci.pApplicationInfo=&app;checked(vkCreateInstance(&ci,nullptr,&instance));
  uint32_t n=0;checked(vkEnumeratePhysicalDevices(instance,&n,nullptr));if(!n)throw std::runtime_error("no Vulkan device");
  std::vector<VkPhysicalDevice> devices(n);checked(vkEnumeratePhysicalDevices(instance,&n,devices.data()));gpu=devices[0];
  VkPhysicalDeviceProperties info{};vkGetPhysicalDeviceProperties(gpu,&info);std::printf("Vulkan device: %s\n",info.deviceName);
  vkGetPhysicalDeviceMemoryProperties(gpu,&props);vkGetPhysicalDeviceQueueFamilyProperties(gpu,&n,nullptr);
  std::vector<VkQueueFamilyProperties> families(n);vkGetPhysicalDeviceQueueFamilyProperties(gpu,&n,families.data());
  uint32_t family=0;while(family<n&&!(families[family].queueFlags&VK_QUEUE_COMPUTE_BIT))++family;
  if(family==n)throw std::runtime_error("no compute queue");float priority=1;
  VkDeviceQueueCreateInfo qi{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};qi.queueFamilyIndex=family;qi.queueCount=1;qi.pQueuePriorities=&priority;
  const char* ext=VK_KHR_PUSH_DESCRIPTOR_EXTENSION_NAME;VkPhysicalDeviceFeatures features{};features.shaderStorageImageExtendedFormats=VK_TRUE;
  VkDeviceCreateInfo dc{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};dc.queueCreateInfoCount=1;dc.pQueueCreateInfos=&qi;dc.enabledExtensionCount=1;dc.ppEnabledExtensionNames=&ext;dc.pEnabledFeatures=&features;
  checked(vkCreateDevice(gpu,&dc,nullptr,&dev));vkGetDeviceQueue(dev,family,0,&queue);
  push=(PFN_vkCmdPushDescriptorSetKHR)vkGetDeviceProcAddr(dev,"vkCmdPushDescriptorSetKHR");if(!push)throw std::runtime_error("no push descriptors");
  VkCommandPoolCreateInfo pc{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};pc.queueFamilyIndex=family;checked(vkCreateCommandPool(dev,&pc,nullptr,&pool));
  VkDescriptorSetLayoutBinding bs[2]{{0,VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,1,VK_SHADER_STAGE_COMPUTE_BIT,nullptr},{1,VK_DESCRIPTOR_TYPE_STORAGE_IMAGE,1,VK_SHADER_STAGE_COMPUTE_BIT,nullptr}};
  VkDescriptorSetLayoutCreateInfo sc{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};sc.flags=VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR;sc.bindingCount=2;sc.pBindings=bs;
  checked(vkCreateDescriptorSetLayout(dev,&sc,nullptr,&set));VkPushConstantRange range{VK_SHADER_STAGE_COMPUTE_BIT,0,4};
  VkPipelineLayoutCreateInfo lc{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};lc.setLayoutCount=1;lc.pSetLayouts=&set;lc.pushConstantRangeCount=1;lc.pPushConstantRanges=&range;checked(vkCreatePipelineLayout(dev,&lc,nullptr,&layout));
  VkSamplerCreateInfo si{VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO};si.magFilter=si.minFilter=VK_FILTER_LINEAR;si.addressModeU=si.addressModeV=si.addressModeW=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;checked(vkCreateSampler(dev,&si,nullptr,&sampler));
  easu=pipeline(FSR_EASU_COMP_SPV,sizeof FSR_EASU_COMP_SPV);rcas=pipeline(FSR_RCAS_COMP_SPV,sizeof FSR_RCAS_COMP_SPV);
 }
 uint32_t type(uint32_t mask,VkMemoryPropertyFlags flags){for(uint32_t i=0;i<props.memoryTypeCount;++i)if((mask&(1u<<i))&&(props.memoryTypes[i].propertyFlags&flags)==flags)return i;throw std::runtime_error("memory type missing");}
 VkPipeline pipeline(const uint32_t* code,size_t size){
  VkShaderModuleCreateInfo mi{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO};mi.codeSize=size;mi.pCode=code;VkShaderModule m{};checked(vkCreateShaderModule(dev,&mi,nullptr,&m));
  VkComputePipelineCreateInfo ci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};ci.stage.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;ci.stage.stage=VK_SHADER_STAGE_COMPUTE_BIT;ci.stage.module=m;ci.stage.pName="main";ci.layout=layout;
  VkPipeline p{};checked(vkCreateComputePipelines(dev,{},1,&ci,nullptr,&p));vkDestroyShaderModule(dev,m,nullptr);return p;
 }
 Buffer buffer(VkDeviceSize size){Buffer b;VkBufferCreateInfo ci{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};ci.size=size;ci.usage=VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT;checked(vkCreateBuffer(dev,&ci,nullptr,&b.b));
  VkMemoryRequirements req{};vkGetBufferMemoryRequirements(dev,b.b,&req);VkMemoryAllocateInfo ai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ai.allocationSize=req.size;ai.memoryTypeIndex=type(req.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);checked(vkAllocateMemory(dev,&ai,nullptr,&b.mem));checked(vkBindBufferMemory(dev,b.b,b.mem,0));checked(vkMapMemory(dev,b.mem,0,VK_WHOLE_SIZE,0,&b.map));buffers.push_back(b);return b;}
 Image image(uint32_t w,uint32_t h,VkFormat format){Image i;VkImageCreateInfo ci{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};ci.imageType=VK_IMAGE_TYPE_2D;ci.format=format;ci.extent={w,h,1};ci.mipLevels=ci.arrayLayers=1;ci.samples=VK_SAMPLE_COUNT_1_BIT;ci.usage=VK_IMAGE_USAGE_STORAGE_BIT|VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT;checked(vkCreateImage(dev,&ci,nullptr,&i.im));
  VkMemoryRequirements req{};vkGetImageMemoryRequirements(dev,i.im,&req);VkMemoryAllocateInfo ai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};ai.allocationSize=req.size;ai.memoryTypeIndex=type(req.memoryTypeBits,0);checked(vkAllocateMemory(dev,&ai,nullptr,&i.mem));checked(vkBindImageMemory(dev,i.im,i.mem,0));
  VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};vi.image=i.im;vi.viewType=VK_IMAGE_VIEW_TYPE_2D;vi.format=format;vi.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};checked(vkCreateImageView(dev,&vi,nullptr,&i.view));images.push_back(i);return i;}
 void barrier(VkCommandBuffer cmd){VkMemoryBarrier b{VK_STRUCTURE_TYPE_MEMORY_BARRIER};b.srcAccessMask=VK_ACCESS_MEMORY_WRITE_BIT;b.dstAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT;vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT|VK_PIPELINE_STAGE_HOST_BIT,0,1,&b,0,nullptr,0,nullptr);}
 void general(VkCommandBuffer cmd,Image i){VkImageMemoryBarrier b{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};b.dstAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT;b.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED;b.newLayout=VK_IMAGE_LAYOUT_GENERAL;b.srcQueueFamilyIndex=b.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;b.image=i.im;b.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,0,0,nullptr,0,nullptr,1,&b);}
 void pass(VkCommandBuffer cmd,VkPipeline p,Image input,Image output,uint32_t w,uint32_t h,bool sharpen){
  VkDescriptorImageInfo info[2]{{sampler,input.view,VK_IMAGE_LAYOUT_GENERAL},{VK_NULL_HANDLE,output.view,VK_IMAGE_LAYOUT_GENERAL}};VkWriteDescriptorSet ws[2]{};
  for(unsigned i=0;i<2;++i){ws[i].sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;ws[i].dstBinding=i;ws[i].descriptorCount=1;ws[i].descriptorType=i?VK_DESCRIPTOR_TYPE_STORAGE_IMAGE:VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;ws[i].pImageInfo=&info[i];}
  vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,p);push(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,2,ws);
  if(sharpen){float stops=0.8f;vkCmdPushConstants(cmd,layout,VK_SHADER_STAGE_COMPUTE_BIT,0,4,&stops);}
  vkCmdDispatch(cmd,(w+7)/8,(h+7)/8,1);barrier(cmd);
 }
 static float half(uint16_t x){const int e=(x>>10)&31,m=x&1023;if(e==31)return NAN;const float v=e?std::ldexp(1.0f+m/1024.0f,e-15):std::ldexp(m/1024.0f,-14);return x&0x8000?-v:v;}
 void run(uint32_t sw,uint32_t sh,uint32_t dw,uint32_t dh,bool constant){
  auto upload=buffer(size_t(sw)*sh*4);auto* pixels=(uint8_t*)upload.map;
  for(uint32_t y=0;y<sh;++y)for(uint32_t x=0;x<sw;++x){size_t a=(size_t(y)*sw+x)*4;pixels[a]=constant?51:((x/5+y/5)&1)?230:20;pixels[a+1]=constant?102:80;pixels[a+2]=constant?153:uint8_t(x*255/std::max(sw-1,1u));pixels[a+3]=255;}
  const VkDeviceSize bytes=VkDeviceSize(dw)*dh*8;auto result=buffer(bytes*2);
  auto input=image(sw,sh,VK_FORMAT_R8G8B8A8_UNORM),mid=image(dw,dh,VK_FORMAT_R16G16B16A16_SFLOAT),out=image(dw,dh,VK_FORMAT_R16G16B16A16_SFLOAT);
  VkCommandBufferAllocateInfo ai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};ai.commandPool=pool;ai.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;ai.commandBufferCount=1;VkCommandBuffer cmd{};checked(vkAllocateCommandBuffers(dev,&ai,&cmd));VkCommandBufferBeginInfo bi{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};bi.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;checked(vkBeginCommandBuffer(cmd,&bi));general(cmd,input);general(cmd,mid);general(cmd,out);
  VkBufferImageCopy c{};c.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1};c.imageExtent={sw,sh,1};vkCmdCopyBufferToImage(cmd,upload.b,input.im,VK_IMAGE_LAYOUT_GENERAL,1,&c);barrier(cmd);
  pass(cmd,easu,input,mid,dw,dh,false);pass(cmd,rcas,mid,out,dw,dh,true);
  c.imageExtent={dw,dh,1};vkCmdCopyImageToBuffer(cmd,mid.im,VK_IMAGE_LAYOUT_GENERAL,result.b,1,&c);c.bufferOffset=bytes;vkCmdCopyImageToBuffer(cmd,out.im,VK_IMAGE_LAYOUT_GENERAL,result.b,1,&c);barrier(cmd);checked(vkEndCommandBuffer(cmd));VkSubmitInfo si{VK_STRUCTURE_TYPE_SUBMIT_INFO};si.commandBufferCount=1;si.pCommandBuffers=&cmd;checked(vkQueueSubmit(queue,1,&si,VK_NULL_HANDLE));checked(vkQueueWaitIdle(queue));
  const auto* values=(const uint16_t*)result.map;const size_t channels=size_t(dw)*dh*4;size_t different=0;
  for(size_t k=0;k<channels;++k){const float a=half(values[k]),b=half(values[channels+k]);if(!std::isfinite(a)||!std::isfinite(b))throw std::runtime_error("nonfinite pixel");if(std::abs(a-b)>1e-4f)++different;
   if((k&3)==3){if(a!=1||b!=1)throw std::runtime_error("invalid alpha");}else if(constant){const float want=float((k&3)+1)*0.2f;if(std::abs(a-want)>0.002f||std::abs(b-want)>0.002f)throw std::runtime_error("constant color changed");}
  }
  if(!constant&&different<100)throw std::runtime_error("RCAS did not sharpen the edge pattern");
  std::printf("PASS %ux%u -> %ux%u: finite pixels, alpha, %s, %zu sharpened channels\n",sw,sh,dw,dh,constant?"constant colors":"edge sharpening",different);
  vkFreeCommandBuffers(dev,pool,1,&cmd);
 }
 ~Fixture(){if(!dev)return;vkDeviceWaitIdle(dev);for(auto i:images){vkDestroyImageView(dev,i.view,nullptr);vkDestroyImage(dev,i.im,nullptr);vkFreeMemory(dev,i.mem,nullptr);}for(auto b:buffers){vkUnmapMemory(dev,b.mem);vkDestroyBuffer(dev,b.b,nullptr);vkFreeMemory(dev,b.mem,nullptr);}vkDestroyPipeline(dev,easu,nullptr);vkDestroyPipeline(dev,rcas,nullptr);vkDestroySampler(dev,sampler,nullptr);vkDestroyPipelineLayout(dev,layout,nullptr);vkDestroyDescriptorSetLayout(dev,set,nullptr);vkDestroyCommandPool(dev,pool,nullptr);vkDestroyDevice(dev,nullptr);vkDestroyInstance(instance,nullptr);}
};
int main(){try{Fixture f;f.run(48,32,113,71,false);f.run(640,360,3840,2160,true);return 0;}catch(const std::exception& e){std::fprintf(stderr,"FAIL: %s\n",e.what());return 1;}}
