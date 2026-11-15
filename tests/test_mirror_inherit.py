"""Compile and run the rule for which pages a remade pool's mirror takes from a retired one (gpu/vk/mirror_inherit.h; no game/GPU)."""
import argparse
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_source():
    """mirror_make still copies the retired mirrors through the rule, and the switch back is still read"""
    src = (ROOT / "gpu/vk/vk_memory.cpp").read_text(encoding="utf-8")
    for needle in ('#include "mirror_inherit.h"', "const uint32_t synced = r.synced_gen;",
                   "mirror_inherit::runs(a, b, r.lo, p->lo, kPageShift", 'getenv("RX_VK_INHERIT_ALL")',
                   "region_gen[region] <= synced", "page_gen(page) <= synced",
                   # (AkynoLeyend: its mirror_sync has no bare-entry protection, so the rule is the page generations alone)
                   # (synced in this submission: synced_gen is behind the GPU's writes of its earlier segments)
                   "if (inherit_all || r.synced_epoch == mirror_epoch)"):
        if needle not in src:
            raise SystemExit("vk_memory.cpp no longer has: " + needle)
    make = src[src.index("bool mirror_make(Pool& pool) {"):]
    make = make[:make.index("\n}\n")]
    if "const VkBufferCopy part{a - r.lo, a - p->lo, b - a};" in make:
        raise SystemExit("mirror_make copies a retired mirror's whole part again")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    check_source()
    with tempfile.TemporaryDirectory(prefix="mirror-inherit-") as tmp:
        exe = Path(tmp) / "mirror-inherit"
        subprocess.run([args.cxx, "-std=c++20", "-static", "-Wall", "-Wextra", "-Werror",
                        str(ROOT / "tests/test_mirror_inherit.cpp"), "-o", str(exe)], check=True)
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
