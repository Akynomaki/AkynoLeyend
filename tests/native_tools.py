"""A native compiler the tests can really execute (not just a name found on PATH)."""
import functools
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def _runs(compiler):
    try:
        return subprocess.run([compiler, "--version"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@functools.lru_cache(maxsize=4)
def native_compiler(cxx=True):
    """OCARINA_TEST_CXX/CC, then PATH, then the SDK's own LLVM (Windows); None when none runs."""
    names = ("c++", "clang++", "g++") if cxx else ("cc", "clang", "gcc")
    candidates = [os.environ.get("OCARINA_TEST_CXX" if cxx else "OCARINA_TEST_CC")]
    candidates += [shutil.which(name) for name in names]
    if os.name == "nt":
        candidates.append(str(ROOT / "ferramentas/llvm/bin" / ("clang++.exe" if cxx else "clang.exe")))
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and _runs(candidate):
            return str(Path(candidate))
    return None


def native_cxx():
    return native_compiler(True)


def native_cc():
    return native_compiler(False)
