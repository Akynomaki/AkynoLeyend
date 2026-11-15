"""Read game identities without extracting data or invoking a compiler."""

import importlib.util
import struct
from pathlib import Path

from .config import ROOT, SUPPORTED_BUILD
from .errors import ProjectError


def _identity(header: bytes, description: str) -> str:
    if len(header) != 0x60 or header[:4] != b"NSO0":
        raise ProjectError(f"Modulo main invalido: {description}")
    identity = header[0x40:0x60].hex()
    if not identity.startswith(SUPPORTED_BUILD):
        raise ProjectError(f"Build do jogo {identity[:8]}; esta base suporta {SUPPORTED_BUILD}.")
    return identity


def build_id(main: Path) -> str:
    try:
        with main.open("rb") as stream:
            header = stream.read(0x60)
    except OSError as error:
        raise ProjectError(f"Nao foi possivel ler {main}: {error}") from error
    if len(header) != 0x60 or header[:4] != b"NSO0":
        raise ProjectError(f"Modulo main invalido: {main}")
    return header[0x40:0x60].hex()


def verify_version(exefs: Path) -> str:
    identity = build_id(exefs / "main")
    if not identity.startswith(SUPPORTED_BUILD):
        raise ProjectError(f"Build do jogo {identity[:8]}; esta base suporta {SUPPORTED_BUILD}.")
    return identity


def verify_nup(path: Path) -> str:
    specification = importlib.util.spec_from_file_location(
        "ocarina_nup_reader", ROOT / "nx2/nup.py"
    )
    assert specification and specification.loader
    reader = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(reader)
    archive = None
    try:
        archive = reader.Nup(path)
        title = reader.pick_title(archive, None)
        main = next(
            (record for name, record in archive.walk(title["exefs"]) if name == "main"), None
        )
        if main is None:
            raise ProjectError("O arquivo nao contem o modulo main esperado.")
        return _identity(archive.read(main, 0x60), str(path))
    except (OSError, ValueError, IndexError, RecursionError, struct.error, SystemExit) as error:
        raise ProjectError(f"Nao foi possivel validar o arquivo .nup: {error}") from error
    finally:
        if archive is not None:
            archive.f.close()
