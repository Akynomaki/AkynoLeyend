"""NVIDIA DLSS's runtime (nvngx_dlss.dll) for the dlss/dlaa upscaling modes.

The runtime is NVIDIA's, under NVIDIA's own license (the RTX SDKs license, saved as LICENSE.txt beside it). AkynoLeyend
never ships it: this fetches it from NVIDIA's DLSS repository at one pinned release, checked against its SHA-256, into
%LOCALAPPDATA%\\AkynoLeyend\\ngx, and only after the player has accepted NVIDIA's license (--accept-nvidia-license, or the
launcher's own question). The game reads that folder from AKYNO_DLSS_DIR. NGX's core (_nvngx.dll) comes with NVIDIA's
driver and is never copied. The pinned release and hashes are Hookshot 2.1.0's (scripts/ngx_sdk.py, v310.9.16).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import urllib.request
from pathlib import Path

from .errors import ProjectError

COMMIT = "9981c6350dc58c0ce21f024fd65e31e851c31689"   # (NVIDIA/DLSS v310.9.16)
BASE = "https://raw.githubusercontent.com/NVIDIA/DLSS/" + COMMIT
LICENSE_URL = "https://github.com/NVIDIA/DLSS/blob/%s/LICENSE.txt" % COMMIT
FILES = {
    "nvngx_dlss.dll": ("lib/Windows_x86_64/rel/nvngx_dlss.dll",
                       "d00b5b0ab29c3ca101b70c3a5ecb3a01b7ef33766a3383a28a18623083e6123e"),
    "LICENSE.txt": ("LICENSE.txt", "d4216e39ebef5f9b50a6712ebb37beeb5379862a67733a9999c651f21592aaf0"),
}
VERSION = "310.9.16"
TIMEOUT = 60

NOTICE = (
    "NVIDIA DLSS: o AkynoLeyend nao inclui nem redistribui o runtime da NVIDIA. Este comando baixa nvngx_dlss.dll "
    "(DLSS %s) do repositorio oficial github.com/NVIDIA/DLSS, confere o SHA-256 e o guarda em %%LOCALAPPDATA%%\\AkynoLeyend\\ngx. "
    "O arquivo e da NVIDIA e segue a licenca NVIDIA RTX SDKs: %s (salva como LICENSE.txt ao lado). "
    "Usar o DLSS significa aceitar essa licenca." % (VERSION, LICENSE_URL)
)


def runtime_directory(environment: dict | None = None) -> Path:
    env = os.environ if environment is None else environment
    base = env.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "AkynoLeyend" / "ngx"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def installed(directory: Path | None = None) -> Path | None:
    """The folder when it holds the pinned runtime and NVIDIA's license, unchanged; None otherwise"""
    folder = directory or runtime_directory()
    for name, (_, digest) in FILES.items():
        path = folder / name
        if not path.is_file() or _sha256(path) != digest:
            return None
    return folder


def fetch(accepted: bool, directory: Path | None = None, opener=urllib.request.urlopen, say=print) -> Path:
    """Both files into the folder, each through a .part file kept only when its SHA-256 is the expected one"""
    if not accepted:
        raise ProjectError(
            "A licenca da NVIDIA nao foi aceita: nada foi baixado. Leia " + LICENSE_URL +
            " e use --accept-nvidia-license (ou o botao do launcher) se concordar."
        )
    folder = directory or runtime_directory()
    folder.mkdir(parents=True, exist_ok=True)
    for name, (path, digest) in FILES.items():
        target = folder / name
        if target.is_file() and _sha256(target) == digest:
            continue
        part = target.with_name(target.name + ".part")
        try:
            with opener(BASE + "/" + path, timeout=TIMEOUT) as response, part.open("wb") as out:
                shutil.copyfileobj(response, out, 1 << 20)
            if _sha256(part) != digest:
                raise ProjectError(f"{name} baixado nao confere com o SHA-256 esperado; descartado.")
            os.replace(part, target)
            say(f"DLSS: {name} conferido em {folder}")
        except OSError as error:
            raise ProjectError(f"Nao foi possivel baixar {name} da NVIDIA: {error}") from error
        finally:
            if part.exists():
                part.unlink()
    return folder
