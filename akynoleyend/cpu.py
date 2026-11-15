"""(r13j) The CPU instructions this computer has, and the x86-64 level the game is compiled for on it.

The lifted game, the host and the renderer are C compiled on the player's own PC (nx2/build.py, -march=$RX_MARCH). Hookshot's
default is x86-64-v3 (AVX2, FMA, BMI1/2, LZCNT, MOVBE: Intel Haswell and AMD Zen on); on a CPU without those the game stops
at its first such instruction with 0xC000001D (STATUS_ILLEGAL_INSTRUCTION), before the game's first instruction runs.

Lichii and Fritchii (GPL-3.0) solve it for their releases with a generic build (x86-64 with SSE4.1 and CX16 required,
YUZU_BUILD_PRESET generic/v3/zen2/zen4/native in their CMakeLists.txt) and a JIT that picks instructions at run time. A static
recompilation has no JIT; but it is compiled on the PC that runs it, so the level is chosen here, from CPUID, before Criar:
x86-64-v3 where the CPU and Windows have all of it, else x86-64-v2, else x86-64 (always with CX16, which 64-bit Windows needs).

CPUID is read by a probe compiled with the packaged clang (as preflight.require_tools already compiles one), so the answer is
the processor's own, with XGETBV for whether Windows keeps the AVX registers."""

import functools
import json
import os
import subprocess
import tempfile
from pathlib import Path

ILLEGAL_INSTRUCTION_EXIT = 0xC000001D   # STATUS_ILLEGAL_INSTRUCTION
DEFAULT_MARCH = "x86-64-v3"             # what every build before r13j was compiled for (nx2/build.py's default)
MARCH_LEVELS = ("x86-64", "x86-64-v2", "x86-64-v3")

# x86-64-v2 and -v3 as the psABI defines them (clang's -march=x86-64-v2/-v3), plus what Windows must allow (os_avx).
V2 = ("cx16", "lahf", "popcnt", "sse3", "ssse3", "sse41", "sse42")
V3 = V2 + ("avx", "avx2", "bmi1", "bmi2", "f16c", "fma", "lzcnt", "movbe", "os_avx")
REQUIRED = {"x86-64": ("cx16",), "x86-64-v2": V2, "x86-64-v3": V3}
NAMES = {"avx": "AVX", "avx2": "AVX2", "bmi1": "BMI1", "bmi2": "BMI2", "f16c": "F16C", "fma": "FMA", "lzcnt": "LZCNT",
         "movbe": "MOVBE", "os_avx": "AVX ativado no Windows", "cx16": "CMPXCHG16B", "lahf": "LAHF/SAHF",
         "popcnt": "POPCNT", "sse3": "SSE3", "ssse3": "SSSE3", "sse41": "SSE4.1", "sse42": "SSE4.2"}

PROBE = r"""
#include <cpuid.h>
#include <stdio.h>
int main(void) {
    unsigned a = 0, b = 0, c = 0, d = 0, top = 0, ext = 0;
    unsigned c1 = 0, b7 = 0, ce = 0;
    int os_avx = 0;
    __get_cpuid(0, &top, &b, &c, &d);
    if (__get_cpuid(1, &a, &b, &c, &d)) c1 = c;
    if (c1 >> 27 & 1) {   /* OSXSAVE: Windows saves the extended registers; XCR0 bits 1 and 2: SSE and AVX state */
        unsigned lo, hi;
        __asm__ volatile("xgetbv" : "=a"(lo), "=d"(hi) : "c"(0));
        os_avx = (lo & 6) == 6;
    }
    if (top >= 7 && __get_cpuid_count(7, 0, &a, &b, &c, &d)) b7 = b;
    __get_cpuid(0x80000000u, &ext, &b, &c, &d);
    if (ext >= 0x80000001u && __get_cpuid(0x80000001u, &a, &b, &c, &d)) ce = c;
    printf("{\"sse3\": %u, \"ssse3\": %u, \"fma\": %u, \"cx16\": %u, \"sse41\": %u, \"sse42\": %u, \"movbe\": %u, "
           "\"popcnt\": %u, \"avx\": %u, \"f16c\": %u, \"os_avx\": %d, \"bmi1\": %u, \"avx2\": %u, \"bmi2\": %u, "
           "\"lahf\": %u, \"lzcnt\": %u}\n",
           c1 & 1, c1 >> 9 & 1, c1 >> 12 & 1, c1 >> 13 & 1, c1 >> 19 & 1, c1 >> 20 & 1, c1 >> 22 & 1, c1 >> 23 & 1,
           c1 >> 28 & 1, c1 >> 29 & 1, os_avx, b7 >> 3 & 1, b7 >> 5 & 1, b7 >> 8 & 1, ce & 1, ce >> 5 & 1);
    return 0;
}
"""


