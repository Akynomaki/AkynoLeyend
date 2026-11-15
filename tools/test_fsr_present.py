"""Execute production present functions and embedded shaders using a Vulkan ICD.

Example on Linux with software Vulkan:
  VK_ICD_FILENAMES=/path/to/lvp.json python3 tools/test_fsr_present.py
No game data is read. Requires a C++20 compiler, Vulkan headers and loader.
"""
import argparse
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(source, marker):
    start = source.index(marker)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def production_source():
    source = (ROOT / "gpu/vk/vk_framegen.cpp").read_text()
    declarations = source[source.index("constexpr int kMaxMult"):source.index("int64_t now_ns()")]
    texture = (ROOT / "gpu/vk/vk_texture.cpp").read_text()
    state_start = texture.index("// AkynoLeyend: conservative adjacent-barrier reuse")
    declarations += texture[state_start:texture.index("void full_barrier(", state_start)]
    markers = ["int multiplier()", "void drop_pipe(", "bool make_pipe(", "bool init_samplers()",
               "bool init_scale()", "bool init()", "bool make_img(", "void drop_img(",
               "void to_general(", "void pass(", "VkImage framegen_scale("]
    functions = [function((ROOT / "gpu/vk/vk_texture.cpp").read_text(), "void full_barrier(")]
    functions += [function(source, marker) for marker in markers]
    functions.append(function((ROOT / "gpu/vk/vk_replay.cpp").read_text(), "void blit_crop("))
    return declarations + "\n\n" + "\n\n".join(functions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default=shutil.which("c++"))
    parser.add_argument("--vulkan-include", type=Path, default=ROOT / "ferramentas/deps/vulkan/include")
    parser.add_argument("--vulkan-loader", default="-l:libvulkan.so.1")
    args = parser.parse_args()
    if not args.cxx:
        parser.error("C++ compiler unavailable")
    with tempfile.TemporaryDirectory(prefix="akyno-fsr-present-") as directory:
        path = Path(directory)
        (path / "fsr_present_production.inc").write_text(production_source())
        tracked = (ROOT / "gpu/vk/vk_work.h").read_text()
        names = re.findall(r"^#define (vk\w+)\(", tracked, re.M)
        (path / "fsr_test_work.inc").write_text(
            "namespace vkx {\n" + "\n".join("using ::" + name + ";" for name in names)
            + '\n}\n#include "vk_work.h"\n')
        binary = path / "present-check"
        subprocess.run([args.cxx, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-Wno-missing-field-initializers", "-I" + str(args.vulkan_include),
                        "-I" + str(ROOT / "gpu/vk"), "-I" + str(path),
                        str(ROOT / "tests/native/test_fsr_present.cpp"), args.vulkan_loader,
                        "-o", str(binary)], check=True, timeout=120)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=120)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        result.check_returncode()
        if "Validation Error:" in result.stdout + result.stderr or "SYNC-HAZARD-" in result.stdout + result.stderr:
            raise SystemExit("Vulkan validation reported an invalid command")


if __name__ == "__main__":
    main()
