// Exercise the production IR, optimization and SPIR-V backend with synthetic atomics.
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <stdexcept>
#include <vector>
#include <spirv/unified1/spirv.hpp>
#include "shader_recompiler/backend/spirv/emit_spirv.h"
#include "shader_recompiler/environment.h"
#include "shader_recompiler/frontend/ir/ir_emitter.h"
#include "shader_recompiler/host_translate_info.h"
#include "shader_recompiler/ir_opt/passes.h"
#include "shader_recompiler/object_pool.h"
using namespace Shader;

struct EnvironmentFixture final : Environment {
    EnvironmentFixture() { stage = Stage::Compute; }
    u64 ReadInstruction(u32) override { return 0; }
    u32 ReadCbufValue(u32, u32) override { return 0; }
    TextureType ReadTextureType(u32) override { return TextureType::Color2D; }
    TexturePixelFormat ReadTexturePixelFormat(u32) override { return TexturePixelFormat::R8_UNORM; }
    bool IsTexturePixelFormatInteger(u32) override { return false; }
    u32 ReadViewportTransformState() override { return 0; }
    u32 TextureBoundBuffer() const override { return 0; }
    u32 LocalMemorySize() const override { return 0; }
    u32 SharedMemorySize() const override { return 0; }
    std::array<u32,3> WorkgroupSize() const override { return {1,1,1}; }
    bool HasHLEMacroState() const override { return false; }
    std::optional<ReplaceConstant> GetReplaceConstBuffer(u32,u32) override { return std::nullopt; }
    void Dump(u64,u64) override {}
};

void require(bool ok,const char* message) { if (!ok) throw std::runtime_error(message); }
void run(bool global,const std::filesystem::path& directory,bool tracked=false) {
    ObjectPool<IR::Inst> pool;
    IR::Block block{pool}; IR::Program program;
    program.stage=Stage::Compute;program.workgroup_size={1,1,1};
    program.blocks.push_back(&block);program.post_order_blocks.push_back(&block);
    IR::AbstractSyntaxNode body{};body.type=IR::AbstractSyntaxNode::Type::Block;body.data.block=&block;
    program.syntax_list.push_back(body);
    IR::AbstractSyntaxNode ret{};ret.type=IR::AbstractSyntaxNode::Type::Return;program.syntax_list.push_back(ret);
    IR::IREmitter ir{block};
    if(tracked) {
        const auto low=ir.GetCbuf(ir.Imm32(0u),ir.Imm32(0x100u));
        const auto high=ir.GetCbuf(ir.Imm32(0u),ir.Imm32(0x104u));
        const auto address=ir.PackUint2x32(ir.CompositeConstruct(low,high));
        (void)ir.GlobalAtomicCompareExchange(address,ir.Imm32(7u),ir.Imm32(11u));
        HostTranslateInfo host{};host.min_ssbo_alignment=16;
        Optimization::GlobalMemoryToStorageBufferPass(program,host);
        bool found=false;
        for(auto& inst:block.Instructions()) if(inst.GetOpcode()==IR::Opcode::StorageAtomicCompareExchange32) {
            found=true;require(inst.NumArgs()==4,"tracked CAS lost its replacement value");
            require(inst.Arg(2).U32()==7&&inst.Arg(3).U32()==11,"tracked CAS operand order changed");
        }
        require(found,"synthetic CAS was not tracked to storage");
    }
    else if(global) (void)ir.GlobalAtomicCompareExchange(ir.Imm64(u64{0x1000}),ir.Imm32(7u),ir.Imm32(11u));
    else block.AppendNewInst(IR::Opcode::StorageAtomicCompareExchange32,{ir.Imm32(0u),ir.Imm32(0u),ir.Imm32(7u),ir.Imm32(11u)});
    IR::IREmitter tail{block};tail.Epilogue();
    Optimization::DeadCodeEliminationPass(program);
    EnvironmentFixture environment;Optimization::CollectShaderInfoPass(environment,program);
    if(program.info.constant_buffer_descriptors.empty())program.info.constant_buffer_descriptors.push_back({0,1});
    if(program.info.storage_buffers_descriptors.empty())program.info.storage_buffers_descriptors.push_back({0,0x10,1,true});
    program.info.used_constant_buffer_types|=IR::Type::U32|IR::Type::U32x2;
    Profile profile{};profile.supported_spirv=0x00010600;profile.support_int64=true;
    profile.support_descriptor_aliasing=true;profile.min_ssbo_alignment=16;
    profile.unified_descriptor_binding=true;
    const auto words=Backend::SPIRV::EmitSPIRV(profile,program);
    std::map<u32,u32> constants;std::map<u32,std::vector<u32>> parameters;
    u32 function=0,label=0;unsigned atomics=0;
    std::set<u32> atomic_blocks,atomic_results,returned_results;
    for(size_t at=5;at<words.size();) {
        const u32 n=words[at]>>16;require(n>0&&at+n<=words.size(),"invalid SPIR-V instruction span");
        const auto op=static_cast<spv::Op>(words[at]&65535);
        if(op==spv::Op::OpConstant&&n==4)constants[words[at+2]]=words[at+3];
        if(op==spv::Op::OpFunction)function=words[at+2];
        if(op==spv::Op::OpLabel)label=words[at+1];
        if(op==spv::Op::OpFunctionParameter)parameters[function].push_back(words[at+2]);
        if(op==spv::Op::OpAtomicCompareExchange) {
            require(n==9,"wrong compare-exchange operand count");++atomics;
            require(atomic_blocks.insert(label).second,"atomic duplicated within one execution block");
            atomic_results.insert(words[at+2]);
            if(global) {const auto& p=parameters[function];require(p.size()==3&&words[at+7]==p[2]&&words[at+8]==p[1],"global CAS comparator/value swapped");}
            else require(constants[words[at+7]]==11&&constants[words[at+8]]==7,"storage CAS comparator/value swapped");
        }
        if(op==spv::Op::OpReturnValue&&atomic_results.contains(words[at+1]))returned_results.insert(words[at+1]);
        at+=n;
    }
    const unsigned expected_atomics=global&&std::getenv("RX_VK_FOLLOW_STORES")?2:1;
    require(atomics==expected_atomics,"wrong atomic count across storage/page-table branches");
    require(!global||returned_results==atomic_results,"global CAS branch no longer returns the previous word");
    std::filesystem::create_directories(directory);
    const auto path=directory/(tracked?"tracked-cas.spv":global?"global-cas.spv":"storage-cas.spv");
    std::ofstream output(path,std::ios::binary);output.write(reinterpret_cast<const char*>(words.data()),words.size()*4);
    require(bool(output),"module write failed");
    std::printf("PASS %s CAS: side effect kept, comparator/value order correct%s\n",tracked?"tracked":global?"global":"storage",global?", previous word returned":"");
}
int main(int argc,char**argv) {
    try {require(argc==2,"usage: fixture output-directory");run(false,argv[1],true);run(false,argv[1]);run(true,argv[1]);return 0;}
    catch(const std::exception& e){std::fprintf(stderr,"FAIL: %s\n",e.what());return 1;}
}
