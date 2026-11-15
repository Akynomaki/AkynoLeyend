"""Select a generic renderer only when source, dependency and binary hashes agree."""
import hashlib
import json
from pathlib import Path
from .files import sha256


def renderer_identity(root: Path, deps: Path) -> str:
    digest = hashlib.sha256()
    for label, folder in (("gpu", root / "gpu"), ("fsr-sdk", root / "third_party" / "amd-fsr-sdk"),
                          ("vulkan", deps / "vulkan"),
                          ("spirv", deps / "spirv"), ("vma", deps / "vma")):
        for path in sorted(folder.rglob("*"), key=lambda p: p.relative_to(folder).as_posix()):
            if path.is_file() and path.suffix in {".c", ".cpp", ".h", ".hpp", ".inc"}:
                digest.update((label + "/" + path.relative_to(folder).as_posix()).encode() + b"\0")
                digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    for name in ("nx2/build.py", "akynoleyend/prebuilt.py", "akynoleyend/build_support.py",
                 "third_party/a64-kit/tools/toolchain.py", "profiles/shader-cache-compatible.json"):
        path = root / name
        if path.is_file():
            digest.update(name.encode() + b"\0")
            digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def renderer_prebuilt(root: Path, deps: Path, directory: Path, environment, report=print):
    if environment.get("OCARINA_BUILD_RENDERER") == "1" or environment.get("RX_VK_ONLY"):
        return None
    config = {"target": environment.get("OCARINA_TARGET"),
              "march": environment.get("RX_MARCH", "x86-64-v3"),
              "release": environment.get("RX_RELEASE", "0")}
    manifest, binary = directory / "renderer.json", directory / "AkynoLeyend.dll"
    if not manifest.is_file() or not binary.is_file():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        match = (data.get("schema") == 1 and data.get("config") == config
                 and data.get("source_sha256") == renderer_identity(root, deps)
                 and data.get("binary_sha256") == sha256(binary))
    except (OSError, ValueError, TypeError, AttributeError):
        match = False
    if not match:
        report("Renderizador pronto nao corresponde aos fontes/configuracao; compilando dos fontes.")
        return None
    report("Renderizador Vulkan pronto: fontes, dependencias e hash conferidos.")
    return binary
