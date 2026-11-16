"""0.4.9: the launcher's Graphics > "Vegetação decorativa". The option's way from the launcher to the renderer: the CLI's
--lite-scene, akynoleyend/graphics.py's AKYNO_LITE_SCENE (only when on), the renderer's list (gpu/vk/lite_scene.h, compiled
and run alone) and the check in gpu/vk/vk_draw.cpp's draw. No game here: none of this says what the picture or the frame rate
is with the option on (that is measured in the game; the catalogue's notes are in the header)."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from akynoleyend.environment import clean_environment  # noqa: E402
from akynoleyend.errors import ProjectError  # noqa: E402
from akynoleyend.graphics import graphics_environment  # noqa: E402
from native_tools import native_cc  # noqa: E402


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


def keys(header):
    body = header[header.index("akyno_lite_scene_keys[] = {"):header.index("};", header.index("akyno_lite_scene_keys[] = {"))]
    return re.findall(r"0x([0-9a-f]{16})ULL", body)


# (programs that must stay: the trees' crowns, the passes without which the screen showed a stale menu, the interface and
# the ground mist)
KEPT = {"6b4dea601798c255", "e28434e1afe8321a", "3b8c07f2eb4bb7d9", "f93c1d64658c850b",
        "abdd8ace9d7b8824", "4dc180c50d9c2bbc", "d6124888a5c5d2e6",
        "fc10fab78898d67e", "dc310f71db89f779", "2479abad219cb19a",
        "1a7482c0ec9991ea", "02ff9920c2571cc2",
        "701ae221d88b2908"}   # (the ground mist)
EFFECTS = {"a37e5fc5f233e1ba", "5bea5f63bbd3d665", "cd9e931fd94b96d8", "bd375eeff1343782"}


class Version(unittest.TestCase):
    def test_this_is_0_4_9(self):
        from akynoleyend import __version__
        from akynoleyend.coherence import PREVIOUS_HOST_SOURCES
        self.assertEqual(__version__, "0.4.9")
        self.assertEqual(source("VERSION").strip(), "0.4.9")
        self.assertIn("<Version>0.4.9</Version>", source("builder/AkynoLeyendBuilder/AkynoLeyendBuilder.csproj"))
        updater = source("builder/AkynoLeyendUpdater/AkynoLeyendUpdater.csproj")
        self.assertIn("<Version>0.4.9</Version>", updater)
        self.assertIn("<AssemblyName>AkynoLeyend-Atualizador-0.4.9</AssemblyName>", updater)
        core = source("builder/AkynoLeyendUpdater/Core.cs")
        self.assertIn('public const string To = "0.4.9";', core)
        self.assertIn('"0.4.6", "0.4.7", "0.4.8" };', core)
        self.assertIn('__version__ != "0.4.9" or "0.4.8" not in PREVIOUS_HOST_SOURCES', source("tools/make_distribution.py"))
        # the final 0.4.8 tree (what its complete package's Criar records) and the 0.4.8 installs before it
        for identity in ("bc0d21660a20abcc6746d257c24f73ba7d73adf8bfdac683af64f3493bed6913",
                         "47c4982f115f741d470c06162e01070a57fda94d19385684322bf4b154d39f70"):
            self.assertIn(identity, PREVIOUS_HOST_SOURCES["0.4.8"])

    def test_notes_and_readme(self):
        import json
        notes = json.loads(source("docs/notas-atualizacao.json"))
        self.assertEqual(notes["version"], "0.4.9")
        self.assertIn("Vegetação e efeitos decorativos", notes["notes"]["new"][0])
        self.assertIn("0.4.9", source("LEIA-PRIMEIRO.txt").splitlines()[0])


class Environment(unittest.TestCase):
    def test_on_sets_the_variable(self):
        self.assertEqual(graphics_environment(lite_scene=True).get("AKYNO_LITE_SCENE"), "1")

    def test_off_and_unset_leave_the_game_as_before(self):
        self.assertEqual(graphics_environment(lite_scene=False), graphics_environment())
        self.assertNotIn("AKYNO_LITE_SCENE", graphics_environment(lite_scene=False))
        self.assertNotIn("AKYNO_LITE_SCENE", graphics_environment())

    def test_refuses_a_non_boolean(self):
        for value in ("on", 1, "1"):
            with self.assertRaises(ProjectError):
                graphics_environment(lite_scene=value)

    def test_not_inherited_from_the_launchers_own_environment(self):
        # (a value left in the parent's environment never reaches the game: the AKYNO_ prefix is cleaned)
        self.assertNotIn("AKYNO_LITE_SCENE", clean_environment({"AKYNO_LITE_SCENE": "1", "PATH": "x"}))

    def test_cli_and_launch_pass_it_on(self):
        cli = source("akynoleyend/cli.py")
        self.assertIn('player.add_argument("--lite-scene", choices=("on", "off")', cli)
        self.assertEqual(cli.count('lite_scene=None if args.lite_scene is None else args.lite_scene == "on",'), 2)
        launch = source("akynoleyend/launch.py")
        self.assertIn("lite_scene: bool | None = None,", launch)
        self.assertIn("        lite_scene=lite_scene,\n    )\n    graphics = graphics_environment(**graphics_options)", launch)


class List(unittest.TestCase):
    def test_keys(self):
        found = keys(source("gpu/vk/lite_scene.h"))
        self.assertEqual(len(found), 36)
        self.assertTrue(EFFECTS <= set(found))
        self.assertEqual(len(set(found)), len(found))
        self.assertFalse(KEPT & set(found))

    def test_the_header_alone(self):
        compiler = native_cc()
        if not compiler:
            self.skipTest("C compiler unavailable")
        header = source("gpu/vk/lite_scene.h")
        found = keys(header)
        checks = "".join(f"    CHECK(akyno_lite_scene_key(0x{k}ULL));\n" for k in found)
        checks += "".join(f"    CHECK(!akyno_lite_scene_key(0x{k}ULL));\n" for k in sorted(KEPT))
        text = ('#include <stdio.h>\n#include "lite_scene.h"\n'
                '#define CHECK(x) do { if (!(x)) { printf("failed: %s\\n", #x); return 1; } } while (0)\n'
                "int main(void) {\n" + checks +
                "    CHECK(!akyno_lite_scene_key(0));\n"
                '    CHECK(akyno_lite_scene_value("1"));\n'
                '    CHECK(!akyno_lite_scene_value(0) && !akyno_lite_scene_value("") && !akyno_lite_scene_value("0"));\n'
                '    CHECK(!akyno_lite_scene_value("10") && !akyno_lite_scene_value("on") && !akyno_lite_scene_value(" 1"));\n'
                "    return 0;\n}\n")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "t.c").write_text(text, encoding="utf-8")
            binary = path / ("t.exe" if os.name == "nt" else "t")
            built = subprocess.run([compiler, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "gpu/vk"),
                                    str(path / "t.c"), "-o", str(binary)], capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


class Draw(unittest.TestCase):
    def test_checked_once_and_where_the_other_skips_are(self):
        draw = source("gpu/vk/vk_draw.cpp")
        self.assertIn('#include "lite_scene.h"', draw)
        start = draw.index("void draw(VkCommandBuffer cmd, NvnState& s, const DrawArgs& d) {")
        live = draw.index("if (skip_live(cp->key)) return;", start)
        lite = draw.index('akyno_lite_scene_value(getenv("AKYNO_LITE_SCENE"))', start)
        check = draw.index("if (lite && akyno_lite_scene_key(cp->key)) return;", start)
        prog = draw.index("RX_VK_SKIP_PROG: draws too", start)
        self.assertTrue(live < lite < check < prog)
        # (the variable read in the static's initializer: once, not on every draw)
        self.assertIn("static const bool lite = [] {", draw[live:check])
        self.assertEqual(draw.count('getenv("AKYNO_LITE_SCENE")'), 1)

    def test_draw_stats_tell_the_kind_of_draw(self):
        draw = source("gpu/vk/vk_draw.cpp")
        self.assertIn("uint8_t blend, blend_src, blend_dst, depth_test, depth_write, a2c;", draw)
        self.assertIn("if (stats_query.cmd) stats_note_state(stats_query.index, s);", draw)
        self.assertIn('" {blend %llu src %u dst %u | ztest %llu | zwrite %llu | a2c %llu | inst %llu}"', draw)


class Launcher(unittest.TestCase):
    def test_the_graphics_row(self):
        xaml = source("builder/AkynoLeyendBuilder/MainWindow.xaml")
        self.assertIn('<ComboBox x:Name="LiteSceneBox"', xaml)
        self.assertIn('Tag="off" />', xaml[xaml.index('x:Name="LiteSceneBox"'):])
        self.assertIn("Vegetação e efeitos decorativos (reiniciar o jogo)", xaml)
        window = source("builder/AkynoLeyendBuilder/MainWindow.xaml.cs")
        self.assertIn("LiteScene=Choice(LiteSceneBox)", window)
        self.assertIn("Select(LiteSceneBox,g.LiteScene);", window)
        options = source("builder/AkynoLeyendBuilder/LaunchOptions.cs")
        self.assertIn('public string LiteScene{get;init;}="off";', options)
        self.assertIn('if(LiteScene=="on"){args.Add("--lite-scene");args.Add("on");}', options)


if __name__ == "__main__":
    unittest.main()
