"""r13: Hookshot v2.1.0's Text speed, Text size, Mouse camera and Disable camera centering (commit 8ef84611): the three hooks in
the lifted code (nx2/oot_patches.py), their update for a work lifted before them (nx2/upgrade_output.py), the host's files
compiled alone against stand-ins, and the panel's rows. The fixtures are Hookshot's own tests' (tests/test_text_speed.py,
test_text_size.py, test_mouse_native.py, test_camera_centering.py), with this base's option ids. No game or GPU: none of this
says the rows were tried in the game."""
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


patches = load("oot_patches_r13", "nx2/oot_patches.py")

# (the shape of the lifted function, build e0f3ccfa: the call that reaches the block, the block's head; the block's backward
# goto carries the interrupt poll (nx2/poll.py), and a --no-polls build has it bare: both shapes are patched)
TEXT_LIFTED = '''#include "a64.h"
void f_80b1e140(Ctx *A64_NOESC c);
void f_80b1e140(Ctx *__restrict A64_NOESC c) {
if (((c->x[9] >> 0) & 1)) { goto L_80b1e1b4; }
L_80b1e18c:;
return;
''' + patches.TEXT_OLD_POLLED + '''if (((c->x[8] >> 4) & 1)) { goto L_80b1e460; }
}
void f_80b1e9f0(Ctx *__restrict A64_NOESC c) {
}
'''
CAM_BODY = patches.CAM_FOLLOW_ANCHOR + "    c->x[25] = c->x[26];\n" + patches.CAM_FOLLOW_JOIN + "\n    return;\n"
CAM_LIFTED = '#include "a64.h"\nvoid before(Ctx *c) {\n' + CAM_BODY + "}\n" + patches.CAM_HEAD + CAM_BODY + "}\n"


class TextSpeedPatch(unittest.TestCase):
    def test_both_shapes_once_and_only_that_function(self):
        out = patches.patch_text_speed(TEXT_LIFTED)
        self.assertEqual(out.count("*= hos_text_scale"), 1)
        self.assertLess(out.index(patches.TEXT_DECL), out.index("void f_80b1e140"))
        self.assertGreater(out.index("*= hos_text_scale"), out.index("L_80b1e1b4:;"))
        self.assertIn("A64_POLL(c); goto L_80b1e18c;", out)
        self.assertEqual(out.count(patches.TEXT_MARK), 1)
        bare = patches.patch_text_speed(TEXT_LIFTED.replace(patches.TEXT_OLD_POLLED, patches.TEXT_OLD))
        self.assertEqual(bare.count("*= hos_text_scale"), 1)
        self.assertNotIn("A64_POLL", bare)
        self.assertEqual(patches.patch_text_speed(out), out)
        self.assertEqual(patches.patch_text_speed(bare), bare)
        self.assertIsNone(patches.patch_text_speed(TEXT_LIFTED.replace("f_80b1e140", "f_80b1e150")))
        other = TEXT_LIFTED.replace("+ 110);", "+ 112);")   # (another game version)
        self.assertEqual(patches.patch_text_speed(other), other)


