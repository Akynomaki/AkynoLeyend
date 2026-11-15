"""Verify the packaged toolchain before extracting or compiling a large game."""

import importlib.util
from importlib import import_module
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from .environment import clean_environment
from .errors import ProjectError

REQUIRED = (
    "llvm/bin/clang.exe",
    "llvm/bin/clang++.exe",
    "llvm/bin/ld.lld.exe",
    "deps/vulkan/include/vulkan/vulkan.h",
    "deps/vma/include/vk_mem_alloc.h",
    "deps/spirv/include/spirv/unified1/spirv.hpp",
    "deps/ffmpeg/include/libavcodec/avcodec.h",
    "deps/ffmpeg/include/libswscale/swscale.h",
    "deps/ffmpeg/lib/libavcodec.a",
    "deps/ffmpeg/lib/libavutil.a",
    "deps/ffmpeg/lib/libswscale.a",
)
PYTHON_MODULES = ("numpy", "lz4", "capstone", "unicorn", "zstandard")


def build_environment(tools: Path, parent: dict[str, str] | None = None) -> dict[str, str]:
    result = clean_environment(os.environ if parent is None else parent)
    result.update(
        {
            "OCARINA_LLVM_ROOT": str((tools / "llvm").resolve()),
            "OCARINA_DEPS": str((tools / "deps").resolve()),
            "OCARINA_TARGET": "windows-gnu",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    result["PATH"] = str(tools / "llvm/bin") + os.pathsep + result.get("PATH", "")
    return result


def inspect_tools(tools: Path, require_windows: bool = True) -> list[str]:
    failures = []
    if require_windows and (os.name != "nt" or struct.calcsize("P") != 8):
        failures.append("A compilacao e a execucao do jogo requerem Windows x64.")
    if sys.version_info < (3, 12):
        failures.append("Use Python 3.12 ou mais recente, de 64 bits.")
    failures.extend(
        f"Ferramenta/dependencia ausente: {tools / relative}"
        for relative in REQUIRED
        if not (tools / relative).is_file()
    )
    for module in PYTHON_MODULES:
        if importlib.util.find_spec(module) is None:
            failures.append(
                f"Modulo Python ausente: {module}. Use o Python incluido ou instale requirements.txt."
            )
            continue
        try:
            import_module(module)
        except (ImportError, OSError) as error:
            failures.append(f"O modulo Python {module} existe, mas nao carregou: {error}")
    return failures


def require_tools(tools: Path) -> dict[str, str]:
    failures = inspect_tools(tools)
    if failures:
        raise ProjectError("\n".join(failures))
    environment = build_environment(tools)
    compiler = tools / "llvm/bin/clang.exe"
    with tempfile.TemporaryDirectory(prefix="akynoleyend-check-") as directory:
        folder = Path(directory)
        source, executable = folder / "probe.c", folder / "probe.exe"
        source.write_text(
            "#include <windows.h>\nint main(void) { return GetCurrentProcessId() == 0; }\n"
        )
        command = [
            str(compiler),
            "--target=x86_64-w64-windows-gnu",
            "-fuse-ld=lld",
            "-static",
            str(source),
            "-o",
            str(executable),
        ]
        result = subprocess.run(
            command, env=environment, capture_output=True, text=True, errors="replace"
        )
        if result.returncode:
            raise ProjectError(
                "A toolchain nao conseguiu compilar e ligar o teste Windows:\n"
                + result.stderr[-3000:]
            )
    return environment