def missing(features: dict, march: str) -> list[str]:
    """What of `march` this CPU lacks, by NAMES; [] when it runs it."""
    return [NAMES[name] for name in REQUIRED.get(march, REQUIRED[DEFAULT_MARCH]) if not features.get(name)]


def supports(features: dict, march: str) -> bool:
    return not missing(features, march)


def choose_march(features: dict) -> str:
    """The highest level the CPU and Windows run, never above x86-64-v3 (what the project measures and ships)."""
    for march in reversed(MARCH_LEVELS):
        if supports(features, march):
            return march
    return "x86-64"


def build_march(manifest: dict) -> str:
    """The level a build was compiled for: builds before r13j recorded none and were all x86-64-v3."""
    march = manifest.get("march")
    return march if march in MARCH_LEVELS else DEFAULT_MARCH


@functools.lru_cache(maxsize=4)
def _probe(compiler: str) -> str | None:
    with tempfile.TemporaryDirectory(prefix="akynoleyend-cpu-") as directory:
        folder = Path(directory)
        source, executable = folder / "cpu.c", folder / "cpu.exe"
        source.write_text(PROBE, encoding="utf-8")
        # (no -march: the probe itself is baseline x86-64, so it runs on any CPU)
        command = [compiler, "--target=x86_64-w64-windows-gnu", "-fuse-ld=lld", "-static", "-O1",
                   str(source), "-o", str(executable)]
        try:
            built = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=120,
                                   env={**os.environ, "PATH": str(Path(compiler).parent) + os.pathsep + os.environ.get("PATH", "")})
            if built.returncode:
                return None
            ran = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        return ran.stdout if ran.returncode == 0 else None


def detect(tools: Path) -> dict | None:
    """{feature: bool} from this CPU's CPUID; None where the probe cannot be built or run (no check is made then)."""
    if os.name != "nt":
        return None
    compiler = Path(tools) / "llvm/bin/clang.exe"
    if not compiler.is_file():
        return None
    text = _probe(str(compiler.resolve()))
    if not text:
        return None
    try:
        values = json.loads(text)
    except ValueError:
        return None
    if not isinstance(values, dict):
        return None
    return {name: bool(values.get(name)) for name in NAMES}


PF_AVX_INSTRUCTIONS_AVAILABLE, PF_AVX2_INSTRUCTIONS_AVAILABLE = 39, 40


def windows_says_avx2() -> bool:
    """Windows' own answer (IsProcessorFeaturePresent), instant. True only where it says AVX and AVX2: every such CPU so far
    also has FMA, BMI1/2, LZCNT and MOVBE. False says nothing (a Windows before these flags answers False too): ask CPUID."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        present = ctypes.windll.kernel32.IsProcessorFeaturePresent
        return bool(present(PF_AVX_INSTRUCTIONS_AVAILABLE)) and bool(present(PF_AVX2_INSTRUCTIONS_AVAILABLE))
    except (OSError, AttributeError):
        return False


def launch_refusal(manifest: dict, tools: Path, cpu: str) -> str | None:
    """Before Jogar: the message when this CPU lacks what the build was compiled for; None when it runs it or is not known."""
    march = build_march(manifest)
    if march == DEFAULT_MARCH and windows_says_avx2():
        return None
    features = detect(tools)
    if features is None or supports(features, march):
        return None
    return unsupported_message(cpu, march, features)


def unsupported_message(cpu: str, march: str, features: dict) -> str:
    """Before Jogar: the build needs instructions this CPU lacks."""
    lacks = ", ".join(missing(features, march))
    return (f"Este jogo foi compilado para {march}, mas o processador deste PC ({cpu or 'desconhecido'}) nao tem: {lacks}. "
            "Ele fecharia na abertura com o codigo 0xC000001D (instrucao ilegal). Use Criar de novo nesta pasta: "
            f"a compilacao passa a usar {choose_march(features)}, o nivel que este processador executa. "
            "Saves e entrada sao preservados.")


def illegal_instruction_message(cpu: str, march: str, features: dict | None) -> str:
    """After a run that ended with 0xC000001D."""
    if features is not None and not supports(features, march):
        return unsupported_message(cpu, march, features)
    known = "" if features is None else " O processador parece ter todas as instrucoes desse nivel."
    return (f"O jogo fechou com 0xC000001D (instrucao ilegal): o processador recebeu uma instrucao que nao executa. "
            f"Este jogo foi compilado para {march}.{known} Envie a pasta de diagnostico desta tentativa "
            "(erros.log tem a linha 'machine:' com o processador e as instrucoes).")