class CameraPatches(unittest.TestCase):
    def test_mouse_camera_first_line_once(self):
        out = patches.patch_mouse_camera(CAM_LIFTED)
        self.assertIn(patches.CAM_HEAD + "    hos_mouse_camera(c->x[0]);", out)
        self.assertIn("extern void hos_mouse_camera(uint64_t camera);\n", out)
        self.assertEqual(patches.patch_mouse_camera(out), out)
        self.assertIsNone(patches.patch_mouse_camera('#include "a64.h"\nvoid f_1(Ctx *c) {\n}\n'))

    def test_centering_hook_only_in_the_camera(self):
        out = patches.patch_camera_centering(CAM_LIFTED)
        self.assertEqual(out.count(patches.CAM_FOLLOW_HOOK), 1)
        self.assertGreater(out.index(patches.CAM_FOLLOW_HOOK), out.index(patches.CAM_HEAD))
        self.assertEqual(patches.patch_camera_centering(out), out)
        for anchor in (patches.CAM_FOLLOW_ANCHOR, patches.CAM_FOLLOW_JOIN):
            for copies in (0, 2):
                body = CAM_BODY.replace(anchor, anchor * copies)
                self.assertIsNone(patches.patch_camera_centering('#include "a64.h"\n' + patches.CAM_HEAD + body + "}\n"))

    def test_all_hooks_named(self):
        text, held = patches.patch_panel_hooks(CAM_LIFTED)
        self.assertEqual(held, ["mouse camera", "camera centering"])
        again, held_again = patches.patch_panel_hooks(text)
        self.assertEqual((again, held_again), (text, held))
        _, held = patches.patch_panel_hooks(TEXT_LIFTED)
        self.assertEqual(held, ["text speed and size"])
        self.assertEqual(patches.patch_panel_hooks("void f_1(Ctx *c) {\n}\n"), ("void f_1(Ctx *c) {\n}\n", []))


class HooksByUpdate(unittest.TestCase):
    """nx2/upgrade_output.py: an update adds the hooks to a work lifted without them."""

    def hook_edits(self):
        sys.path.insert(0, str(ROOT / "nx2"))
        try:
            return load("upgrade_output_r13", "nx2/upgrade_output.py")
        except Exception as error:   # (nx2/build.py wants the project's toolchain layout)
            self.skipTest("nx2/upgrade_output.py not importable here: %s" % error)

    def test_adds_them_keeps_line_ends_and_is_quiet_after(self):
        module = self.hook_edits()
        with tempfile.TemporaryDirectory() as tmp:
            gen = Path(tmp)
            (gen / "code_028.c").write_bytes(TEXT_LIFTED.replace("\n", "\r\n").encode())
            (gen / "code_hot_1.c").write_bytes(CAM_LIFTED.encode())
            (gen / "code_099.c").write_bytes(b"void f_1(Ctx *c) {\n}\n")
            edits, held = module.hook_edits(gen, {})
            self.assertEqual(held, {"text speed and size", "mouse camera", "camera centering"})
            self.assertEqual(sorted(p.name for p in edits), ["code_028.c", "code_hot_1.c"])
            crlf = edits[gen / "code_028.c"]
            self.assertIn(patches.TEXT_MARK.encode(), crlf)
            self.assertNotIn(b"\n", crlf.replace(b"\r\n", b""))   # (every line end still CRLF)
            self.assertNotIn(b"\r\n", edits[gen / "code_hot_1.c"])
            for path, data in edits.items():
                path.write_bytes(data)
            self.assertEqual(module.hook_edits(gen, {}), ({}, held))   # (hooked already: nothing to compile)

    def test_stamp_only_with_every_hook(self):
        text = source("nx2/upgrade_output.py")
        self.assertIn('HOOKS_STAMP = "akyno-panel-hooks-r13-v5"', text)
        self.assertIn("all_hooks = len(hooks) == len(oot_patches.PANEL_HOOKS)", text)
        self.assertEqual(text.count("if all_hooks:\n        (gen / HOOKS_STAMP).touch()"), 1)
        self.assertEqual(text.count("if all_hooks:\n            (gen / HOOKS_STAMP).touch()"), 1)
        maintenance = source("akynoleyend/maintenance.py")
        self.assertIn('HOOKS_STAMP = "akyno-panel-hooks-r13-v5"', maintenance)
        self.assertIn("or not (gen / HOOKS_STAMP).is_file())", maintenance)
        self.assertIn("if not had_hooks:\n                (gen / HOOKS_STAMP).unlink(missing_ok=True)", maintenance)

    def test_the_lift_makes_them_too(self):
        text = source("nx2/oot_patches.py")
        apply = text[text.index("def apply(gen):"):]
        self.assertIn("s, held = patch_panel_hooks(s)", apply)


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def compile_and_run(test, files, sources, flags=()):
    from tests.native_tools import native_cc
    cc = native_cc()
    if not cc:
        test.skipTest("no native C compiler")
    with tempfile.TemporaryDirectory(prefix="r13-native-") as tmp:
        tmp = Path(tmp)
        for name, text in files.items():
            (tmp / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp / name).write_text(text, encoding="utf-8", newline="\n")
        exe = tmp / "t.exe"
        build = subprocess.run([cc, "-std=gnu11", "-Wall", "-O1", *flags, *[str(tmp / s) for s in sources], "-o", str(exe)],
                               text=True, capture_output=True)
        test.assertEqual(build.returncode, 0, build.stderr)
        run = subprocess.run([str(exe)], text=True, capture_output=True, timeout=60)
        test.assertEqual(run.returncode, 0, run.stdout + run.stderr)


