"""Compile and run the write-back shadows' rules near the VRAM limit (gpu/vk/vram_pressure.h; no game/GPU required), and check
that vk_memory.cpp still judges the shadows by what is really allocated, with the switch back to the driver's count alone."""
import argparse
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "g++"]

ROOT = Path(__file__).resolve().parents[1]


def check_source():
    src = (ROOT / "gpu/vk/vk_memory.cpp").read_text(encoding="utf-8")
    for needle in ('#include "vram_pressure.h"', 'getenv("RX_VK_SHADOW_RAW")',
                   "vram_pressure::shadow_fits(n, used, allowed, block_free)",
                   "vram_pressure::shadows_go(used, allowed, block_free)"):
        if needle not in src:
            raise SystemExit("vk_memory.cpp no longer has: " + needle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    check_source()
    with tempfile.TemporaryDirectory(prefix="vram-pressure-") as tmp:
        exe = Path(tmp) / "vram-pressure"
        subprocess.run([args.cxx, "-std=c++20", "-static", "-Wall", "-Wextra", "-Werror",
                        str(ROOT / "tests/test_vram_pressure.cpp"), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)



class NativeRun(__import__("unittest").TestCase):
    """The suite's run (unittest discover): the same main() with the SDK's own compiler"""
    def test_native(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from tests.native_tools import native_cxx
        cxx = native_cxx()
        if not cxx:
            self.skipTest("no native C++ compiler")
        argv = sys.argv
        sys.argv = [__file__, "--cxx", cxx]
        try:
            main()
        finally:
            sys.argv = argv

if __name__ == "__main__":
    main()
