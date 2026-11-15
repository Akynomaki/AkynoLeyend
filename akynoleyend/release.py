"""Reject Windows packages whose launcher or renderer differs from their sources."""

import hashlib
from pathlib import Path, PureWindowsPath

from . import __version__
from .errors import ProjectError
from .files import read_json, sha256
from .prebuilt import renderer_prebuilt


def launcher_identity(root: Path) -> str:
    folder = root / "builder/AkynoLeyendBuilder"
    digest = hashlib.sha256()
    # Preserve the order of the Windows receipts when packaging from another OS.
    for path in sorted(folder.rglob("*"), key=lambda p: PureWindowsPath(*p.relative_to(folder).parts)):
        if not path.is_file() or {"bin", "obj"}.intersection(path.relative_to(folder).parts):
            continue
        if path.suffix not in {".cs", ".xaml", ".csproj", ".manifest"}:
            continue
        digest.update(path.relative_to(folder).as_posix().encode() + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    for name in ("AkynoLeyend.ico", "AkynoLeyend.png"):
        path = root / "assets" / name
        digest.update(name.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def verify_launcher(root: Path):
    receipt = read_json(root / "builder/launcher-build.json")
    binary = root / "AkynoLeyendBuilder.exe"
    if (
        receipt.get("schema") != 1
        or receipt.get("version") != __version__
        or receipt.get("source_sha256") != launcher_identity(root)
        or receipt.get("binary_sha256") != sha256(binary)
        or receipt.get("pe_product_version") != __version__
    ):
        raise ProjectError(
            "O launcher nao corresponde a esta revisao. Republique a interface antes de empacotar."
        )
    with binary.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ProjectError("Launcher sem cabecalho Windows PE.")


def verify_windows_release(root: Path):
    verify_launcher(root)
    ready = renderer_prebuilt(
        root,
        root / "ferramentas/deps",
        root / "ferramentas/prebuilt",
        {"OCARINA_TARGET": "windows-gnu", "RX_RELEASE": "1"},
        lambda _: None,
    )
    if ready is None:
        raise ProjectError(
            "A DLL da distribuicao nao corresponde aos fontes, dependencias e configuracao."
        )
    metadata = read_json(ready.parent / "renderer.json")
    if metadata.get("release") != __version__:
        raise ProjectError("A DLL generica pertence a outra revisao.")
