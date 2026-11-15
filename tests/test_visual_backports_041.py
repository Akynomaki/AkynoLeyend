"""Source-integrity regressions for selected Hookshot 2.0.5 Vulkan visual backports.

These don't replace a Windows compilation and GPU comparisons; each test checks a narrow
source-level contract or the ARM64 version guard used to inject optional occlusion logic.
"""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]


def code(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


class VisualBackportTests(unittest.TestCase):
    def test_early_texel_writes_are_copied_and_replayed(self):
        src = code('host/rx_backend.c')
        for text in ('case 5:', 'c.data = (uint8_t *)malloc', 'memcpy(c.data, src,',
                     'if (keep_early(&c)) return;', 'free(early[i].data);',
                     'vk->nvn_write_texels(&c->t, c->level, c->layer0'):
            self.assertIn(text, src)
        self.assertIn('const uint64_t max_bytes = 64ull << 20;', src)

    def test_lifted_occlusion_patch_only_when_opcode_matches(self):
        src = code('nx2/lift.py')
        self.assertIn('if a.standalone:\n        # Known game build only:', src)
        self.assertIn('oot_occlusion.install(L, img)', src)
        p = ROOT / 'nx2' / 'oot_occlusion.py'
        spec = importlib.util.spec_from_file_location('akyno_oot_occlusion', p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)

        class Img:
            def __init__(self, mismatch=False): self.mismatch=mismatch
            def word(self, pc):
                return 0 if self.mismatch and pc == m.MAIN + m.OFFSETS[0] else m.LDRB_W8_X0
        class Lifter:
            def __init__(self): self.after = {}
        lift=Lifter()
        self.assertEqual(m.install(lift, Img()), 6)
        self.assertEqual(len(lift.after), 6)
        lift=Lifter()
        self.assertEqual(m.install(lift, Img(True)), 5)
        self.assertEqual(len(lift.after), 5)

    def test_mesh_grid_is_copied_on_gpu_before_indirect_dispatch(self):
        src = code('gpu/vk/vk_draw.cpp')
        self.assertIn('grid_patch_want = indirect && !no_grid_patch', src)
        self.assertIn('vkCmdCopyBuffer(cmd, args.buffer, grid_patch_buf', src)
        self.assertIn('VK_ACCESS_2_UNIFORM_READ_BIT', src)
        self.assertLess(src.index('vkCmdCopyBuffer(cmd, args.buffer, grid_patch_buf'),
                        src.index('vkCmdDispatchIndirect(cmd, args.buffer, args.offset);'))

    def test_no_false_writes_for_bare_read_ranges(self):
        src = code('gpu/vk/vk_draw.cpp')
        self.assertIn('d.is_written ? (1ull << 20) : bare_read', src)
        self.assertIn('d.is_written && !bare', src)
        self.assertIn('dev.props.limits.maxStorageBufferRange', src)

    def test_gpu_created_ground_maps_kept_with_bounded_lru(self):
        src=code('gpu/vk/vk_texture.cpp')
        self.assertIn('RX_VK_KEEP_FINALIZED_MB', src)
        self.assertIn('owner->second.first != tex->gpu', src)
        self.assertIn('tex->first_written != tex->last_written', src)
        self.assertIn('kept_finalized_bytes -= tex->bytes', src)
        self.assertIn('RX_VK_EVICT_MIN_UNUSED', src)
        self.assertLess(src.index('if (keep_finalized(tex)) {'),src.index('watch_tex(tex, "evicted")'))


if __name__ == '__main__': unittest.main()
