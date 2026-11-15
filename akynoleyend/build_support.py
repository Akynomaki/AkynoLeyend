"""Shared compile-cache and linker rules, independent of the lifted game."""

import functools
import hashlib
import json
import os
import re
from pathlib import Path


def require_cached_game_objects(jobs, cache_folder):
    """A maintenance update must never start compiling missing translated game units."""
    from .errors import ProjectError
    for cc, source, output, flags, dependencies in jobs:
        key = object_key(cc, source, flags, dependencies)
        stamp = Path(str(output) + ".sha256")
        if Path(output).is_file() and stamp.is_file() and stamp.read_text() == key:
            continue
        if (Path(cache_folder) / (key + ".o")).is_file():
            continue
        raise ProjectError(
            "Cache da unidade traduzida ausente ou diferente: " + Path(source).name +
            ". A atualizacao foi interrompida antes de recompilar o jogo. "
            "Restaure a pasta work da instalacao correspondente ou use Criar."
        )


def shader_source_identity(vk: Path) -> tuple[str, str]:
    # Same order on Windows and POSIX: the registered fingerprints must not depend on the host OS.
    paths = sorted((p for name in ("eden", "sirit", "compat") for p in (vk/name).rglob("*") if p.is_file()),
                   key=lambda p: p.relative_to(vk).parts)
    paths += [vk/name for name in ("vk_shader.cpp", "vk_state.h", "vk_api.h", "vk_shader.h")]
    short, full = hashlib.sha1(), hashlib.sha256()
    for path in paths:
        data = path.relative_to(vk).as_posix().encode() + path.read_bytes().replace(b"\r\n", b"\n")
        short.update(data)
        full.update(data)
    return short.hexdigest()[:16], full.hexdigest()


def shader_cache_stamp(vk: Path, compatibility: Path | None = None) -> str:
    """Reuse only a registered exact source fingerprint, including the ABI header."""
    current, fingerprint = shader_source_identity(vk)
    path = compatibility or Path(__file__).resolve().parent.parent / "profiles/shader-cache-compatible.json"
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
        kept = registry.get("source_sets", {}).get(fingerprint, {}).get("stamp", "")
        if registry.get("schema") == 1 and isinstance(kept, str) and re.fullmatch(r"[0-9a-f]{16}", kept):
            return kept
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return current


@functools.lru_cache(maxsize=8)
def compiler_identity(compiler: str, modified_ns: int, size: int) -> str:
    del (
        modified_ns,
        size,
    )  # Included in the cache key; an updated compiler is hashed again.
    digest = hashlib.sha256()
    executable = Path(compiler).resolve()
    binaries = {executable}
    # llvm-mingw uses small driver wrappers: also identify the compiler they load.
    for pattern in ("clang-[0-9]*.exe", "libLLVM*.dll", "libclang-cpp.dll"):
        binaries.update(executable.parent.glob(pattern))
    for binary in sorted(binaries):
        digest.update(binary.name.encode())
        with binary.open("rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                digest.update(block)
    return digest.hexdigest()


def object_key(compiler: str, source: str, flags: list[str], dependencies: bytes) -> str:
    path = Path(compiler).resolve()
    stat = path.stat()
    digest = hashlib.sha256()
    digest.update(compiler_identity(str(path), stat.st_mtime_ns, stat.st_size).encode())
    digest.update(json.dumps(flags, ensure_ascii=True, separators=(",", ":")).encode())
    digest.update(Path(source).read_bytes())
    digest.update(dependencies)
    return digest.hexdigest()


def is_mingw() -> bool:
    return os.environ.get("OCARINA_TARGET") == "windows-gnu"


def link_options(map_file: str, stack: bool = False, windowed: bool = False) -> list[str]:
    if is_mingw():
        result = ["-Wl,-Map," + map_file]
        if stack:
            result.append("-Wl,--stack,8388608")
        if windowed:
            result.append("-mwindows")
        return result
    result = ["-Wl,/map:" + map_file]
    if stack:
        result.append("-Wl,/stack:8388608")
    if windowed:
        result.append("-Wl,/subsystem:windows,/entry:mainCRTStartup")
    return result


def video_libraries(root: str) -> list[str]:
    if is_mingw():
        base = ["-L" + str(Path(root) / "lib"), "-lavcodec", "-lswscale", "-lavutil"]
    else:
        base = [
            str(Path(root) / "lib" / (name + ".lib"))
            for name in ("avcodec", "swscale", "swresample", "avutil")
        ]
    return base + ["-lbcrypt", "-lmfplat", "-lmfuuid", "-lstrmiids", "-lole32"]
