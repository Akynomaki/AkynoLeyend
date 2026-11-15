"""Validated paths and a memory-aware compile policy."""

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import ProjectError
from .files import require_separate
from .hardware import snapshot

ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_BUILD = "e0f3ccfa"
MANIFEST = "AkynoLeyend-build.json"
LANGUAGES = {
    "en-US",
    "en-GB",
    "fr",
    "fr-CA",
    "de",
    "it",
    "es",
    "es-419",
    "pt-BR",
    "nl",
    "pl",
    "ru",
    "ja",
    "ko",
    "zh-Hans",
    "zh-Hant",
}


def available_memory() -> int:
    return snapshot()["ram_available"]


def compile_jobs(
    requested: int | None, free_bytes: int | None = None, cpus: int | None = None,
    *, chunk_mib: int = 6,
) -> int:
    """Compiler processes at once. Before 0.4.5: 3.5 GiB set aside for each, one process on a 16 GB PC. Now one a thread,
    as many as a typical unit's measured peak fits in the free memory (compile_plan.compile_slots); nx2/build.py's memory
    gate holds back a heavier unit until it fits."""
    if requested is not None:
        if requested < 1:
            raise ProjectError("--jobs deve ser maior que zero.")
        return requested
    from .compile_plan import compile_slots
    free = available_memory() if free_bytes is None else free_bytes
    cores = max(1, cpus if cpus is not None else
                (getattr(os, "process_cpu_count", os.cpu_count)() or 1))
    return compile_slots(free, cores, chunk_mib=chunk_mib)


@dataclass(frozen=True)
class BuildRequest:
    output: Path
    work: Path
    tools: Path
    nup: Path | None = None
    exefs: Path | None = None
    romfs: Path | None = None
    language: str = "pt-BR"
    jobs: int | None = None
    chunk_mib: int | None = None
    renderer_from_source: bool = False

    def validate(self) -> None:
        if self.chunk_mib is not None and self.chunk_mib not in (3, 6, 12, 24):
            raise ProjectError("--chunk-mib deve ser 3, 6, 12 ou 24.")
        if bool(self.nup) == bool(self.exefs or self.romfs):
            raise ProjectError("Use --nup ARQUIVO ou o par --exefs PASTA --romfs PASTA.")
        if not self.nup and not (self.exefs and self.romfs):
            raise ProjectError("Informe as duas pastas: --exefs e --romfs.")
        if self.language not in LANGUAGES:
            raise ProjectError(f"Idioma nao suportado: {self.language}")
        compile_jobs(self.jobs)
        for source in (self.nup, self.exefs, self.romfs):
            if source is None:
                continue
            if not source.exists():
                raise ProjectError(f"Entrada nao encontrada: {source}")
            require_separate(self.output, source)
            require_separate(self.work, source)
        require_separate(self.output, self.work)
        for folder in (self.output, self.work):
            require_separate(folder, ROOT / "host")
            require_separate(folder, ROOT / "gpu")
            require_separate(folder, ROOT / "third_party")
        if self.nup and not self.nup.is_file():
            raise ProjectError("--nup deve apontar para um arquivo.")
        if self.exefs and not (self.exefs / "main").is_file():
            raise ProjectError("A pasta exefs deve conter o modulo main.")
        if self.romfs and not self.romfs.is_dir():
            raise ProjectError("--romfs deve apontar para uma pasta.")
