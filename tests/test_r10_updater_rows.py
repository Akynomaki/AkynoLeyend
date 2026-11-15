"""r10: the updater's fixes (abandoned staging, its log, cleanup after the files are in place), the frame-step hook added to
an existing work by an update, and the F1 rows taken from Hookshot v2.1.0. No game or GPU: none of this says the rows were
tried in the game."""
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


class RowArithmetic(unittest.TestCase):
    def test_native(self):
        from tests.native_tools import native_cxx
        cxx = native_cxx()
        if not cxx:
            self.skipTest("no native C++ compiler")
        with tempfile.TemporaryDirectory(prefix="menu-rows-r10-") as tmp:
            exe = Path(tmp) / "menu-rows-r10.exe"
            subprocess.run([cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", str(ROOT / "tests/native/menu_rows_r10.cpp"),
                            "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


class Rows(unittest.TestCase):
    def test_rows_saved_under_the_keys_their_readers_use(self):
        menu = source("gpu/vk/vk_menu.cpp")
        names = re.findall(r'^    \{"([A-Za-z ]+)", "[^"]+", &opts\.', menu, re.M)
        keys = {name.lower().replace(" ", "_") for name in names}
        for key in ("dlss_model", "mouse_sensitivity", "menu_shortcut"):
            self.assertIn(key, keys)
        self.assertIn('boot_option("dlss_model", 0)', source("gpu/vk/vk_fsr_sdk.cpp"))
        self.assertIn("case AKYNO_OPT_MOUSE_SENS: return opts.mouse_sens;", source("gpu/vk/vk_replay.cpp"))
        self.assertIn("rx_option(AKYNO_OPT_MOUSE_SENS, 0)", source("host/nn_hid.c"))

    def test_rows_listed_on_pages_and_restart(self):
        menu = source("gpu/vk/vk_menu.cpp")
        self.assertIn("DlssModel, MouseSens, MenuKey,", menu)   # (r11 rows follow them, then SettingCount)
        video = re.search(r"constexpr Setting video_rows\[\] = \{([^}]+)\}", menu).group(1)
        pad = re.search(r"constexpr Setting pad_rows\[\] = \{([^}]+)\}", menu).group(1)
        restart = re.search(r"constexpr Setting restart_rows\[\] = \{([^}]+)\}", menu).group(1)
        self.assertIn("DlssModel", video)
        self.assertIn("DlssModel", restart)
        self.assertIn("MouseSens", pad)
        self.assertIn("MenuKey", pad)

    def test_esc_opens_without_closing_in_the_same_tick(self):
        menu = source("gpu/vk/vk_menu.cpp")
        self.assertIn("if (press[5] && !esc_opens) open_now = false;", menu)
        self.assertIn("akyno_menu_opens(opts.menu_shortcut, press[6], press[0], chord, 0)", menu)

    def test_defaults_leave_the_game_as_it_was(self):
        header = source("gpu/vk/vk_menu.h")
        for line in ("int dlss_model = 0;", "int mouse_sens = 0;", "int menu_shortcut = 0;"):
            self.assertIn(line, header)
        self.assertNotIn("AKYNO_OPT_", source("gpu/vk/vk_api.h"))


class AbandonedStaging(unittest.TestCase):
    def test_only_never_installed_folders_go(self):
        from akynoleyend.updater import clear_abandoned
        with tempfile.TemporaryDirectory() as tmp:
            updates = Path(tmp) / "atualizacoes"
            checked = updates / "pendente-a" / "arquivos"
            checked.mkdir(parents=True)
            (checked / "x.txt").write_text("x")
            rollback = updates / "pendente-b"
            (rollback / "anterior").mkdir(parents=True)
            keep = updates / "pendente-c"
            keep.mkdir()
            (updates / "ultima-atualizacao.log").write_text("log")
            notes = []
            self.assertEqual(clear_abandoned(updates, keep=keep, report=notes.append), 1)
            self.assertFalse((updates / "pendente-a").exists())
            self.assertTrue(rollback.exists() and keep.exists() and (updates / "ultima-atualizacao.log").exists())
            self.assertTrue(notes)
            self.assertEqual(clear_abandoned(Path(tmp) / "nada"), 0)

    def test_stage_clears_before_staging(self):
        self.assertIn('clear_abandoned(root / "atualizacoes", report=report)', source("akynoleyend/updater.py"))


class ApplyUpdate(unittest.TestCase):
    def test_installs_logs_and_cleans_up_without_a_game(self):
        from akynoleyend.updater import apply_update
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "inst"
            folder = root / "atualizacoes" / "pendente-1"
            (folder / "arquivos").mkdir(parents=True)
            payload = b"novo\n"
            (folder / "arquivos" / "nota.txt").write_bytes(payload)
            (root / "nota.txt").write_bytes(b"velho\n")
            plan = folder / "plano.json"
            plan.write_text(json.dumps({"schema": 1, "root": str(root), "output": str(root / "jogo"), "version": "x",
                                        "files": {"nota.txt": hashlib.sha256(payload).hexdigest()}, "jobs": None,
                                        "notes": {}}), encoding="utf-8")
            self.assertEqual(apply_update(plan, 0, restart=False), 0)
            self.assertEqual((root / "nota.txt").read_bytes(), payload)
            self.assertFalse(folder.exists())
            log = (root / "atualizacoes" / "ultima-atualizacao.log").read_text(encoding="utf-8")
            self.assertIn("Instalacao: " + str(root), log)
            self.assertIn("Nenhum jogo compilado", log)
            self.assertIn("@@done", log)

    def test_cleanup_cannot_fail_an_installed_update(self):
        text = source("akynoleyend/updater.py")
        body = text[text.index("def apply_update"):]
        self.assertLess(body.index("install_files(plan, maintain)"), body.index("shutil.rmtree(plan.parent)"))
        self.assertIn('except OSError as error: note("Pasta temporaria mantida', body)
        self.assertLess(body.index("shutil.rmtree(plan.parent)"), body.index('subprocess.Popen([str(root/"AkynoLeyendBuilder.exe")]'))


class StepHookByUpdate(unittest.TestCase):
    """nx2/upgrade_output.py: an update adds the frame-step hook to a work lifted without it, both divides or neither."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location("oot_patches_r10", ROOT / "nx2/oot_patches.py")
        self.patches = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.patches)

    def lifted(self, register, name):
        return ('#include "a64.h"\nvoid %s(Ctx *__restrict A64_NOESC c) {\n    uint64_t _a=1,_b=2,_v;\n'
                "    _v=a64_fpx_div32_div32(c,_a,_b);\n    a64_vset64(c->vreg[%d],_v);}\n}\n\nvoid f_0(Ctx *c) {\n}\n" % (name, register))

    def step_edits(self):
        sys.path.insert(0, str(ROOT / "nx2"))
        try:
            spec = importlib.util.spec_from_file_location("upgrade_output_r10", ROOT / "nx2/upgrade_output.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as error:   # (nx2/build.py wants the project's toolchain layout)
            self.skipTest("nx2/upgrade_output.py not importable here: %s" % error)
        return module.step_edits

    def test_both_sites_or_none(self):
        step_edits = self.step_edits()
        with tempfile.TemporaryDirectory() as tmp:
            gen = Path(tmp)
            (gen / "code_016.c").write_text(self.lifted(8, "f_80706be0"), newline="")
            (gen / "code_099.c").write_text("void f_1(Ctx *c) {\n}\n", newline="")
            edits, hooked = step_edits(gen, {})
            self.assertEqual((edits, hooked), ({}, 0))           # (one divide only: nothing)
            (gen / "code_176.c").write_text(self.lifted(0, "f_83b6ea90"), newline="")
            edits, hooked = step_edits(gen, {})
            self.assertEqual(hooked, 2)
            self.assertEqual(sorted(p.name for p in edits), ["code_016.c", "code_176.c"])
            for data in edits.values():
                self.assertIn(self.patches.STEP_MARK.encode(), data)
                self.assertNotIn(b"\r\n", data)
            for path, data in edits.items():
                path.write_bytes(data)
            self.assertEqual(step_edits(gen, {}), ({}, 2))     # (hooked already: nothing to compile)

    def test_a_crlf_file_is_matched_and_keeps_its_line_ends(self):
        # (the Windows work of the r9 correction had f_83b6ea90's file in CRLF: the hook was found at 1 of 2 divides)
        step_edits = self.step_edits()
        with tempfile.TemporaryDirectory() as tmp:
            gen = Path(tmp)
            (gen / "code_017.c").write_bytes(self.lifted(8, "f_80706be0").encode())
            (gen / "code_178.c").write_bytes(self.lifted(0, "f_83b6ea90").replace("\n", "\r\n").encode())
            edits, hooked = step_edits(gen, {})
            self.assertEqual(hooked, 2)
            crlf = edits[gen / "code_178.c"]
            self.assertIn(self.patches.STEP_MARK.encode(), crlf)
            self.assertNotIn(b"\n", crlf.replace(b"\r\n", b""))   # (every line end still CRLF)
            self.assertNotIn(b"\r\n", edits[gen / "code_017.c"])

    def test_no_marker_without_the_hook(self):
        text = source("nx2/upgrade_output.py")
        self.assertIn("if step_sites:   # (hooked already; without the hook the next update looks again)", text)

    def test_maintenance_asks_for_it(self):
        text = source("akynoleyend/maintenance.py")
        self.assertIn('needs_step_upgrade = reuse_game_from is None and (not (gen / STEP_STAMP).is_file()', text)   # (r12: or stale stubs)
        self.assertIn('["--step-only"] if step_only else []', text)
        self.assertIn('STEP_STAMP = "akyno-frame-step-v1"', source("nx2/upgrade_output.py"))
        self.assertIn('STEP_STAMP = "akyno-frame-step-v1"', text)


if __name__ == "__main__":
    unittest.main()
