"""0.4.8: the preload at every start (the programs and pipelines play met, read and built before the game and, past a bounded
wait, in the background) and the larger shader bank. Read from the sources: no game, no GPU."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


def function(text, signature):
    """The body of the C++ function that starts with signature (up to the next line that is a lone closing brace)."""
    start = text.index(signature)
    end = text.index("\n}\n", start)
    return text[start:end]


class Version(unittest.TestCase):
    def test_this_is_0_4_8(self):
        # (0.4.9: the version itself is test_049_lite_scene's; the updater still starts from 0.4.7)
        from akynoleyend import __version__
        from akynoleyend.coherence import PREVIOUS_HOST_SOURCES
        self.assertIn(__version__, ("0.4.8", "0.4.9"))
        core = source("builder/AkynoLeyendUpdater/Core.cs")
        self.assertIn('"0.4.6", "0.4.7"', core)
        self.assertIn('"0.4.7" not in PREVIOUS_HOST_SOURCES', source("tools/make_distribution.py"))
        # the 0.4.7 before and after the unified branch, as installed (Windows and POSIX orders)
        for identity in ("bc8ecd3c98c85da4be33ab8bbf1ba5af5e1b41731872f6f2c84c42839adfd8e9",
                         "7661e6c99c842080c46e0bbc56119109cbdee925b26c6651174fa9654b706f65",
                         "b3c7d8cb699380bcc49c55668fe9f7cf93217b8c0d485ab067e25bd73faa32ff"):
            self.assertIn(identity, PREVIOUS_HOST_SOURCES["0.4.7"])

    def test_notes_and_readme(self):
        notes = json.loads(source("docs/notas-atualizacao.json"))
        self.assertIn(notes["version"], ("0.4.8", "0.4.9"))
        self.assertIn("pré-carrega", " ".join(notes["notes"]["new"]).lower())
        self.assertIn("0.4.8", source("LEIA-PRIMEIRO.txt"))


class Preload(unittest.TestCase):
    draw = source("gpu/vk/vk_draw.cpp")

    def test_the_start_waits_a_bounded_time_and_the_rest_goes_on(self):
        run = function(self.draw, "void precompile_run(")
        self.assertIn('"RX_VK_PRELOAD_WAIT_MS", 20000', run)
        self.assertIn('"RX_VK_PRELOAD_THREADS", 2', run)
        self.assertIn("std::thread(preload_worker, P, i).detach()", run)
        # the compute pipelines and fallbacks are always waited for (a dispatch is never left out), the graphics ones for at most
        # the wait; a preparation waits for all of it (it saves the cache and exits)
        self.assertIn("P->compute_done.load() >= P->compute_total && waited >= (double)wait_ms", run)
        self.assertIn("prepare_only ? 0 :", run)
        self.assertIn("P->playing.store(true", run)
        # the old precompile wrote into the replay thread's map; the preload never does
        self.assertNotIn("pipelines.emplace", run)
        self.assertNotIn("pipelines.find", function(self.draw, "void preload_graphics("))

    def test_compute_work_is_all_before_play(self):
        worker = function(self.draw, "void preload_worker(")
        # tasks are taken in order: compute, fallbacks, then the graphics notes; in play the extra workers stop
        self.assertLess(worker.index("i < P->computes.size()"), worker.index("preload_graphics("))
        self.assertIn("if (index >= P->play_workers) break;", worker)
        self.assertIn("THREAD_PRIORITY_LOWEST", worker)

    def test_draws_take_the_preloaded_pipelines(self):
        graphics = function(self.draw, "PipeEntry* graphics_pipeline(")
        self.assertIn("preload_take(key)", graphics)
        self.assertLess(graphics.index("preload_take(key)"), graphics.index("pipeline_note(key"))
        take = function(self.draw, "VkPipeline preload_take(")
        self.assertIn("preload_claimed.insert(key)", take)
        give = function(self.draw, "bool preload_give(")
        self.assertIn("vkDestroyPipeline", give)   # (a key a draw made first: the preload's build is never used)

    def test_programs_named_by_notes_share_the_budget(self):
        shader = source("gpu/vk/vk_shader.cpp")
        some = function(shader, "size_t program_cache_load_some(const std::vector<uint64_t>& wanted")
        self.assertIn("if (a < named.size()) consider(named[a++]);", some)
        self.assertIn("if (b < compute.size()) consider(compute[b++]);", some)
        self.assertIn("const std::vector<uint64_t>& wanted", source("gpu/vk/vk_shader.h"))

    def test_budgets(self):
        from akynoleyend.environment import CACHE_MODES
        self.assertEqual(CACHE_MODES["streaming"]["RX_VK_PREWARM_PROGRAMS"], "2048")
        self.assertEqual(CACHE_MODES["streaming"]["RX_VK_PREWARM_PIPELINES"], "4096")
        self.assertEqual(CACHE_MODES["equilibrado"]["RX_VK_PREWARM_PIPELINES"], "8192")
        policy = source("gpu/vk/cache_policy.h")
        for name, value in (("RX_VK_PREWARM_PROGRAMS", "8192"), ("RX_VK_PREWARM_PIPELINES", "8192")):
            limit = int(re.search(r'"%s", \d+, 0, (\d+)\)' % name, policy)[1])
            self.assertGreaterEqual(limit, int(value), name)

    def test_the_prepared_marker_is_0_4_7s(self):
        # (the NX2navi's shaders gave the bank nothing new: no stamp change, and no preparation again after the update)
        shader = source("gpu/vk/vk_shader.cpp")
        self.assertIn("return disk_stamp() ^ (mesh_loads_inlined() ? 0x7231336900000001ull : 0ull);",
                      function(shader, "uint64_t program_prepared_stamp()"))
        self.assertNotIn("seed_bank_stamp", shader)


class LogSummary(unittest.TestCase):
    def test_the_background_part_is_read(self):
        import importlib.util
        import tempfile
        spec = importlib.util.spec_from_file_location("log_summary", ROOT / "tools/analisar_log_shaders.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "game.log"
            log.write_text(
                "[hos host] vk: precompile: 900 programs, 3759 graphics notes, 1200 graphics and 117 compute pipelines built in"
                " 20041 ms; 2559 of the graphics notes go on in the background\n"
                "[hos host] vk: preload: the background part is done: 3500 graphics pipelines built in all, 3300 handed to play,"
                " 200 met in play first; 95.2 s after the start\n", encoding="utf-8")
            result = module.analyze(log)
        self.assertEqual(result["pipeline_precompile"]["graphics_notes"], 3759)
        self.assertEqual(result["preload_background"]["left_for_play"], 2559)
        self.assertEqual(result["preload_background"]["handed"], 3300)


if __name__ == "__main__":
    unittest.main()
