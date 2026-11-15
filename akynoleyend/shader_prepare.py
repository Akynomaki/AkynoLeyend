"""Prepare private shader packages and update only an ABI-compatible renderer."""

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from . import __version__
from .coherence import require_host
from .access import FileAccessError
from .config import MANIFEST, ROOT, SUPPORTED_BUILD
from .cpu import DEFAULT_MARCH, build_march
from .environment import clean_environment
from .errors import ProjectError
from .files import read_json, sha256, workspace_lock, workspace_stage, write_json
from .launch import checked_build, launch
from .prebuilt import renderer_prebuilt
from .process import run

def copy_chunks(source: Path, target: Path) -> None:
    with source.open("rb") as input_file, target.open("wb") as output:
        while block := input_file.read(64 << 10):
            output.write(block)


def update_renderer(folder: Path, work: Path, *, report=print) -> dict:
    """Refresh only the DLL of a host already built from this runtime revision."""
    with workspace_lock(work):
        manifest = checked_build(folder)
        return _update_renderer(folder, manifest, report)


def _update_renderer(folder: Path, manifest: dict, report) -> dict:
    from .build import source_identity
    require_host(manifest)
    if not str(manifest.get("game_build_id", "")).startswith(SUPPORTED_BUILD):
        raise ProjectError(
            "Build ID sem ABI conferida para esta atualizacao. Use Criar com a entrada suportada."
        )
    if build_march(manifest) != DEFAULT_MARCH:
        # (r13j) a game compiled for a CPU without AVX2 keeps the renderer compiled with it: the packaged DLL is x86-64-v3
        report(f"Renderizador compilado para {build_march(manifest)} mantido (a DLL pronta do pacote e x86-64-v3).")
        return manifest
    source = renderer_prebuilt(
        ROOT,
        ROOT / "ferramentas/deps",
        ROOT / "ferramentas/prebuilt",
        {"OCARINA_TARGET": "windows-gnu", "RX_RELEASE": "1"},
        report,
    )
    if source is None:
        raise ProjectError(
            "A DLL pronta nao corresponde a estes fontes. Use Criar para compilar o renderizador."
        )
    identity = read_json(source.parent / "renderer.json")
    updated = dict(
        manifest,
        files=dict(manifest["files"]),
        renderer_version=__version__,
        renderer_source_sha256=identity["source_sha256"],
        runtime_source_sha256=source_identity(),
    )
    updated["files"]["AkynoLeyend.dll"] = identity["binary_sha256"]
    target = folder / "AkynoLeyend.dll"
    if manifest["files"]["AkynoLeyend.dll"] != identity["binary_sha256"]:
        with workspace_stage(prefix=".renderer-update-", dir=folder) as directory:
            stage = Path(directory)
            changed = False
            try:
                copy_chunks(target, stage / "previous.dll")
                copy_chunks(source, stage / "new.dll")
                if sha256(stage / "new.dll") != identity["binary_sha256"]:
                    raise ProjectError(
                        "A copia da DLL nao passou pela conferencia de hash; jogo preservado."
                    )
                (stage / "new.dll").replace(target)
                changed = True
                write_json(folder / MANIFEST, updated)
            except (OSError, ProjectError) as error:
                if changed:
                    try:
                        (stage / "previous.dll").replace(target)
                        write_json(folder / MANIFEST, manifest)
                    except OSError as rollback:
                        # Preserve a recoverable copy instead of letting TemporaryDirectory delete it.
                        backup = folder / (
                            "renderizador-anterior-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
                        )
                        backup.mkdir(exist_ok=True)
                        for name in ("previous.dll", "new.dll"):
                            if (stage / name).is_file():
                                shutil.copyfile(stage / name, backup / name)
                        raise ProjectError(
                            f"Atualizacao interrompida; confira {backup}. Reversao: {rollback}"
                        ) from error
                if isinstance(error, OSError):
                    raise FileAccessError(target, error, "atualizar") from error
                raise
    else:
        write_json(folder / MANIFEST, updated)
    report(
        "Renderizador atualizado e conferido; EXE, imagem, saves e objetos de compilacao preservados."
    )
    return updated


