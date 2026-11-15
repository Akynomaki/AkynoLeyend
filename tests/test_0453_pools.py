"""0.4.5-test.3: textures and render targets in pools of their own, the core kept again, and the recording thread's samples.

The renderer and the host are read from the sources (they run only inside the game); tools/resumo_medicao.py runs here on a
made-up log. No game: none of this says the VRAM stayed under the driver's limit or the stutters went away.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Pools(unittest.TestCase):
    def setUp(self):
        self.vma = source("gpu/vk/vk_vma.cpp")

    def test_two_pools_unless_asked_for_one(self):
        self.assertIn("VmaPool image_pools[2]", self.vma)
        self.assertIn('getenv("RX_VK_IMAGE_POOLS") && atoi(getenv("RX_VK_IMAGE_POOLS")) == 1', self.vma)
        self.assertIn("for (int p = image_pools_split() ? 0 : 1; p < 2; p++)", self.vma)
        self.assertNotIn("images_pool()", self.vma)

    def test_only_the_games_textures_go_to_the_textures_pool(self):
        self.assertIn("ImagePool kind = ImagePool::Other", source("gpu/vk/vk_internal.h"))
        texture = source("gpu/vk/vk_texture.cpp")
        self.assertEqual(len(re.findall(r"ImagePool::Textures", texture)), 1)
        self.assertIn("create_image(ci, x.image, x.allocation, for_target ? ImagePool::Other : ImagePool::Textures)", texture)
        for other in ("vk_framegen.cpp", "vk_fsr_sdk.cpp", "vk_dump.cpp", "vk_draw.cpp", "vk_replay.cpp"):
            self.assertNotIn("ImagePool::Textures", source("gpu/vk/" + other), other)

    def test_blocks_know_their_pool_and_forget_it_when_empty(self):
        self.assertIn("block_pool[block] =", self.vma)
        self.assertIn("block_pool.erase(b->first);", self.vma)
        self.assertIn("targets and the rest %llu blocks (%llu MB of holes)", self.vma)

    def test_the_shader_stamp_is_kept(self):
        self.assertEqual(json.loads(source("ferramentas/prebuilt/renderer.json"))["shader_stamp"], "4cdbb0029868040b")


class CoreKept(unittest.TestCase):
    def test_kept_by_default_given_up_on_request(self):
        text = source("host/nvn_native.c")
        self.assertIn('getenv("HOS_SUBMIT_FREE_CORE")', text)
        self.assertNotIn("HOS_SUBMIT_KEEP_CORE", text)
        from akynoleyend.environment import EXPERIMENTS
        self.assertEqual(EXPERIMENTS["nucleo-solto"], {"HOS_SUBMIT_FREE_CORE": "1"})
        self.assertEqual(EXPERIMENTS["pool-unico"], {"RX_VK_IMAGE_POOLS": "1"})
        self.assertTrue(EXPERIMENTS["amostrar"]["HOS_SAMPLE"].startswith("Presentation Thread"))   # (test.4: |sead::MainThread)
        self.assertNotIn("nucleo-preso", EXPERIMENTS)


class Samples(unittest.TestCase):
    def test_samples_are_summed_and_ranked(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import resumo_medicao
        with tempfile.TemporaryDirectory(prefix="amostras-") as tmp:
            folder = Path(tmp)
            (folder / "erros.log").write_text("\n".join([
                "[hos host] prof-sample leaf (5000 samples): AkynoLeyend.dll+1a00 2000, AkynoLeyend.dll+1a40 1000, nvoglv64.dll+300 500,",
                "[hos host] prof-sample ours (5000 samples): AkynoLeyend.exe+400 3000,",
                "[hos host] prof-sample leaf (5000 samples): AkynoLeyend.dll+1a00 1500,",
            ]) + "\n", encoding="utf-8")
            r = resumo_medicao.summarize(folder, symbols=False)
        leaf = r["samples"]["Presentation Thread"]["leaf"]   # (0.4.5-test.4: by thread; untagged lines are its)
        self.assertEqual(leaf["samples"], 10000)
        self.assertEqual(leaf["top"][0], ("AkynoLeyend.dll+1a00", 3500, 35.0))
        self.assertEqual(r["samples"]["Presentation Thread"]["ours"]["top"][0][1], 3000)
        self.assertIn("Amostras de Presentation Thread (onde estava), 10000 no total:", resumo_medicao.report(r))

    def test_symbols_name_the_function_an_offset_is_in(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import resumo_medicao
        s = resumo_medicao.Symbols([])
        s.tables["x.dll"] = ([0x100, 0x200, 0x300], ["a", "b", "c"])
        self.assertEqual(s.name("x.dll", 0x250), "x.dll!b")
        self.assertEqual(s.name("x.dll", 0x50), "x.dll+50")
        self.assertEqual(s.name("y.dll", 0x10), "y.dll+10")


class Version(unittest.TestCase):
    def test_test_2_installs_update_in_place(self):
        from akynoleyend import __version__
        from akynoleyend.coherence import HOST_REVISION, compatible_previous_host
        self.assertTrue(__version__.startswith("0.4.5-test.") or __version__ in ("0.4.6", "0.4.7", "0.4.8"))
        self.assertTrue(compatible_previous_host({"version": "0.4.5-test.2", "host_revision": HOST_REVISION,
            "source_sha256": "081373776e2f4647d34dc88686a3814be8c860087fe15443b146a1b2a17007ed", "game_build_id": "e0f3ccfa"}))
        self.assertIn('"0.4.5-test.2"', source("builder/AkynoLeyendUpdater/Core.cs"))   # (test.4: test.3 after it)


if __name__ == "__main__":
    unittest.main()
