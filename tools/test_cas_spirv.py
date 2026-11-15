"""Build the real IR/backend fixture and validate its generic SPIR-V (Linux developer check)."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default=shutil.which("clang++") or shutil.which("c++"))
    parser.add_argument("--spirv-val", required=True)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "work/cas-spv")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if not args.cxx:
        parser.error("C++ compiler unavailable")
    build = args.build_dir.absolute()
    build.mkdir(parents=True, exist_ok=True)
    vk = ROOT / "gpu/vk"
    folders = [vk / "eden/shader_recompiler" / folder for folder in ("backend/spirv", "frontend/ir", "ir_opt")]
    folders += [vk / "sirit/src"]
    sources = sorted(p for folder in folders for p in folder.rglob("*.cpp"))
    sources += [ROOT / "tests/native/test_cas_spirv.cpp"]
    include = [vk / "compat", ROOT / "gpu/compat", vk / "eden", ROOT / "gpu/third_party/suyu",
               vk / "sirit/include", vk / "sirit/src", ROOT / "ferramentas/deps/spirv/include"]
    driver = ["--driver-mode=g++", "--target=x86_64-linux-gnu", "--gcc-toolchain=/usr"] if "clang" in Path(args.cxx).name else []
    flags = driver + ["-std=c++20", "-O1", "-w", "-DNDEBUG", "-DMKWVK_INCLUDES=2", "-DVK_NO_PROTOTYPES"]
    flags += ["-I" + str(path) for path in include]
    identity = hashlib.sha256()
    for folder in include:
        for path in sorted(p for p in folder.rglob("*") if p.suffix in {".h", ".hpp", ".inc"}):
            identity.update(str(path).encode() + path.read_bytes())
    dependencies = identity.digest()

    def compile_source(item):
        index, source = item
        output = build / ("unit-%03d.o" % index)
        stamp = output.with_suffix(".key")
        key = hashlib.sha256(str(args.cxx).encode() + repr(flags).encode() + dependencies + source.read_bytes()).hexdigest()
        if not output.exists() or not stamp.exists() or stamp.read_text() != key:
            result = subprocess.run([args.cxx, *flags, "-c", str(source), "-o", str(output)], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(str(source) + "\n" + result.stdout + result.stderr)
            stamp.write_text(key)
        return output

    with ThreadPoolExecutor(max_workers=max(1, min(args.jobs, 8))) as executor:
        objects = list(executor.map(compile_source, enumerate(sources)))
    binary = build / "cas-check"
    subprocess.run([args.cxx, *driver, "-pthread", *(str(path) for path in objects), "-o", str(binary)], check=True)
    environment = os.environ.copy()
    for name in ("RX_VK_FOLLOW_STORES", "RX_VK_NO_FOLLOW", "RX_VK_GP_TEST"):
        environment.pop(name, None)
    for follow in (False, True):
        modules = build / ("modules-follow" if follow else "modules")
        if follow:
            environment["RX_VK_FOLLOW_STORES"] = "1"
        subprocess.run([str(binary), str(modules)], check=True, env=environment)
        for name in ("storage-cas.spv", "global-cas.spv", "tracked-cas.spv"):
            subprocess.run([args.spirv_val, "--target-env", "vulkan1.3", "--uniform-buffer-standard-layout", str(modules / name)], check=True)
    print("PASS: %d production units linked; six CAS modules validated with page-table writes off/on, including tracked global-to-storage; no shader/GPU execution" % len(objects))


if __name__ == "__main__":
    main()
