"""r13: Hookshot v2.1.0's mesh shader compute fallback (issue 640, commit 8ef84611): the push block and the records' header
compiled alone from Eden's header, the choice of path (the F1 panel's Mesh shaders row), the program cache's records, and the
shader cache's stamp kept through profiles/shader-cache-compatible.json. No game or GPU: none of this says the fallback was seen
on a GPU without mesh shaders."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EMIT_SPIRV_H = "gpu/vk/eden/shader_recompiler/backend/spirv/emit_spirv.h"


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


# (the constants as Eden's header defines them, from NUM_TEXTURE_SCALING_WORDS to the records' size, checked as vk_draw.cpp uses
# them: every other program's push block ends where the fallback's addresses begin)
LAYOUT_FIXTURE = r'''#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
using u32 = std::uint32_t;
using f32 = float;
namespace Shader::Backend::SPIRV {
@CONSTANTS@
}
using namespace Shader::Backend::SPIRV;
constexpr u32 kPushSize = MESH_FIRST_PUSH_OFFSET + 8;   // (vk_draw.cpp)
static_assert(kPushSize == 64);
static_assert(MESH_FALLBACK_PUSH_OFFSET == kPushSize);
static_assert(MESH_FALLBACK_PAYLOAD_PUSH_OFFSET % 8 == 0 && MESH_FALLBACK_RECORDS_PUSH_OFFSET % 8 == 0 &&
              MESH_FALLBACK_INDIRECT_INPUT_PUSH_OFFSET % 8 == 0);   // (u64 device addresses)
static_assert(MESH_FALLBACK_RECORDS_PUSH_OFFSET == MESH_FALLBACK_PAYLOAD_PUSH_OFFSET + 8);
static_assert(MESH_FALLBACK_INDIRECT_INPUT_PUSH_OFFSET == MESH_FALLBACK_RECORDS_PUSH_OFFSET + 8);
static_assert(MESH_FALLBACK_PUSH_END == MESH_FALLBACK_INDIRECT_INPUT_PUSH_OFFSET + 8);
static_assert(MESH_FALLBACK_PUSH_END <= 128);   // (Vulkan's least maxPushConstantsSize)
static_assert(MESH_FALLBACK_DRAW_WORD + 4 <= MESH_FALLBACK_ALLOC_WORD);   // (a VkDrawIndirectCommand)
static_assert(MESH_FALLBACK_ALLOC_WORD < MESH_FALLBACK_DISPATCH_WORD);
static_assert(MESH_FALLBACK_DISPATCH_WORD + 3 <= MESH_FALLBACK_HEADER_WORDS);   // (a VkDispatchIndirectCommand)
static_assert(MESH_FALLBACK_CAPACITY <= 65535);   // (Vulkan's least maxComputeWorkGroupCount)
static_assert((MESH_FALLBACK_HEADER_WORDS + MESH_FALLBACK_RECORD_WORDS) * 4ull == (64ull << 20) + 32);
int main() {
    std::printf("push %u..%u, records %llu bytes\n", MESH_FALLBACK_PUSH_OFFSET, MESH_FALLBACK_PUSH_END,
                (unsigned long long)(MESH_FALLBACK_HEADER_WORDS + MESH_FALLBACK_RECORD_WORDS) * 4ull);
    return 0;
}
'''


class Layout(unittest.TestCase):
    def test_push_block_and_records_compiled_alone(self):
        from tests.native_tools import native_cxx
        cxx = native_cxx()
        if not cxx:
            self.skipTest("no native C++ compiler")
        header = source(EMIT_SPIRV_H)
        constants = header[header.index("constexpr u32 NUM_TEXTURE_SCALING_WORDS"):header.index("[[nodiscard]]")]
        with tempfile.TemporaryDirectory(prefix="r13-mesh-") as tmp:
            src, exe = Path(tmp) / "layout.cpp", Path(tmp) / "layout.exe"
            src.write_text(LAYOUT_FIXTURE.replace("@CONSTANTS@", constants), encoding="utf-8", newline="\n")
            build = subprocess.run([cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-const-variable", str(src),
                                    "-o", str(exe)],
                                   text=True, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(exe)], text=True, capture_output=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_only_the_fallbacks_programs_have_the_longer_block(self):
        draw = source("gpu/vk/vk_draw.cpp")
        self.assertIn("constexpr uint32_t kPushSize = Shader::Backend::SPIRV::MESH_FIRST_PUSH_OFFSET + 8;", draw)
        self.assertIn("constexpr uint32_t kFallbackPushSize = Shader::Backend::SPIRV::MESH_FALLBACK_PUSH_END;", draw)
        self.assertIn("uint32_t push_size(const Program& p) { return p.fallback ? kFallbackPushSize : kPushSize; }", draw)
        self.assertIn("const VkPushConstantRange range{stages, 0, push_size(p)};", draw)
        self.assertIn("vkCmdPushConstants(cmd, p.layout, p.push_stages, 0, push_size(p), data);", draw)
        self.assertIn("static_assert(Shader::Backend::SPIRV::MESH_FALLBACK_DISPATCH_WORD == 5 && "
                      "Shader::Backend::SPIRV::MESH_FALLBACK_HEADER_WORDS == 8);", draw)


class Translation(unittest.TestCase):
    def test_eden_takes_the_fallback_only_when_asked(self):
        runtime = source("gpu/vk/eden/shader_recompiler/runtime_info.h")
        for field in ("bool mesh_fallback{};", "bool mesh_fallback_vertex{};", "bool mesh_fallback_task{};",
                      "u32 mesh_fallback_task_threads{};", "u32 mesh_fallback_capacity{};"):
            self.assertIn(field, runtime)   # (off unless the renderer sets them)
        info = source("gpu/vk/eden/shader_recompiler/shader_info.h")
        self.assertIn("return topology == 0 ? 1U : topology == 1 ? 2U : 3U;", info)   # (points, lines, triangles)
        spirv = "gpu/vk/eden/shader_recompiler/backend/spirv/"
        emit = source(spirv + "emit_spirv.cpp")
        self.assertIn("if (ctx.mesh_fallback && (program.stage == Stage::Task || program.stage == Stage::Mesh)) {", emit)
        self.assertIn("(ctx.wants_mesh_first && !ctx.mesh_fallback)", emit)
        self.assertIn("if (runtime_info.mesh_fallback_vertex) {", emit)
        context = source(spirv + "spirv_emit_context.cpp")
        self.assertIn("if (runtime_info.mesh_fallback || runtime_info.mesh_fallback_vertex) {", context)
        self.assertIn("if (runtime_info.mesh_fallback && (stage == Stage::Task || stage == Stage::Mesh)) {", context)
        self.assertIn("members.push_back(mesh_fallback ? U32[1] : U64);", context)
        self.assertIn("if (wants_mesh_fallback) {", context)

    def test_a_fallback_program_is_drawn_as_a_graphics_one(self):
        internal = source("gpu/vk/vk_internal.h")
        self.assertIn("bool uses_mesh_fallback(bool has_task) const { return mesh_fallback || (task_mesh_fallback && has_task); }",
                      internal)
        shader = source("gpu/vk/vk_shader.cpp")
        locked = shader[shader.index("const Program* mesh_program_locked("):]
        locked = locked[:locked.index("struct Job {")]
        self.assertIn("if (!dev.mesh_shader && !dev.mesh_fallback) return nullptr;", locked)
        self.assertIn("const bool fallback = dev.uses_mesh_fallback(task != nullptr);", locked)
        # (a variant made for the other path is never handed out: a native program has mesh set, a fallback one fallback)
        self.assertIn("if (p->fallback != fallback || p->mesh == fallback) continue;", locked)
        self.assertLess(locked.index("p->mesh == fallback) continue;"), locked.index("if (!p->ready.load("))
        self.assertIn("    p->mesh = !fallback;", locked)
        self.assertIn("    p->fallback = fallback;\n", locked)
        self.assertIn("    p->fallback = mesh && dev.uses_mesh_fallback(by_stage[6] != nullptr);\n"
                      "    p->mesh = mesh && !p->fallback;\n", shader)   # (the seed's precompile)
        self.assertIn("st.vk_stage = fallback ? VK_SHADER_STAGE_COMPUTE_BIT : VK_SHADER_STAGE_TASK_BIT_EXT;", shader)
        self.assertIn("ms.vk_stage = fallback ? VK_SHADER_STAGE_COMPUTE_BIT : VK_SHADER_STAGE_MESH_BIT_EXT;", shader)

    def test_program_cache_records(self):
        shader = source("gpu/vk/vk_shader.cpp")
        # (r13c: one encoding for the writer, the file's index and the reader; the fallback's records are 4 and 12. The index
        # took 0 to 3 only, and every start in Compute translated them again)
        # (r13i: and 16, task and mesh stages with the global-load helper inlined: test_r13i_p0.py)
        self.assertIn("return (p.compute ? 1u : 0u) | (p.mesh ? 2u : 0u) | (p.fallback ? 4u : 0u) | (p.fallback_task ? 8u : 0u) |",
                      shader)
        self.assertIn("constexpr uint32_t kRecordKinds = 63u;", shader)
        self.assertEqual(shader.count("put(o, record_kind(p));"), 1)
        self.assertIn("disk_records[p.key].push_back({at + 16, o.size(), record_kind(p)});", shader)
        self.assertIn("if (rec[1]<=cache::Policy::max_record && !(kind&~kRecordKinds)) {", shader)
        self.assertIn("if (kind&~kRecordKinds) throw", shader)
        self.assertNotRegex(shader, r"kind\s*&\s*~\s*(3|15)u")
        for kind in (4, 12):
            self.assertEqual(kind & ~15, 0)
        save = shader[shader.index("    if (p.fallback) {   // (AkynoLeyend r13"):]
        save = save[:save.index("    }\n")]
        saved = re.findall(r"put\(o, (?:\(uint32_t\))?p\.(fallback_\w+)\);", save)
        self.assertEqual(saved, ["fallback_topology", "fallback_vertices_per_workgroup", "fallback_record_words",
                                 "fallback_payload_words", "fallback_task_threads"])
        load = shader[shader.index("if (kind&~kRecordKinds) throw"):]
        load = load[:load.index("p->fallback_task_threads = r.get<uint32_t>();") + 60]
        self.assertEqual(re.findall(r"p->(fallback_\w+) = (?:\(VkPrimitiveTopology\))?r\.get<uint32_t>\(\);", load), saved)
        self.assertIn("if (p->fallback && !dev.uses_mesh_fallback(p->fallback_task)) throw", load)
        # (a GPU on the fallback path has a file of its own; a GPU with mesh shaders and no fallback keeps its file's stamp)
        stamp = shader[shader.index("uint64_t disk_stamp() {"):]
        stamp = stamp[:stamp.index("for (char** e = _environ;")]
        self.assertIn("if (dev.mesh_fallback || dev.task_mesh_fallback) {", stamp)

    def test_each_mesh_path_has_its_own_files(self):
        # (r13c: native and Compute stamp their programs apart, and shared one file: each switch of the row started it again,
        # the native cache lost. The native path keeps its names, so its files stay)
        shader, draw = source("gpu/vk/vk_shader.cpp"), source("gpu/vk/vk_draw.cpp")
        made = shader[shader.index("std::string program_cache_file(const char* name) {"):shader.index("void disk_init() {")]
        self.assertIn('const char* tag = dev.mesh_fallback ? "_compute" : dev.task_mesh_fallback ? "_mixed" : "";', made)
        self.assertIn("file.insert(dot == std::string::npos ? file.size() : dot, tag + device_file_tag());", made)
        self.assertIn('const std::string path = program_cache_file("AkynoLeyend_programs.bin");', shader)
        self.assertIn('return program_cache_file("AkynoLeyend_pipeline_keys.bin");', draw)
        self.assertIn('const std::string path = program_cache_file("AkynoLeyend_prepared.bin");', draw)
        for name in ("AkynoLeyend_programs.bin", "AkynoLeyend_pipeline_keys.bin", "AkynoLeyend_prepared.bin"):
            self.assertEqual((shader + draw).count('"%s"' % name), 1)   # (no other place opens them by name)
        # (the driver's pipeline cache holds either mesh path's pipelines: one file a device, r13d)
        self.assertIn('pcache_path = dir + "AkynoLeyend_pipelines" + tag + ".bin";', draw)

    def test_stamp_kept_through_the_registry(self):
        # (the fallback changed Eden and vk_shader.cpp; the native path's SPIR-V was compared module by module and the old
        # stamp registered for these sources: a GPU with mesh shaders keeps its translated programs)
        from akynoleyend.build_support import shader_cache_stamp, shader_source_identity
        computed, fingerprint = shader_source_identity(ROOT / "gpu/vk")
        registry = json.loads(source("profiles/shader-cache-compatible.json"))
        entry = registry["source_sets"][fingerprint]
        self.assertEqual(entry["stamp"], "4cdbb0029868040b")
        self.assertNotEqual(computed, entry["stamp"])
        self.assertEqual(shader_cache_stamp(ROOT / "gpu/vk"), "4cdbb0029868040b")
        self.assertIn("0 SPIR-V modules different", entry["reason"])


class Choice(unittest.TestCase):
    def test_the_row_read_as_the_device_is_made(self):
        main = source("gpu/vk/vk_main.cpp")
        self.assertIn('int v = boot_option("mesh_shaders", 0);', main)
        self.assertIn('if (const char* e = getenv("RX_VK_FORCE_MESH_FALLBACK")) v = atoi(e) != 0 ? 2 : v;', main)
        self.assertIn("if (mesh_mode == 2) dev.mesh_shader = false;\n"
                      "    else optional(VK_EXT_MESH_SHADER_EXTENSION_NAME, dev.mesh_shader);", main)
        self.assertLess(main.index("else optional(VK_EXT_MESH_SHADER_EXTENSION_NAME"), main.index("vkCreateDevice("))
        self.assertIn('dev.mesh_fallback = !dev.mesh_shader && f12.bufferDeviceAddress && !getenv("RX_VK_NO_MESH_FALLBACK");',
                      main)
        # (Navi 22 on Windows: task + mesh draws on the compute path at Automatic, Hookshot issue 996; Native turns it off)
        self.assertIn("task_mesh_fallback = dev.props.vendorID == 0x1002 && dev.props.deviceID == 0x73df;", main)
        self.assertIn("if (mesh_mode == 1) task_mesh_fallback = false;", main)
        self.assertIn("dev.task_mesh_fallback = task_mesh_fallback && dev.mesh_shader && f12.bufferDeviceAddress", main)

    def test_the_panels_row(self):
        menu, header = source("gpu/vk/vk_menu.cpp"), source("gpu/vk/vk_menu.h")
        self.assertIn("int mesh_mode = 0;", header)   # (Automatic: the card's own mesh shaders where it has them)
        self.assertIn('{"Mesh shaders", "Mesh shaders", &opts.mesh_mode, 0, 2, 1, tx_mesh_mode,', menu)
        self.assertIn('static const char* t[] = {"Automático", "Nativos", "Compute"};', menu)
        names = re.findall(r'^    \{"([A-Za-z ]+)", "[^"]+", &opts\.', menu, re.M)
        self.assertIn("mesh_shaders", {name.lower().replace(" ", "_") for name in names})   # (ini_key, what vk_main.cpp reads)
        enum = re.search(r"enum Setting \{([^}]+)\}", menu).group(1)
        # (0.4.5-test.1: the two Dinâmica rows come after it, appended as every row is)
        self.assertEqual([name.strip() for name in enum.split(",")][-5:], ["MeshMode", "FgMax", "FgTarget", "RenderDistance", "SettingCount"])
        for page in ("video_rows", "restart_rows"):
            listed = re.search(r"constexpr Setting %s\[\] = \{([^}]+)\}" % page, menu).group(1)
            self.assertIn("MeshMode", [name.strip() for name in listed.split(",")])


if __name__ == "__main__":
    unittest.main()