def seed_identity(romfs: Path, image_hash: str) -> str:
    files = [romfs / "Pack/ZsDic.pack.zs"]
    for name in ("Shader", "Layout2Shader", "Lib", "Movie", "Effect"):
        top = romfs / name
        if top.is_dir():
            files.extend(
                p for p in sorted(top.rglob("*")) if p.is_file() and
                (p.name.endswith(".zs") or any(ext in p.name for ext in (".bfsha", ".sarc", ".pck", ".sharcb")))
            )
    if len(files) == 1:
        raise ProjectError(
            "RomFS sem arquivos de shader suportados; o banco anterior foi preservado."
        )
    metadata = []
    for path in files:
        try:
            info = path.stat()
        except OSError as error:
            raise FileAccessError(path, error, "consultar") from error
        metadata.append((path.relative_to(romfs).as_posix(), info.st_size, info.st_mtime_ns))
    data = {
        "schema": 1,
        "image": image_hash,
        "romfs": str(romfs),
        "files": metadata,
        "writer": sha256(ROOT / "nx2/shader_census.py"),
        "containers": sha256(ROOT / "nx2/shader_containers.py"),
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def bank_stamp(path: Path) -> dict:
    value = path.stat()
    if path.is_symlink():
        return {}
    return {"size": value.st_size, "mtime_ns": value.st_mtime_ns,
            "ctime_ns": value.st_ctime_ns, "inode": value.st_ino, "device": value.st_dev}


def prepare_shaders(
    folder: Path,
    work: Path,
    *,
    texture_mode: str = "auto",
    force: bool = False,
    start_game: bool = True,
    shader_workers: int | None = None,
    report=print,
    verified_manifest: dict | None = None,
) -> int:
    with workspace_lock(work):
        manifest = verified_manifest if verified_manifest is not None else checked_build(folder)
        if verified_manifest is None:
            manifest = _update_renderer(folder, manifest, report)
        romfs = Path(manifest["romfs"])
        identity = seed_identity(romfs, manifest["files"]["image.bin"])
        cache = work / "shaders"
        cache.mkdir(parents=True, exist_ok=True)
        bank, marker = cache / "AkynoLeyend_shaders.bin", cache / "seed.json"
        reuse = False
        known_digest = None
        reading = marker
        previous = {}
        try:
            marker.stat()
            previous = read_json(marker)
            reading = bank
            reuse = (
                not force
                and previous.get("input") == identity
                and isinstance(previous.get("sha256"), str)
                and len(previous["sha256"]) == 64
                and (previous.get("bank_stamp") == bank_stamp(bank)
                     or sha256(bank) == previous.get("sha256"))
            )
            if reuse:
                known_digest = previous["sha256"]
        except FileNotFoundError:
            pass
        except OSError as error:
            raise FileAccessError(reading, error, "ler o cache de shaders em") from error
        except ProjectError as error:
            if isinstance(error.__cause__, OSError):
                raise FileAccessError(marker, error.__cause__, "ler") from error
            report("Indice de shaders invalido; regenerando somente esse banco privado.")
        if not reuse:
            report("Indexando os shaders da sua copia do jogo; os pacotes ficam no disco.")
            run(
                [
                    sys.executable,
                    "-I",
                    "-X",
                    "utf8",
                    "-u",
                    str(ROOT / "nx2/shader_census.py"),
                    str(romfs),
                    "--out",
                    str(bank),
                ],
                ROOT,
                clean_environment(os.environ),
                work / "logs/shader-census.log",
                report,
            )
            known_digest = sha256(bank)
            write_json(marker, {"schema": 1, "input": identity, "sha256": known_digest})
        else:
            report(
                "Banco privado de shaders reaproveitado; nenhuma reextracao ou compilacao C foi iniciada."
            )
        # Banco idêntico: nao grave gigabytes desnecessarios em cada preparacao.
        # Confere o hash REAL do arquivo publicado (e tamanho) antes de reutilizar.
        dest = folder / bank.name
        if (
            dest.is_file()
            and not dest.is_symlink()
            and dest.stat().st_size == bank.stat().st_size
            and ((previous.get("sha256") == known_digest
                  and previous.get("installed_path") == str(dest.resolve())
                  and previous.get("installed_stamp") == bank_stamp(dest))
                 or sha256(dest) == known_digest)
        ):
            report("Banco de shaders ja instalado e conferido; copia dispensada.")
        else:
            with workspace_stage(prefix=".shader-publish-", dir=folder) as directory:
                staged = Path(directory) / bank.name
                copy_chunks(bank, staged)
                if sha256(staged) != known_digest:
                    raise ProjectError(
                        "Banco de shaders alterado durante a copia; o anterior foi preservado."
                    )
                staged.replace(dest)
        receipt = {"schema": 2, "input": identity, "sha256": known_digest,
                   "bank_stamp": bank_stamp(bank), "installed_path": str(dest.resolve()),
                   "installed_stamp": bank_stamp(dest)}
        if receipt != previous:
            write_json(marker, receipt)
    report("Banco pronto. O inicio do jogo confere shaders e pipelines para esta GPU e driver.")
    if not start_game:
        return 0
    return launch(
        folder,
        texture_mode=texture_mode,
        cache_mode="preparacao",
        prepare_again=True,
        collect_crash=True,
        shader_workers=shader_workers,
        work=work,
    )
