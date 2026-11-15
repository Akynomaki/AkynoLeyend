"""Index bindings are reused only inside the same command buffer recording."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.native_tools import native_cxx


class IndexBindingTests(unittest.TestCase):
    def test_only_identical_bindings_are_reused(self):
        cxx = native_cxx()
        if cxx is None:
            self.skipTest("C++ compiler unavailable")
        root = Path(__file__).resolve().parents[1]
        draw = (root / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
        begin = draw.index("struct LastIndexBinding")
        end = draw.index("int64_t st_desc_reused", begin)
        recording = draw.split("void draw_begin_recording(", 1)[1].split("// ---- RX_VK_PASS_TRACE", 1)[0]
        self.assertIn("last_index = {};", recording)
        self.assertEqual(draw.count("vkCmdBindIndexBuffer("), 1)
        fixture = r"""
#include <cassert>
#include <cstdint>
using VkCommandBuffer = uint64_t;
using VkBuffer = uint64_t;
using VkDeviceSize = uint64_t;
using VkIndexType = uint32_t;
int issued;
void vkCmdBindIndexBuffer(VkCommandBuffer, VkBuffer, VkDeviceSize, VkIndexType) {
    issued++;
}
"""
        main = r"""
int main() {
    bind_index_buffer(1, 2, 8, 16);
    bind_index_buffer(1, 2, 8, 16);
    assert(issued == 1);
    bind_index_buffer(1, 2, 8, 32);
    bind_index_buffer(1, 2, 16, 32);
    bind_index_buffer(1, 3, 16, 32);
    bind_index_buffer(4, 3, 16, 32);
    assert(issued == 5);
    last_index = {};
    bind_index_buffer(4, 3, 16, 32);
    assert(issued == 6);
}
"""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "index_binding.cpp"
            binary = Path(directory) / "index_binding.exe"
            source.write_text(fixture + draw[begin:end] + main, encoding="utf-8")
            subprocess.run([cxx, "-std=c++20", "-static", str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
