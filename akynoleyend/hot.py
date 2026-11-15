"""Select the supported optimization list and discard stale hot sources after a fresh lift."""

import re
from pathlib import Path

from .config import SUPPORTED_BUILD
from .errors import ProjectError


def configure_hot(root: Path, environment: dict[str, str]) -> None:
    environment.pop("A64_HOT_FUNCS", None)
    environment.pop("A64_HOT_CHUNK", None)
    profile = root / "profiles" / SUPPORTED_BUILD / "hot_funcs.txt"
    if not profile.is_file():
        return
    lines = [line.strip() for line in profile.read_text(encoding="ascii").splitlines()]
    names = [line for line in lines if line and not line.startswith("#")]
    if not names or any(not re.fullmatch(r"f_[0-9a-f]{8}", name) for name in names):
        raise ProjectError(f"Lista de funcoes de otimizacao invalida: {profile}")
    environment.update(A64_HOT_FUNCS=str(profile), A64_HOT_CHUNK="1")


def has_fresh_hot_source(generated: Path) -> bool:
    """A lift without hot matches is valid; old split pieces must not be compiled again."""
    if (generated / "code_hot.c").is_file():
        return True
    for source in generated.glob("code_hot_*.c"):
        if re.fullmatch(r"code_hot_\d+\.c", source.name):
            source.unlink()
    (generated / "code_hot.c.whole").unlink(missing_ok=True)
    return False