TEXT_SPEED_FIXTURE = r'''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); exit(1); } } while (0)
typedef struct { uint64_t x[32]; uint64_t vreg[32][2]; } Ctx;
static uint64_t pane_seen;   /* (the text size hook: host/oot_text_size.c, given the LetterAnimControl) */
static void hos_oot_text_pane(Ctx *c, uint64_t anim) { (void)c; pane_seen = anim; }
static inline void a64_vset64(uint64_t *d, uint64_t v) { d[0] = v; d[1] = 0; }
volatile float hos_text_scale = 1.0f;
@TEXT_SCALE@
static float step(Ctx *c, float dt) {
    uint32_t u;
    memcpy(&u, &dt, 4);
    c->vreg[0][0] = 0xabcd000000000000ull | u, c->vreg[0][1] = 7;
    c->x[19] = 0x1234;
@SNIPPET@    float r;
    memcpy(&r, c->vreg[0], 4);
    return r;
}
int main(void) {
    Ctx c;
    CHECK(text_scale(NULL, 0) == 1.0f && text_scale(NULL, 1) == 2.0f && text_scale(NULL, 2) == 4.0f);
    CHECK(text_scale(NULL, 3) >= 1e5f);           /* Instant: a page in one step */
    CHECK(text_scale("0", 3) == 1.0f);            /* HOS_TEXT_SPEED wins over the panel */
    CHECK(text_scale("", 1) == 2.0f);
    hos_text_scale = text_scale(NULL, 0);
    CHECK(step(&c, 0.5f) == 0.5f && c.vreg[0][1] == 7 && c.vreg[0][0] >> 48 == 0xabcd);   /* Normal: the register untouched */
    hos_text_scale = text_scale(NULL, 2);
    CHECK(step(&c, 0.5f) == 2.0f && c.vreg[0][1] == 0);
    CHECK(pane_seen == 0x1234);   /* the text size hook gets x19 */
    return 0;
}
'''

TEXT_SIZE_HEAD = r'''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); exit(1); } } while (0)
typedef struct { int unused; } Ctx;
enum { AKYNO_OPT_TEXT_SIZE = 81 };
#define BASE 0x10000000ull
static unsigned char mem[0x40000];
static int writes, menu = 0;
static uint64_t recomp_load64(Ctx *c, uint64_t a) { uint64_t v; (void)c; memcpy(&v, mem + (a - BASE), 8); return v; }
static uint64_t recomp_load32(Ctx *c, uint64_t a) { uint32_t v; (void)c; memcpy(&v, mem + (a - BASE), 4); return v; }
static void recomp_store32(Ctx *c, uint64_t a, uint32_t v) { (void)c; memcpy(mem + (a - BASE), &v, 4); writes++; }
int rx_option(int id, int otherwise) { return id == AKYNO_OPT_TEXT_SIZE ? menu : otherwise; }
static int logged;
static void hos_log(const char *fmt, ...) { (void)fmt; logged++; }
'''

