"""r13d: a session with exit code 70 and no trace of it in erros.log (the renderer's std::_Exit skipped the log queue), and an
integrated GPU picked in the F1 panel that emptied the discrete GPU's program cache. Sources and the launcher's reading of a
run; no game or GPU: none of this says why the Intel GPU lost its device."""
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from akynoleyend.runtime_failure import DEVICE_LOST_EXIT, renderer_failure  # noqa: E402


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class LogBeforeExit(unittest.TestCase):
    def test_the_renderers_own_exits(self):
        # (the three places the renderer ends the process itself, none through atexit)
        replay, main = source("gpu/vk/vk_replay.cpp"), source("gpu/vk/vk_main.cpp")
        self.assertIn('logf("vk: GPU_FATAL device_lost result=-4 operation=%s; exit=70", operation);', replay)
        self.assertIn("std::_Exit(70);", replay)
        self.assertIn('logf("vk: PREPARE_FAILED: shader seed absent or invalid; exit=71");', main)
        self.assertIn('logf("vk: PREPARE_COMPLETE: shader cache prepared; no gameplay started");', main)
        self.assertEqual(len(re.findall(r"std::_Exit\(", replay + main)), 3)

    def test_the_host_writes_them_as_they_come(self):
        backend = source("host/rx_backend.c")
        body = backend[backend.index("static void host_log(const char *line) {"):]
        body = body[:body.index("\n}\n")]
        for marker in ('strstr(line, "GPU_FATAL")', '!strncmp(line, "vk: device lost", 15)', 'strstr(line, "PREPARE_FAILED")',
                       'strstr(line, "PREPARE_COMPLETE")'):
            self.assertIn(marker, body)
        # (the line queued first, then the queue written: the order of the log kept)
        self.assertLess(body.index('hos_log("%s", line);'), body.index("hos_log_flush();"))
        self.assertIn("if (renderer_ending) hos_log_flush();", body)
        self.assertIn("void hos_log_flush(void);", source("host/hos.h"))
        # (the renderer's API is unchanged: an executable of this revision takes the r13c DLL and the other way round)
        self.assertIn("#define MKWVK_API_VERSION 2", source("gpu/vk/vk_api.h"))


class ExitCode70(unittest.TestCase):
    def test_a_log_without_the_line(self):
        # (the session analysed: the log stops at an upload, the exit code alone says what happened)
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "erros.log"
            log.write_text("[hos Presentation Thread] vk: slow submit: 509.1 ms: uploads 508.3\n", encoding="utf-8")
            self.assertIsNone(renderer_failure(log))
        launch = source("akynoleyend/launch.py")
        self.assertIn("if not failure and status == DEVICE_LOST_EXIT:", launch)
        self.assertLess(launch.index("if not failure and status == DEVICE_LOST_EXIT:"),
                        launch.index('if failure["kind"] == "device_lost":'))
        self.assertEqual(DEVICE_LOST_EXIT, 70)

    def test_seventy_comes_only_from_a_lost_device(self):
        found = []
        for folder in ("gpu", "host"):
            for path in (ROOT / folder).rglob("*"):
                if path.suffix in {".c", ".cpp", ".h"} and re.search(r"[Ee]xit\w*\(\s*70\s*\)", path.read_text(errors="replace")):
                    found.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(found, ["gpu/vk/vk_replay.cpp"])


class CachesByDevice(unittest.TestCase):
    def test_the_device_auto_chooses_keeps_the_names(self):
        main = source("gpu/vk/vk_main.cpp")
        tag = main[main.index("std::string device_file_tag() {"):]
        tag = tag[:tag.index("\n}\n")]
        self.assertIn('if (dev.auto_device) return "";', tag)
        self.assertIn('"_gpu%04x%04x"', tag)
        pick = main[main.index("bool pick_device() {"):main.index("bool create_device() {")]
        # (Auto's choice taken before the panel's row or RX_VK_DEVICE change it)
        self.assertLess(pick.index("const int auto_best = best;"), pick.index('getenv("RX_VK_DEVICE")'))
        self.assertIn("dev.auto_device = best == auto_best;", pick)
        self.assertIn("bool auto_device = true;", source("gpu/vk/vk_internal.h"))

    def test_every_device_stamped_file_is_named_by_device(self):
        shader, draw = source("gpu/vk/vk_shader.cpp"), source("gpu/vk/vk_draw.cpp")
        self.assertIn("tag + device_file_tag()", shader)
        init = draw[draw.index("void pcache_init() {"):draw.index("struct Targets {")]
        self.assertIn("const std::string tag = device_file_tag();", init)
        self.assertIn('pcache_path = dir + "AkynoLeyend_pipelines" + tag + ".bin";', init)
        self.assertIn('pcache_path=dir+"mkw_vk_pipelines_stream"+tag+".bin";', init)
        self.assertNotIn('"AkynoLeyend_pipelines.bin"', init)
        self.assertNotIn('"mkw_vk_pipelines_stream.bin"', init)


class Package(unittest.TestCase):
    def test_an_installed_r13c_is_updated(self):
        # (the manifest of the code-70 session's r13c build: without it every r13c install refuses the r13d package)
        from akynoleyend.coherence import compatible_previous_host
        r13c = "aeef577d4d5ce2ad470536c8ee47d676d5b3af67f6896919a24f9ac588a1b307"
        self.assertIn('"%s"' % r13c, source("akynoleyend/coherence.py"))
        self.assertTrue(compatible_previous_host({
            "version": "0.4.3-test.4", "source_sha256": r13c,
            "host_revision": "directory304-early-texels-regmap759-output849-v2",
            "game_build_id": "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348000000000000000000000000"}))

    def test_the_generic_renderer_is_this_trees(self):
        from akynoleyend.prebuilt import renderer_identity, renderer_prebuilt
        import json
        prebuilt = ROOT / "ferramentas/prebuilt"
        if not (prebuilt / "AkynoLeyend.dll").is_file():
            self.skipTest("source tree without the Windows tools")
        receipt = json.loads((prebuilt / "renderer.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["source_sha256"], renderer_identity(ROOT, ROOT / "ferramentas/deps"))
        self.assertEqual(receipt["shader_stamp"], "4cdbb0029868040b")
        data = (prebuilt / "AkynoLeyend.dll").read_bytes()
        self.assertIn(b"_gpu%04x%04x", data)
        self.assertIn(b"vk: VRAM compaction", data)   # (r13e: the VRAM control)
        if receipt.get("validation_only") is True:
            self.assertEqual(receipt["nvidia_ngx"], "absent")
            self.assertNotIn(b"NVSDK_NGX_VULKAN_Init", data)
        else:
            self.assertIn("DLSS SDK v310.9.16", receipt["nvidia_ngx"])
            self.assertIn(b"NVSDK_NGX_VULKAN_Init", data)
        self.assertEqual(renderer_prebuilt(ROOT, ROOT / "ferramentas/deps", prebuilt,
                                           {"OCARINA_TARGET": "windows-gnu", "RX_RELEASE": "1"}, lambda _: None),
                         prebuilt / "AkynoLeyend.dll")


if __name__ == "__main__":
    unittest.main()
