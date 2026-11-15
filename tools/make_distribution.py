"""Package source and tools, excluding every local game/build artifact."""

import argparse
import hashlib
import json
import re
import zipfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OMIT_TOP = {
    "work",
    "jogo",
    "analysis",
    "diagnosticos-acesso",
    ".git",
    ".venv",
    "dist",
    "atualizacoes",
    ".ruff_cache",
}
OMIT_PARTS = {"__pycache__"}
OMIT_SUFFIXES = {".pyc", ".pyo", ".so", ".o", ".obj", ".sha1", ".sha256", ".building"}


def files(source_only: bool, update: bool = False):
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if relative.as_posix() == "AkynoLeyend-launcher.json":
            continue
        # Atomic-copy leftovers are not runtime dependencies.
        if re.fullmatch(r"\..+\.[A-Za-z0-9]{6}(?:\.[A-Za-z0-9]{6})*", path.name):
            continue
        if relative.parts[0] in OMIT_TOP or OMIT_PARTS.intersection(relative.parts):
            continue
        if relative.parts[0] == "builder" and {"bin", "obj"}.intersection(relative.parts):
            continue
        # NVIDIA's DLSS SDK only builds the renderer here (its headers and static NGX loader); neither it nor the
        # runtime (nvngx_dlss.dll, fetched on the player's PC by `manage.py dlss-runtime`) is handed out.
        if relative.parts[:2] == ("third_party", "nvidia-dlss-sdk") or path.name.casefold() == "nvngx_dlss.dll":
            continue
        if source_only and relative.parts[0] == "ferramentas":
            continue
        if update and relative.parts[0] == "ferramentas" and relative.parts[1] != "prebuilt":
            continue
        if source_only and relative.as_posix() == "AkynoLeyendBuilder.exe":
            continue
        if relative.parts[0] != "ferramentas" and path.suffix.lower() == ".bin":
            raise SystemExit(
                f"Banco/cache ou dados privados fora de work/jogo; mova antes de empacotar: {relative}"
            )
        # The toolchain's CRT startup .o files are required to link Windows programs.
        if relative.parts[0] != "ferramentas" and path.suffix.lower() in OMIT_SUFFIXES:
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        generic_renderer = relative.as_posix() == "ferramentas/prebuilt/AkynoLeyend.dll"
        if (
            path.name in {"AkynoLeyend.exe", "AkynoLeyend.dll", "image.bin", "romfs.bin"}
            and not generic_renderer
        ):
            raise SystemExit(
                f"A game/build artifact was found outside an excluded folder: {relative}"
            )
        yield path, relative


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument(
        "--update", action="store_true", help="Atualizacao da interface/orquestracao para o host exato do Teste 1."
    )
    args = parser.parse_args()
    if args.source_only and args.update:
        parser.error("Choose source-only or update.")
    if args.update:
        from akynoleyend import __version__
        from akynoleyend.coherence import PREVIOUS_HOST_SOURCES
        if __version__ != "0.4.8" or "0.4.7" not in PREVIOUS_HOST_SOURCES or "0.4.6" not in PREVIOUS_HOST_SOURCES or "0.4.5-test.8" not in PREVIOUS_HOST_SOURCES or "0.4.5-test.7" not in PREVIOUS_HOST_SOURCES or "0.4.5-test.6" not in PREVIOUS_HOST_SOURCES or "0.4.5-test.5" not in PREVIOUS_HOST_SOURCES or "0.4.5-test.4" not in PREVIOUS_HOST_SOURCES or "0.4.5-test.3" not in PREVIOUS_HOST_SOURCES or "0.4.5-test.2" not in PREVIOUS_HOST_SOURCES or "0.4.5-test.1" not in PREVIOUS_HOST_SOURCES or "0.4.5" not in PREVIOUS_HOST_SOURCES or "0.4.4" not in PREVIOUS_HOST_SOURCES:
            parser.error("Atualizacao incremental sem host anterior conferido.")
    if not args.source_only:
        from akynoleyend.release import verify_windows_release

        verify_windows_release(ROOT)
    if ROOT in args.out.resolve().parents:
        raise SystemExit("Write the archive outside the source tree.")
    paths = list(files(args.source_only, args.update))
    names = [relative.as_posix().casefold() for _, relative in paths]
    if len(set(names)) != len(names):
        raise SystemExit("Names collide on a case-insensitive Windows filesystem.")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, relative in paths:
            prefix = "" if args.update else ROOT.name + "/"
            archive.write(path, prefix + relative.as_posix())
        if args.update:
            index = {"schema": 1, "kind": "update", "version": __version__,
                     "files": {relative.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path, relative in paths}}
            notes = json.loads((ROOT / "docs/notas-atualizacao.json").read_text(encoding="utf-8"))
            if notes.get("version") != __version__:
                raise SystemExit("docs/notas-atualizacao.json pertence a outra versao.")
            from akynoleyend.updater import package_notes
            index["notes"] = package_notes({"notes": notes["notes"]})
            archive.writestr("update-package.json", json.dumps(index, ensure_ascii=False, indent=2)+"\n")
    print(f"{args.out}: {len(paths)} files, {args.out.stat().st_size} bytes")


if __name__ == "__main__":
    main()