TEXT_SIZE_MAIN = r'''
static void put64(uint64_t a, uint64_t v) { memcpy(mem + (a - BASE), &v, 8); }
static void putf(uint64_t a, float v) { memcpy(mem + (a - BASE), &v, 4); }
static float getf(uint64_t a) { float v; memcpy(&v, mem + (a - BASE), 4); return v; }
/* a control at anim, its wrapper and pane after it, the game's scale g */
static uint64_t pane_at(uint64_t anim, float g) {
    const uint64_t wrapper = anim + 0x100, pane = anim + 0x200;
    put64(anim + 0x28, wrapper), put64(wrapper + 8, pane), putf(wrapper + 0x28, g), putf(wrapper + 0x38, g);
    return wrapper;
}
static int close_to(float a, float b) { return a > b - 1e-5f && a < b + 1e-5f; }
int main(void) {
    Ctx c;
    const uint64_t anim = BASE + 0x1000, w = pane_at(anim, 0.8f);
    hos_oot_text_pane(&c, anim);   /* Original: nothing written */
    CHECK(writes == 0 && getf(w + 0x28) == 0.8f && getf(w + 0x38) == 0.8f);
    menu = 4;   /* 175%: both fields, once, from the game's value */
    hos_oot_text_pane(&c, anim);
    CHECK(close_to(getf(w + 0x28), 1.4f) && close_to(getf(w + 0x38), 1.4f) && logged == 1);
    const int after = writes;
    hos_oot_text_pane(&c, anim);
    hos_oot_text_pane(&c, anim);
    CHECK(writes == after && close_to(getf(w + 0x28), 1.4f));   /* not again on the next steps */
    putf(w + 0x28, 0.5f);   /* the game writes its own value again */
    hos_oot_text_pane(&c, anim);
    CHECK(close_to(getf(w + 0x28), 0.875f) && close_to(getf(w + 0x38), 1.4f));
    menu = 2;   /* another choice: from the game's value, not the scaled one */
    hos_oot_text_pane(&c, anim);
    CHECK(close_to(getf(w + 0x28), 0.625f) && close_to(getf(w + 0x38), 1.0f));
    menu = 0;   /* back to Original: the game's own values */
    hos_oot_text_pane(&c, anim);
    CHECK(getf(w + 0x28) == 0.5f && getf(w + 0x38) == 0.8f);
    menu = 99;   /* out of range: Original */
    hos_oot_text_pane(&c, anim);
    CHECK(getf(w + 0x28) == 0.5f);
    menu = 3;   /* no control, no wrapper, no pane: nothing read past them, nothing written */
    writes = 0;
    hos_oot_text_pane(&c, 0);
    put64(BASE + 0x9000 + 0x28, 0);
    hos_oot_text_pane(&c, BASE + 0x9000);
    const uint64_t bare = pane_at(BASE + 0xa000, 0.8f);
    put64(bare + 8, 0);
    hos_oot_text_pane(&c, BASE + 0xa000);
    CHECK(writes == 0 && getf(bare + 0x28) == 0.8f);
    /* more panes than the host keeps: each new one is still scaled, and the one on screen keeps its own value */
    for (int i = 0; i < 200; i++) {
        const uint64_t a = BASE + 0x10000 + (uint64_t)i * 0x300, wi = pane_at(a, 0.8f);
        hos_oot_text_pane(&c, a);
        hos_oot_text_pane(&c, anim);
        CHECK(close_to(getf(wi + 0x28), 1.2f) && close_to(getf(w + 0x38), 1.2f));
    }
    hos_oot_text_pane(&c, anim);
    CHECK(close_to(getf(w + 0x38), 1.2f));
    return 0;
}
'''

MOUSE_HOS_H = r'''
#pragma once
#include <stdint.h>
#include <stddef.h>
extern uint8_t *fake_heap;
#define HOS_HEAP_BASE 0x1000000000ULL
#define GP(a) ((void *)(fake_heap + ((uint64_t)(a) - HOS_HEAP_BASE)))
void hos_log(const char *fmt, ...);
int64_t hos_now_ns(void);
'''

