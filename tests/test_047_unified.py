"""0.4.7 unified: the 0.4.5-test.1 unified branch (Render Compute, Render VRAM, the r13k/r13l VRAM policy, the output sizes
and the F1 panel's render distance) merged into the main line's 0.4.7. Read from the sources: no game, no GPU."""

import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class Coherence(unittest.TestCase):
    def test_one_key_per_version(self):
        # (the textual merge left "0.4.5-test.1" twice: in a dict literal the second set silently replaced the first)
        tree = ast.parse(source("akynoleyend/coherence.py"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
                self.assertEqual(len(keys), len(set(keys)), [k for k in keys if keys.count(k) > 1])

    def test_both_branches_update_in_place(self):
        from akynoleyend.coherence import PREVIOUS_HOST_SOURCES
        test1 = PREVIOUS_HOST_SOURCES["0.4.5-test.1"]
        for identity in (
            "df76cd9ce03758f3382f2d8c92875eb4d7623808f53c77ed53357e18acf309ca",   # test.1 on the Teste-1 (main line)
            "e8a1da01e2f0e1be65e599551e06e3027cacf7190a9142c86efa689a60dc6b32",   # the original test.1 tree
            "5b63a1d429ed4c81530a02df815551a4894b6197403708fee577e1d8c94fc605",   # Render VRAM candidate
            "4062b0cfd439f189cc9c9466c949f6347e1bb36f3dba13ab5b8ba1eb0c149e2b",   # the unified package, Windows order
            "ee6953d70e0a23b28757595d46c0db46dbff8e4e410001670625da308142f159",   # the unified package, POSIX order
        ):
            self.assertIn(identity, test1)
        # the 0.4.7 before the merge, as installed on the Teste-1
        self.assertIn("bc8ecd3c98c85da4be33ab8bbf1ba5af5e1b41731872f6f2c84c42839adfd8e9", PREVIOUS_HOST_SOURCES["0.4.7"])
        for version in ("0.4.5-test.2", "0.4.5-test.8", "0.4.6"):
            self.assertIn(version, PREVIOUS_HOST_SOURCES)

    def test_the_updater_starts_from_every_listed_version(self):
        from akynoleyend.coherence import PREVIOUS_HOST_SOURCES
        core = source("builder/AkynoLeyendUpdater/Core.cs")
        for version in ("0.4.3-test.4", "0.4.4", "0.4.5", "0.4.5-test.1", "0.4.5-test.8", "0.4.6"):
            self.assertIn('"%s"' % version, core)
            self.assertIn(version, PREVIOUS_HOST_SOURCES)


class Maintenance(unittest.TestCase):
    def test_main_line_works_get_the_output_sizes_and_the_render_distance_hooks(self):
        text = source("akynoleyend/maintenance.py")
        self.assertIn('startswith(("0.4.5", "0.4.6", "0.4.7"))', text)
        self.assertIn('HOOKS_STAMP = "akyno-panel-hooks-r13-v5"', text)
        self.assertIn('HOOKS_STAMP = "akyno-panel-hooks-r13-v5"', source("nx2/upgrade_output.py"))

    def test_host_abi_unchanged(self):
        from akynoleyend.coherence import HOST_REVISION
        self.assertEqual(HOST_REVISION, "directory304-early-texels-regmap759-output849-v2")


class Notes(unittest.TestCase):
    def test_package_notes_belong_to_this_version(self):
        from akynoleyend import __version__
        from akynoleyend.updater import package_notes
        notes = json.loads(source("docs/notas-atualizacao.json"))
        self.assertEqual(notes["version"], __version__)
        checked = package_notes({"notes": notes["notes"]})
        text = json.dumps(checked, ensure_ascii=False)
        # (0.4.6 took the Teste de desempenho out of the launcher: no note may send a player to it)
        self.assertNotIn("Teste de desempenho >", text)
        self.assertNotIn("DLSS e DLAA indisponíveis", text)
        self.assertIn("Distância de renderização", text)
        self.assertTrue(checked["known_issues"])

    def test_readme_first_names_this_version(self):
        from akynoleyend import __version__
        first = source("LEIA-PRIMEIRO.txt").splitlines()[0]
        self.assertIn(__version__, first)
        self.assertNotIn("0.4.6 será a versão definitiva", source("LEIA-PRIMEIRO.txt"))


if __name__ == "__main__":
    unittest.main()
