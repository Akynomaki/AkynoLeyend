"""r13f: mesh programs that draw points (NVN2 topology 1, handed to Eden as 0 by vk_shader.cpp's mesh_registers_of). The issue 302
backport (test_mesh_points_043.py) brought the topology and the point sprite coordinates, but Eden still refused topology 0: the
game's four point mesh programs were never drawn ("Mesh output topology 0 (SET_MESH_SHADER_A 0x00040200) is not implemented",
their two draws left out every frame on the RTX 3060 Ti, 12/11/2026). Sources and the shader stamp's registry; no game or GPU:
none of this says what those draws show on screen."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EDEN = "gpu/vk/eden/shader_recompiler/"


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Translator(unittest.TestCase):
    def test_topology_0_is_taken(self):
        translate = source(EDEN + "frontend/maxwell/translate_program.cpp")
        check = translate[translate.index("if (program.stage == Stage::Mesh) {"):]
        check = check[:check.index("throw NotImplementedException")]
        self.assertIn("program.mesh.topology != 0", check)
        self.assertIn("program.mesh.topology != 1", check)
        self.assertIn("program.mesh.topology != 4", check)

    def test_corners_as_the_expressions_they_replace(self):
        # (2 for lines and 3 for triangles, as before: every program of topology 1 or 4 translates as it did, which is
        # what keeps the shader stamp)
        info = source(EDEN + "shader_info.h")
        self.assertIn("return topology == 0 ? 1U : topology == 1 ? 2U : 3U;", info)
        corners = lambda topology: 1 if topology == 0 else 2 if topology == 1 else 3
        old = lambda topology: 2 if topology == 1 else 3
        for topology in (1, 4):
            self.assertEqual(corners(topology), old(topology))
        self.assertEqual(corners(0), 1)

    def test_every_choice_of_output_follows_corners(self):
        emit = source(EDEN + "backend/spirv/emit_spirv.cpp")
        context = source(EDEN + "backend/spirv/spirv_emit_context.cpp")
        mesh = source(EDEN + "backend/spirv/emit_spirv_mesh.cpp")
        self.assertIn("program.mesh.Corners() == 1   ? spv::ExecutionMode::OutputPoints", emit)
        self.assertIn("mesh_map_bytes = 4 + mesh_info.Corners() * mesh_info.max_primitives;", context)
        self.assertIn("corners == 1   ? spv::BuiltIn::PrimitivePointIndicesEXT", context)
        self.assertIn("const u32 corners{mesh.Corners()};", mesh)
        self.assertIn("corners == 1 ? indices[0]", mesh)   # (a point's index is a scalar)
        # (no choice between lines and triangles alone is left in the back end or the front end's check)
        for name in ("backend/spirv/emit_spirv.cpp", "backend/spirv/spirv_emit_context.cpp",
                     "backend/spirv/emit_spirv_mesh.cpp"):
            self.assertNotRegex(source(EDEN + name), r"topology == 1 \?")
            self.assertNotIn("mesh_lines", source(EDEN + name))

    def test_a_point_program_without_a_size_writes_one(self):
        context = source(EDEN + "backend/spirv/spirv_emit_context.cpp")
        mesh = source(EDEN + "backend/spirv/emit_spirv_mesh.cpp")
        header = source(EDEN + "backend/spirv/spirv_emit_context.h")
        self.assertIn("Id mesh_point_size_default{};", header)
        self.assertIn("if (corners == 1 && !Sirit::ValidId(point_size)) {", context)
        self.assertIn("spv::BuiltIn::PointSize", context[context.index("if (corners == 1 && !Sirit::ValidId(point_size))"):])
        copy = mesh[mesh.index("const auto copy = [&] {"):]
        copy = copy[:copy.index("\n        };")]   # (the lambda's own end, not a brace initializer's inside it)
        self.assertIn("ctx.mesh_point_size_default, vertex), ctx.Const(1.0f)", copy)
        # (inside the vertex copy, which the vertices past the program's count do not reach)
        self.assertLess(copy.index("CopyLines(ctx, vertex, 0, vertex_lines"), copy.index("mesh_point_size_default"))

    def test_the_fragment_side_was_already_there(self):
        # (issue 302's half that came in 0.4.3: the unwritten generics read the point sprite's coordinates)
        shader = source("gpu/vk/vk_shader.cpp")
        self.assertIn("if (mesh_t->program.mesh.topology == 0)", shader)
        self.assertIn("frt.point_coord_generics.set(i);", shader)
        get_set = source(EDEN + "backend/spirv/emit_spirv_context_get_set.cpp")
        self.assertIn("ctx.runtime_info.point_coord_generics.test(index)", get_set)


class Stamp(unittest.TestCase):
    def test_kept_through_the_registry_with_its_reason(self):
        from akynoleyend.build_support import shader_cache_stamp, shader_source_identity
        computed, fingerprint = shader_source_identity(ROOT / "gpu/vk")
        registry = json.loads(source("profiles/shader-cache-compatible.json"))["source_sets"]
        entry = registry[fingerprint]
        self.assertEqual(entry["stamp"], "4cdbb0029868040b")
        self.assertNotEqual(computed, "4cdbb0029868040b")
        self.assertEqual(shader_cache_stamp(ROOT / "gpu/vk"), "4cdbb0029868040b")
        self.assertIn("Kept by construction, not measured module by module", entry["reason"])
        # The unguarded legacy emitter must never be reintroduced.
        self.assertNotIn("a40b759f1661d188214db90ef0a61e5bda802b04c49e78406674a8a49df00189", registry)

    def test_a_failed_translation_is_not_kept(self):
        # (so the programs refused before are translated again at the next start, the stamp kept)
        shader = source("gpu/vk/vk_shader.cpp")
        body = shader[shader.index("void translate_mesh_into("):]
        body = body[:body.index("\n}\n")]
        self.assertLess(body.index("program_cache_save(p, kept);"), body.index("} catch (const std::exception& e) {"))
        self.assertIsNone(re.search(r"catch \(const std::exception& e\) \{[^}]*program_cache_save", body))


if __name__ == "__main__":
    unittest.main()