MOUSE_FIXTURE = r'''
#include "hos.h"
#include "../gpu/vk/menu_option_ids.h"
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
uint8_t *fake_heap;
double hos_mouse_sens = 1.0;
volatile int hos_mouse_pointing = 0;
static int64_t clock_ns = 1000000000LL;
void hos_log(const char *fmt, ...) { va_list a; va_start(a, fmt); vfprintf(stderr, fmt, a); va_end(a); fputc(10, stderr); }
int64_t hos_now_ns(void) { return clock_ns; }
static int32_t move_x, move_y;
static int captured = 1, menu_invert, menu_native = 1, menu_centering;
int rx_option(int id, int otherwise) {
    return id == AKYNO_OPT_MOUSE_INVERT ? menu_invert : id == AKYNO_OPT_MOUSE_NATIVE ? menu_native :
           id == AKYNO_OPT_CAM_NO_CENTERING ? menu_centering : otherwise;
}
int hos_mouse_take(int32_t *dx, int32_t *dy) { *dx = move_x, *dy = move_y; move_x = move_y = 0; return captured; }
void hos_mouse_give_back(int32_t dx, int32_t dy) { move_x += dx, move_y += dy; }
int hos_mouse_native(void);
void hos_mouse_camera(uint64_t camera);
int hos_disable_camera_centering(void);
static const uint64_t CAM = HOS_HEAP_BASE + 10 * 4096 + 0x40, OTHER = HOS_HEAP_BASE + 20 * 4096;
static float getf(uint64_t a) { float f; memcpy(&f, GP(a), 4); return f; }
static void putf(uint64_t a, float f) { memcpy(GP(a), &f, 4); }
static int fails;
#define PITCH (CAM + 0x18c)
#define YAW (CAM + 0x1a4)
static void state(uint32_t v) { memcpy(GP(CAM + 0x204), &v, 4); }
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s (pitch %g yaw %g)\n", __LINE__, #c, getf(PITCH), getf(YAW)); fails++; } } while (0)
static int close_to(float a, float b) { return fabsf(a - b) < 1e-3f; }
static void frame(int32_t dx, int32_t dy) { move_x += dx, move_y += dy; clock_ns += 16666667; hos_mouse_camera(CAM); }
int main(void) {
    fake_heap = (uint8_t *)calloc(64, 4096);
    putf(CAM + 0x178, -85), putf(CAM + 0x17c, 89);
    putf(PITCH, 10), putf(YAW, 30);
    state(4);   /* turned by the player */
    move_x = 5, move_y = 3;
    CHECK(hos_mouse_native() == -1);   /* no camera has run yet: the stick takes it */
    move_x = move_y = 0;
    frame(10, 4);
    CHECK(close_to(getf(YAW), 29.0f) && close_to(getf(PITCH), 10.4f));   /* right: yaw falls; down: pitch rises */
    move_x = 3;
    CHECK(hos_mouse_native() == 1 && move_x == 3);   /* the camera's now: the motion stays for it */
    frame(-3, 0);
    frame(0, 100000);
    CHECK(close_to(getf(PITCH), 89.0f));   /* kept within the limits */
    frame(0, -100000);
    CHECK(close_to(getf(PITCH), -85.0f));
    putf(YAW, -179.5f);
    frame(10, 0);
    CHECK(close_to(getf(YAW), 179.5f));   /* wrapped */
    putf(PITCH, 0);
    menu_invert = 1;   /* the panel's Invert mouse vertical: down tilts up */
    frame(0, 10);
    CHECK(close_to(getf(PITCH), -1.0f));
    menu_invert = 0;
    putf(OTHER + 0x18c, NAN);   /* (no limits, no angles: not a camera) */
    move_x = 50;
    hos_mouse_camera(OTHER);
    CHECK(move_x == 50 && isnan(getf(OTHER + 0x18c)));
    move_x = 0;
    menu_native = 0;   /* the panel's Mouse camera off: the hook does nothing */
    putf(YAW, 0);
    frame(10, 0);
    CHECK(close_to(getf(YAW), 0.0f));
    move_x = 0;
    menu_native = 1;
    frame(0, 0);
    captured = 0;
    CHECK(hos_mouse_native() == 0);   /* not captured: nothing */
    captured = 1;
    clock_ns += 200000000LL;   /* no camera for 200 ms (the pause menu): the stick again */
    CHECK(hos_mouse_native() == -1);
    /* aiming in first person (the slingshot): the camera keeps updating, state 0, another draws: the stick takes it */
    state(4);
    frame(0, 0);
    state(0);
    putf(YAW, 0);
    frame(10, 0);
    CHECK(close_to(getf(YAW), 0.0f) && move_x == 10);
    CHECK(hos_mouse_native() == -1);   /* at once, not 150 ms later */
    move_x = 0;
    state(3);   /* following Link again: the mouse turns it */
    frame(10, 0);
    CHECK(close_to(getf(YAW), -1.0f));
    CHECK(hos_mouse_native() == 1);
    /* (this base) the ability wheel open: the motion is the stick's at once, the camera's angles as they were */
    hos_mouse_pointing = 1;
    frame(10, 0);
    CHECK(close_to(getf(YAW), -1.0f) && move_x == 10 && hos_mouse_native() == -1);
    hos_mouse_pointing = 0;
    move_x = 0;
    frame(10, 0);
    CHECK(close_to(getf(YAW), -2.0f) && hos_mouse_native() == 1);
    CHECK(hos_disable_camera_centering() == 0);
    menu_centering = 1;
    CHECK(hos_disable_camera_centering() == 1);
    return fails != 0;
}
'''


