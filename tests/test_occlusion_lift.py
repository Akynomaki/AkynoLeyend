"""Exercise the bundled lifter, not a stand-in with a fabricated ``after`` API."""

import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import kit  # noqa: E402,F401
import a64_lift  # noqa: E402
import oot_occlusion  # noqa: E402

RET = 0xD65F03C0
LOAD = "c->x[8] = *(const unsigned char *)(uintptr_t)c->x[0];"


class OcclusionImage:
    """Six tiny synthetic functions plus an identical load outside the patch sites."""

    hooks = {}

    def __init__(self):
        self.entries = {oot_occlusion.MAIN + off for off in oot_occlusion.OFFSETS}
        self.entries.add(oot_occlusion.MAIN)
        self.words = {
            pc + delta: word
            for pc in self.entries
            for delta, word in ((0, oot_occlusion.LDRB_W8_X0), (4, RET))
        }

    def word(self, pc):
        return self.words[pc]

    def in_code(self, pc):
        return pc in self.words


def install(lifter, image):
    with contextlib.redirect_stdout(io.StringIO()):
        return oot_occlusion.install(lifter, image)


class OcclusionLiftTests(unittest.TestCase):
    def test_real_lifter_emits_all_six_patches_after_the_validated_loads(self):
        image = OcclusionImage()
        lifter = a64_lift.Lifter(image)
        self.assertEqual(install(lifter, image), 6)
        lifter.discover()
        for pc in sorted(image.entries):
            with self.subTest(pc=hex(pc)):
                source, _ = lifter.emit_function(pc, {oot_occlusion.LDRB_W8_X0: (LOAD, 0)})
                if pc == oot_occlusion.MAIN:
                    self.assertNotIn("hos_occlusion_off", source)
                else:
                    self.assertEqual(source.count("extern volatile int hos_occlusion_off"), 1)
                    self.assertLess(source.index(LOAD), source.index("if (hos_occlusion_off)"))

    def test_different_or_unreadable_instructions_are_left_untouched(self):
        image = OcclusionImage()
        sites = [oot_occlusion.MAIN + off for off in oot_occlusion.OFFSETS]
        image.words[sites[0]] = 0xD503201F  # NOP: unsupported original word.
        del image.words[sites[1]]
        lifter = a64_lift.Lifter(image)
        self.assertEqual(install(lifter, image), 4)
        self.assertNotIn(sites[0], lifter.after)
        self.assertNotIn(sites[1], lifter.after)

    def test_existing_post_instruction_code_is_preserved_in_order(self):
        image = OcclusionImage()
        lifter = a64_lift.Lifter(image)
        pc = oot_occlusion.MAIN + oot_occlusion.OFFSETS[0]
        lifter.after[pc] = "c->x[7] = 42;"
        self.assertEqual(install(lifter, image), 6)
        lifter.discover()
        source, _ = lifter.emit_function(pc, {oot_occlusion.LDRB_W8_X0: (LOAD, 0)})
        self.assertLess(source.index(LOAD), source.index("c->x[7] = 42;"))
        self.assertLess(source.index("c->x[7] = 42;"), source.index("if (hos_occlusion_off)"))

    def test_generated_c_executes_enabled_and_disabled_with_local_registers(self):
        compiler = shutil.which("cc")
        if compiler is None:
            self.skipTest("C compiler unavailable")
        image = OcclusionImage()
        pc = oot_occlusion.MAIN + oot_occlusion.OFFSETS[0]
        for local in ("0", "31"):
            with self.subTest(local_registers=local), patch.dict(os.environ, {"A64_LOCAL_REGS": local}):
                lifter = a64_lift.Lifter(image)
                install(lifter, image)
                # Also verify that the register analysis sees writes made only by a hook.
                lifter.after[pc] += "\nc->x[7] = 42;"
                lifter.discover()
                sources = [lifter.emit_function(entry, {oot_occlusion.LDRB_W8_X0: (LOAD, 0)})[0]
                           for entry in sorted(image.entries)]
                code = """#include <assert.h>
#include <stdint.h>
#define A64_NOESC
typedef struct { uint64_t x[32]; } Ctx;
volatile int hos_occlusion_off;
""" + "\n".join(sources)
                code += "int main(void) { unsigned char value=173; Ctx c={0}; c.x[0]=(uintptr_t)&value;\n"
                for enabled in (0, 1):
                    code += f"hos_occlusion_off={enabled};\n"
                    for entry in sorted(image.entries):
                        expected = 0 if enabled and entry != oot_occlusion.MAIN else 173
                        code += f"c.x[8]=99; f_{entry:08x}(&c); assert(c.x[8]=={expected});\n"
                    code += f"f_{pc:08x}(&c); assert(c.x[7]==42);\n"
                code += "return 0; }\n"
                with tempfile.TemporaryDirectory() as directory:
                    folder = Path(directory)
                    source = folder / "occlusion.c"
                    source.write_text(code, encoding="utf-8")
                    binary = folder / "occlusion"
                    result = subprocess.run([compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                                             str(source), "-o", str(binary)], capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
