"""r13d: three of Hookshot v2.1.0's translation fixes, for every card but NVIDIA (found on the Intel integrated GPU of a Core
Ultra 9 275HX): the compare-exchange loop's ceiling, invariant positions and the colour NaN guard. Read from the sources: each fix
behind its flag, the flags set by vendor, the program cache's stamp changed only when one is on, and the shader stamp kept. No
GPU here: these tests do not say the game was seen on an Intel GPU."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPV = "gpu/vk/eden/shader_recompiler/backend/spirv/"


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Flags(unittest.TestCase):
    def test_flags_start_off(self):
        layout = source(SPV + "mma_layout.h")
        for flag in ("frag_nan_guard", "position_invariant", "cas_loop_cap"):
            self.assertIn("inline bool %s = false;" % flag, layout)

    def test_set_only_for_cards_other_than_nvidia(self):
        coop = source("gpu/vk/vk_coopmat.cpp")
        body = coop[coop.index("void coopmat_init() {"):]
        self.assertIn("const bool other = dev.props.vendorID != 0x10DE;", body)
        for flag, env in (("cas_loop_cap", "RX_VK_NO_CAS_CAP"), ("position_invariant", "RX_VK_NO_INVARIANT"),
                          ("frag_nan_guard", "RX_VK_NO_NAN_GUARD")):
            self.assertIn('%s = other && !std::getenv("%s");' % (flag, env), body)
        # (before the early returns of the matrix probe: every card gets its flags)
        self.assertLess(body.index("cas_loop_cap = other"), body.index("return;"))


class Emitters(unittest.TestCase):
    def test_cas_loop_unchanged_without_the_flag(self):
        ctx = source(SPV + "spirv_emit_context.cpp")
        self.assertIn("    if (!cas_loop_cap) return Id{};\n", ctx)
        self.assertIn("    if (!cas_loop_cap) return success;\n", ctx)
        self.assertEqual(ctx.count("CasTriesVariable("), 4)   # (the definition and the three loops)
        self.assertEqual(ctx.count("CasLoopDone("), 4)
        self.assertNotIn("OpBranchConditional(success, merge_block, loop_header)", ctx)
        self.assertNotIn("OpBranchConditional(store_successful,", ctx)

    def test_invariant_positions_behind_the_flag(self):
        ctx = source(SPV + "spirv_emit_context.cpp")
        self.assertEqual(ctx.count("if (position_invariant) Decorate(output_position, spv::Decoration::Invariant);"), 2)

    def test_nan_guard_behind_the_flag(self):
        getset = source(SPV + "emit_spirv_context_get_set.cpp")
        self.assertIn("if (frag_nan_guard) {", getset)
        self.assertIn('#include "shader_recompiler/backend/spirv/mma_layout.h"', getset)


class UniformSnapshot(unittest.TestCase):
    def test_on_by_default_only_for_intel_without_a_mirror(self):
        draw = source("gpu/vk/vk_draw.cpp")
        self.assertIn('const bool on = e ? atoi(e) != 0 : dev.props.vendorID == 0x8086 && !pools_mirrored();', draw)
        self.assertNotIn('static const bool snapshot = getenv("RX_VK_UB_SNAPSHOT") != nullptr;', draw)
        self.assertIn("bool pools_mirrored();", source("gpu/vk/vk_internal.h"))
        memory = source("gpu/vk/vk_memory.cpp")
        self.assertIn("bool pools_mirrored() {", memory)
        # (outside the file's anonymous namespaces, where vk_draw.cpp can link it)
        self.assertGreater(memory.index("bool pools_mirrored() {"), memory.rindex("} // namespace\n"))


class Stamps(unittest.TestCase):
    def test_program_cache_stamp_only_when_a_fix_is_on(self):
        shader = source("gpu/vk/vk_shader.cpp")
        self.assertIn("if (fixes) add(&fixes, sizeof fixes);", shader)

    def test_shader_stamp_kept(self):
        from akynoleyend.build_support import shader_cache_stamp, shader_source_identity
        computed, fingerprint = shader_source_identity(ROOT / "gpu/vk")
        sets = json.loads(source("profiles/shader-cache-compatible.json"))["source_sets"]
        self.assertEqual(sets[fingerprint]["stamp"], "4cdbb0029868040b")
        # (r13e's set replaced r13d's, whose reason it carries)
        self.assertIn("r13d over source set b81c50bf (r13c)", sets[fingerprint]["reason"])
        self.assertEqual(shader_cache_stamp(ROOT / "gpu/vk"), "4cdbb0029868040b")


if __name__ == "__main__":
    unittest.main()