class HostFiles(unittest.TestCase):
    def test_text_speed_scales_only_when_asked(self):
        snippet = patches.TEXT_ADD
        self.assertEqual(snippet.count(patches.TEXT_MARK), 1)
        fixture = (TEXT_SPEED_FIXTURE.replace("@TEXT_SCALE@", block(source("host/nn_vi.c"), "static float text_scale("))
                   .replace("@SNIPPET@", snippet))
        compile_and_run(self, {"t.c": fixture}, ["t.c"], ["-Wextra", "-Werror"])

    def test_text_size_scales_from_the_games_own_value(self):
        host = source("host/oot_text_size.c")
        self.assertIn("void hos_oot_text_pane(Ctx *c, uint64_t anim)", host)
        self.assertIn("extern void hos_oot_text_pane(Ctx *c, uint64_t anim);", patches.TEXT_DECL)
        self.assertIn("rx_option(AKYNO_OPT_TEXT_SIZE, 0)", host)
        self.assertIn('getenv("HOS_TEXT_SIZE")', host)
        ids = source("gpu/vk/menu_option_ids.h")
        order = re.search(r"enum \{(.*?)\};", ids, re.S).group(1)
        names = re.findall(r"\b(AKYNO_OPT_\w+)", order)
        self.assertEqual(64 + names.index("AKYNO_OPT_TEXT_SIZE"), 81)   # (the fixture's stand-in value)
        body = "".join(line for line in host.splitlines(keepends=True) if not line.startswith("#include"))
        body = body.replace("int rx_option(int id, int otherwise);\n", "", 1)
        compile_and_run(self, {"t.c": TEXT_SIZE_HEAD + body + TEXT_SIZE_MAIN}, ["t.c"], ["-Wextra", "-Werror"])

    def test_mouse_native_turns_the_player_camera(self):
        if sys.platform != "win32":
            self.skipTest("mouse_native.c is compiled against windows.h here")
        files = {"host/hos.h": MOUSE_HOS_H, "host/t.c": MOUSE_FIXTURE, "host/mouse_native.c": source("host/mouse_native.c"),
                 "gpu/vk/menu_option_ids.h": source("gpu/vk/menu_option_ids.h")}
        compile_and_run(self, files, ["host/t.c", "host/mouse_native.c"])


