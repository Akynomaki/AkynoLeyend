"""Prepare controller artwork from the user's existing RomFS, never by rebuilding game code."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from .config import ROOT
from .errors import ProjectError
from .files import read_json, write_json, workspace_stage

MARKER = "AkynoLeyend-prompts.json"
# Private modules for the icon generator (fontTools, Pillow, astc-encoder, texture2ddecoder, archspec),
# shipped with the application for the SDK's CPython 3.14 x64. Never installed into ferramentas/python.
LIBRARIES = "bibliotecas/icones-python"
PROBE = ("import sys;sys.path.insert(0,sys.argv[1]);"
         "import fontTools,PIL,astc_encoder,texture2ddecoder,numpy,zstandard")
FACES = ("switch", "xbox", "ps4", "ps5", "steamdeck")
REQUIRED = ("Common.bntx", "Common.blarc", "ring.bin") + tuple(
    f"{face}/{name}" for face in FACES for name in ("External.bfotf", "textures.bin", "hint.bin")
)
INPUTS = ("Font2/Scalable/External.Nin_Ounce_NVN2.bfotf.zs",
          "UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.bntx.zs",
          "UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.blarc.zs", "Pack/ZsDic.pack.zs")


def source_stamp(root=ROOT):
    digest = hashlib.sha256()
    paths = [root / "nx2" / name for name in ("prompt_assets.py", "prompt_faces.py", "prompt_draw.py", "prompt_requirements.txt")]
    paths += sorted(p for p in (root / "third_party/kenney_input").rglob("*") if p.is_file())
    paths += sorted(p for p in (root / "nx2/prompt_faces").rglob("*") if p.is_file())
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def input_stamp(romfs):
    paths = list(INPUTS)
    tables = sorted((romfs / "System/Resource").glob("ResourceSizeTable.*.rsizetable.zs"))
    if len(tables) != 1:
        raise ValueError("Tabela de tamanho de recursos ausente ou ambigua")
    paths += [tables[0].relative_to(romfs).as_posix()]
    return {name: [int((romfs/name).stat().st_size), int((romfs/name).stat().st_mtime_ns)] for name in paths}


def cached(destination, stamp, inputs):
    try:
        marker = read_json(destination/MARKER)
        if marker.get("schema") != 1 or marker.get("project") != "AkynoLeyend" or marker.get("source") != stamp or marker.get("inputs") != inputs:
            return False
        return all((destination/name).is_file() and (destination/name).stat().st_size == size > 0
                   for name, size in marker["files"].items()) and all(name in marker["files"] for name in REQUIRED)
    except (OSError, ValueError, KeyError, TypeError, ProjectError):
        return False


def prepare_prompts(folder, romfs, *, root=ROOT, report=print, runner=subprocess.run):
    """Atomic, bounded-cache preparation. Missing tooling keeps the original artwork available."""
    folder, romfs = Path(folder), Path(romfs)
    destination = folder/"prompts"
    try:
        inputs = input_stamp(romfs)
        stamp = source_stamp(root)
        if cached(destination, stamp, inputs):
            return {"state": "cached", "folder": str(destination)}
        if destination.exists():
            try:
                owner = read_json(destination/MARKER)
                owned = owner.get("schema") == 1 and owner.get("project") == "AkynoLeyend"
            except (OSError, ValueError, TypeError, ProjectError):
                owned = False
            if not owned:
                report("Icones: pasta prompts externa preservada; a preparacao automatica nao a substitui.")
                return {"state": "external-folder"}
        libraries = root/LIBRARIES
        probe = runner([sys.executable, "-I", "-c", PROBE, str(libraries)],
                       capture_output=True, text=True, timeout=30)
        if probe.returncode:
            report("Icones de controle novos indisponiveis: componentes de " + LIBRARIES + " ausentes ou incompativeis com este Python. Os icones originais permanecem; nenhum objeto do jogo foi alterado.")
            return {"state": "missing-dependencies", "detail": probe.stderr[-1000:]}
        report("@@stage prompts Preparando icones dos controles a partir dos arquivos locais")
        folder.mkdir(parents=True, exist_ok=True)
        with workspace_stage(prefix=".prompts-", dir=folder) as directory:
            stage = Path(directory)
            target = stage/"prepared"
            log = stage/"prepare.log"
            with log.open("w", encoding="utf-8") as output:
                result = runner([sys.executable, "-I", "-X", "utf8", str(root/"nx2/prompt_assets.py"), "--libraries", str(libraries),
                                 "--romfs", str(romfs), "--out", str(target), "--require-complete"],
                                stdout=output, stderr=subprocess.STDOUT, text=True, timeout=1200)
            if result.returncode:
                report("Icones: geracao interrompida; arquivos anteriores preservados.")
                return {"state": "generation-failed", "detail": log.read_text(encoding="utf-8")[-2000:]}
            if not all((target/name).is_file() and (target/name).stat().st_size for name in REQUIRED):
                return {"state": "incomplete", "detail": "O gerador nao produziu todos os estilos/layouts"}
            files = {p.relative_to(target).as_posix(): p.stat().st_size for p in target.rglob("*") if p.is_file()}
            write_json(target/MARKER, {"schema": 1, "project": "AkynoLeyend", "source": stamp, "inputs": inputs, "files": files})
            previous = stage/"previous"
            had_previous = destination.exists()
            if had_previous:
                destination.replace(previous)
            try:
                target.replace(destination)
            except OSError:
                if had_previous:
                    previous.replace(destination)
                raise
        report("Icones de controles prontos; arquivos do jogo, objetos e saves preservados.")
        return {"state": "prepared", "folder": str(destination)}
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        report("Icones: " + str(error) + "; icones originais/anteriores preservados.")
        return {"state": "unavailable", "detail": str(error)}
