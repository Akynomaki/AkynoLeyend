"""r13e: a storage buffer's end in the shaders' search by address taken from the address as given when the card's storage buffer
alignment is over 16 (64 on the Intel integrated GPU of a Core Ultra 9 275HX): rounded down, its last bytes went to the guest page
table. Read from the sources: the flag, set by alignment; the emitter unchanged without it; the program cache's stamp. No GPU here:
these tests do not say the game was seen on an Intel GPU."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPV = "gpu/vk/eden/shader_recompiler/backend/spirv/"


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class SsboEnd(unittest.TestCase):
    def test_flag_starts_off(self):
        self.assertIn("inline bool ssbo_end_unaligned = false;", source(SPV + "mma_layout.h"))

    def test_set_by_the_cards_alignment(self):
        coop = source("gpu/vk/vk_coopmat.cpp")
        body = coop[coop.index("void coopmat_init() {"):]
        self.assertIn('ssbo_end_unaligned = dev.props.limits.minStorageBufferOffsetAlignment > 16 && '
                      '!std::getenv("RX_VK_SSBO_END_ALIGNED");', body)
        self.assertLess(body.index("ssbo_end_unaligned ="), body.index("return;"))

    def test_emitter_unchanged_without_the_flag(self):
        ctx = source(SPV + "spirv_emit_context.cpp")
        self.assertIn("Id ssbo_end{OpIAdd(U64, ssbo_end_unaligned ? unaligned_addr : ssbo_addr, ssbo_size)};", ctx)
        self.assertNotIn("Id ssbo_end{OpIAdd(U64, ssbo_addr, ssbo_size)};", ctx)
        # (the table entries already end at the address as given)
        self.assertIn("Id ssbo_end{OpIAdd(U64, unaligned_addr, OpUConvert(U64, size_word))};", ctx)

    def test_binding_holds_the_rounded_bytes(self):
        draw = source("gpu/vk/vk_draw.cpp")
        self.assertIn("const uint64_t base = addr & ~(salign - 1);", draw)
        self.assertIn("uint64_t n = std::max<uint64_t>(((size + (addr - base)) + 3) & ~3ull, 16);", draw)

    def test_program_cache_stamp(self):
        self.assertIn("(ssbo_end_unaligned ? 16u : 0u)", source("gpu/vk/vk_shader.cpp"))


if __name__ == "__main__":
    unittest.main()