class PanelRows(unittest.TestCase):
    def test_rows_ids_and_readers(self):
        menu = source("gpu/vk/vk_menu.cpp")
        for row in ('{"Text speed", "Velocidade do texto", &opts.text_speed, 0, 3, 1, tx_text_speed,',
                    '{"Text size", "Tamanho do texto", &opts.text_size, 0, 4, 1, tx_text_size,',
                    '{"Mouse camera", "Câmera do mouse", &opts.mouse_native, 0, 1, 1, tx_mousecam,',
                    '{"Disable camera centering", "Desativar centralização da câmera", &opts.disable_camera_centering, 0, 1, 1, tx_onoff,'):
            self.assertIn(row, menu)
        game = re.search(r"constexpr Setting game_rows\[\] = \{([^}]+)\}", menu).group(1)
        pad = re.search(r"constexpr Setting pad_rows\[\] = \{([^}]+)\}", menu).group(1)
        self.assertIn("TextSpeed, TextSize", game)
        self.assertIn("MouseCam", pad)
        self.assertIn("CamNoCenter", pad)
        restart = re.search(r"constexpr Setting restart_rows\[\] = \{([^}]+)\}", menu).group(1)
        for name in ("TextSpeed", "TextSize", "MouseCam", "CamNoCenter"):
            self.assertNotIn(name, restart)   # (at once)
        replay = source("gpu/vk/vk_replay.cpp")
        for line in ("case AKYNO_OPT_TEXT_SPEED: return opts.text_speed;", "case AKYNO_OPT_TEXT_SIZE: return opts.text_size;",
                     "case AKYNO_OPT_MOUSE_NATIVE: return opts.mouse_native;",
                     "case AKYNO_OPT_CAM_NO_CENTERING: return opts.disable_camera_centering;"):
            self.assertIn(line, replay)
        header = source("gpu/vk/vk_menu.h")
        for line in ("int text_speed = 0;", "int text_size = 0;", "int mouse_native = 0;", "int disable_camera_centering = 0;"):
            self.assertIn(line, header)   # (off: the game as it was)
        self.assertNotIn("AKYNO_OPT_", source("gpu/vk/vk_api.h"))

    def test_host_reads_the_rows(self):
        vi = source("host/nn_vi.c")
        step = block(vi, "static void realtime_step(")
        self.assertIn("const float scale = text_scale(env, rx_option(AKYNO_OPT_TEXT_SPEED, 0));", step)
        self.assertIn("hos_text_scale = scale;", step)
        self.assertLess(step.index("hos_text_scale = scale;"), step.index("if (!mod) return;"))   # (set every present)
        hid = source("host/nn_hid.c")
        self.assertIn("rx_option(AKYNO_OPT_MOUSE_NATIVE, 0)", hid)
        self.assertIn("int captured = 0, as_stick = !native || pointing;", hid)
        native = source("host/mouse_native.c")
        self.assertIn("rx_option(AKYNO_OPT_MOUSE_NATIVE, 0)", native)
        self.assertIn("rx_option(AKYNO_OPT_CAM_NO_CENTERING, 0)", native)
        self.assertNotIn("rx_option(6, 0)", native)
        self.assertIn("void hos_mouse_give_back(int32_t dx, int32_t dy)", source("host/display.c"))

    def test_earlier_ids_kept(self):
        ids = source("gpu/vk/menu_option_ids.h")
        order = re.findall(r"\b(AKYNO_OPT_\w+)", re.search(r"enum \{(.*?)\};", ids, re.S).group(1))
        self.assertEqual(order.index("AKYNO_OPT_MOUSE_SENS"), 8)    # (72)
        self.assertEqual(order.index("AKYNO_OPT_MIC"), 15)          # (79)
        self.assertEqual(order[16:20], ["AKYNO_OPT_TEXT_SPEED", "AKYNO_OPT_TEXT_SIZE", "AKYNO_OPT_MOUSE_NATIVE",
                                        "AKYNO_OPT_CAM_NO_CENTERING"])


if __name__ == "__main__":
    unittest.main()
