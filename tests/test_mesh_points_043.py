"""Execute production point-mesh setup and attribute emission against synthetic state."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def function(source, marker):
    start = source.index(marker)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class PointMeshTests(unittest.TestCase):
    def execute(self, source):
        compiler = shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "points.cpp").write_text(source)
            binary = path / "points"
            result = subprocess.run([compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                                     "-I" + str(ROOT / "gpu/vk/compat"), "-I" + str(ROOT / "gpu/vk/eden"),
                                     "-I" + str(ROOT / "gpu/compat"),
                                     str(path / "points.cpp"), "-o", str(binary)],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_points_do_not_become_lines_and_mesh_bounds_stay_intact(self):
        body = function((ROOT / "gpu/vk/vk_shader.cpp").read_text(), "std::array<u32, 3> mesh_registers_of(")
        self.execute(r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
using u32=uint32_t;
struct Code {u32 topology{},payload_bytes{},max_vertices{},max_primitives{},mesh_threads{};};
''' + body + r'''
int main(){
    Code task{0,129,0,0,99}, mesh{1,0,64,126,99};
    for (u32 topology=0;topology<5;++topology) {
        mesh.topology=topology;const auto r=mesh_registers_of(&task,mesh);
        assert((r[0]&15)==(topology==1?0:topology==3?4:topology));
        assert(((r[0]>>4)&0x1ff)==126 && ((r[0]>>13)&0x1ff)==126);
        assert(r[1]==(63u<<20));assert((r[2]&63)==63);
        assert(((r[2]>>12)&0x1ff)==2 && ((r[2]>>22)&0x1ff)==2);
    }
    mesh.max_vertices=999;mesh.topology=1;
    auto r=mesh_registers_of(nullptr,mesh);assert((r[0]&15)==0);
    assert(((r[0]>>4)&0x1ff)==256 && ((r[0]>>13)&0x1ff)==256 && r[2]==0);
}
''')

    def test_point_mask_uses_sprite_coordinates_and_preserves_written_generics(self):
        source = (ROOT / "gpu/vk/vk_shader.cpp").read_text()
        start = source.index("            if (mesh_t->program.mesh.topology == 0)")
        selection = source[start:source.index("            for (int i = 0; i < 8;", start)]
        backend = (ROOT / "gpu/vk/eden/shader_recompiler/backend/spirv/emit_spirv_context_get_set.cpp").read_text()
        emit = function(backend, "Id EmitGetAttribute(")
        fixture = r'''
#include <array>
#include <bit>
#include <cassert>
#include <limits>
#include <stdexcept>
#include "shader_recompiler/runtime_info.h"
namespace IR=Shader::IR;
enum class Stage {Fragment,VertexB};
using Id=u32;
enum class InputGenericLoadOp {Bitcast,SToF,UToF,None};
struct Generic {Id id{},pointer_type{},component_type{};InputGenericLoadOp load_op{};};
struct EmitContext {
    Stage stage=Stage::Fragment;Shader::RuntimeInfo runtime_info;
    std::array<Id,4> F32{},U32{};Id U1{},input_f32{},point_coord{};
    std::array<Generic,32> input_generics{};bool need_input_position_indirect=false;
    Id primitive_id{},layer{},input_position{},instance_id{},instance_index{},base_instance{},vertex_id{},vertex_index{};
    Id base_vertex{},draw_index{},front_face{},tess_coord{},u32_zero_value{},f32_zero_value{};
    struct {bool support_vertex_instance_id=false;} profile;
    Id Const(u32 v){return v;}Id Const(float v){return std::bit_cast<u32>(v);}
    Id OpAccessChain(Id,Id,Id index){return index+1000;}
    Id OpLoad(Id,Id pointer){assert(pointer==1000||pointer==1001);return Const(pointer==1000?0.25f:0.75f);}
    Id OpBitcast(Id,Id v){return v;}Id OpConvertSToF(Id,Id v){return v;}Id OpConvertUToF(Id,Id v){return v;}
    Id OpISub(Id,Id a,Id b){return a-b;}Id OpSelect(Id,Id c,Id a,Id b){return c?a:b;}
};
bool ValidId(Id v){return v!=0;}
template<class... A> Id AttrPointer(EmitContext&,A...){return 0;}
struct NotImplementedException:std::runtime_error {
    template<class... A> NotImplementedException(const char* message,A...):std::runtime_error(message){}
};
struct Holder {struct {struct {int topology{};} mesh;struct {Shader::VaryingState loads,stores;} info;} program;};
Shader::RuntimeInfo setup(Holder* mesh_t,Holder* fs){Shader::RuntimeInfo frt;
'''
        fixture += selection + 'return frt;}\n' + emit
        fixture += r'''
int main(){
    Holder mesh,fragment;fragment.program.info.loads.Set(IR::Attribute::Generic5X);
    fragment.program.info.loads.Set(IR::Attribute::Generic6X);mesh.program.info.stores.Set(IR::Attribute::Generic6X);
    EmitContext ctx;ctx.runtime_info=setup(&mesh,&fragment);
    assert(ctx.runtime_info.point_coord_generics.count()==1 && ctx.runtime_info.point_coord_generics[5]);
    const float expected[]{0.25f,0.75f,0,1};
    for(u32 component=0;component<4;++component){
        auto a=static_cast<IR::Attribute>(static_cast<u32>(IR::Attribute::Generic5X)+component);
        assert(EmitGetAttribute(ctx,a,0)==ctx.Const(expected[component]));
        auto untouched=static_cast<IR::Attribute>(static_cast<u32>(IR::Attribute::Generic6X)+component);
        assert(EmitGetAttribute(ctx,untouched,0)==ctx.Const(component==3?1.0f:0.0f));
    }
    ctx.stage=Stage::VertexB;assert(EmitGetAttribute(ctx,IR::Attribute::Generic5X,0)==ctx.Const(0.0f));
    mesh.program.mesh.topology=4;assert(setup(&mesh,&fragment).point_coord_generics.none());
    mesh.program.mesh.topology=0;mesh.program.info.stores.Set(IR::Attribute::Generic5Y);
    assert(setup(&mesh,&fragment).point_coord_generics.none());
}
'''
        self.execute(fixture)


if __name__ == "__main__":
    unittest.main()
