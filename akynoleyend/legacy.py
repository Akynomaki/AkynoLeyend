"""Reversible conversion of local unsigned 0.3.x builds; old names are compatibility IDs."""

import shutil
import struct
from pathlib import Path
from .errors import ProjectError
from .files import read_json, sha256, workspace_lock, workspace_stage, write_json

OLD_MANIFEST = "ocarina-build.json"
OLD_PROJECT = "ocarina-hookshot"
OLD_EXE = "hookshot.exe"
OLD_DLL = "hookshot_vk.dll"
OLD_OPTIONS = "hookshot_options.ini"
NEW_MANIFEST = "AkynoLeyend-build.json"
NEW_EXE = "AkynoLeyend.exe"
NEW_DLL = "AkynoLeyend.dll"
NEW_OPTIONS = "AkynoLeyend_opts.ini"
VERSIONS = {"0.3.6-dev.1", "0.3.7-dev.1", "0.3.8-dev.1", "0.3.8-dev.2", "0.3.9-dev.1"}


def brand_pe(data: bytes) -> tuple[bytes, dict]:
    try:
        if data[:2] != b"MZ":
            raise ValueError("MZ")
        pe = struct.unpack_from("<I", data, 60)[0]
        machine, sections = struct.unpack_from("<HH", data, pe + 4)
        optional_size = struct.unpack_from("<H", data, pe + 20)[0]
        optional = pe + 24
        if data[pe : pe + 4] != b"PE\0\0" or machine != 0x8664 or optional_size < 240:
            raise ValueError("PE x64")
        if struct.unpack_from("<H", data, optional)[0] != 0x20B:
            raise ValueError("PE32+")
        if any(struct.unpack_from("<II", data, optional + 112 + 4 * 8)):
            raise ValueError("executavel assinado")
        spans = []
        for i in range(sections):
            section = optional + optional_size + i * 40
            size, offset = struct.unpack_from("<II", data, section + 16)
            flags = struct.unpack_from("<I", data, section + 36)[0]
            if offset + size > len(data):
                raise ValueError("secao truncada")
            if flags & 0x40 and flags & 0x40000000 and not flags & (0x80000000 | 0x20000000):
                spans.append((offset, offset + size))
    except (struct.error, ValueError, OverflowError) as e:
        raise ProjectError(
            f"EXE nao pode ser migrado com seguranca ({e}). Use Criar; original preservado."
        ) from e
    result = bytearray(data)
    changes = {}
    for old, new, minimum, maximum in [(OLD_DLL, NEW_DLL, 1, 1), (OLD_OPTIONS, NEW_OPTIONS, 1, 2)]:
        before, after = old.encode() + b"\0", new.encode() + b"\0"
        if len(before) != len(after):
            raise ProjectError("Identificador de migracao com tamanho diferente.")
        found = []
        for begin, end in spans:
            at = data.find(before, begin, end)
            while at >= 0:
                found.append(at)
                at = data.find(before, at + len(before), end)
        if not minimum <= len(found) <= maximum or data.count(before) != len(found):
            raise ProjectError(
                f"Layout do EXE nao reconhecido para {old}; original preservado. Use Criar."
            )
        for at in found:
            result[at : at + len(before)] = after
        changes[old] = {"new": new, "offsets": found}
    return bytes(result), changes


def migrate_build(folder: Path, report=print) -> dict | None:
    if (folder / NEW_MANIFEST).is_file() or not (folder / OLD_MANIFEST).is_file():
        return None
    with workspace_lock(folder):
        if (folder / NEW_MANIFEST).is_file():
            return None
        manifest = read_json(folder / OLD_MANIFEST)
        if (
            not isinstance(manifest, dict)
            or manifest.get("project") != OLD_PROJECT
            or manifest.get("schema") != 1
            or manifest.get("version") not in VERSIONS
            or not str(manifest.get("game_build_id", "")).startswith("e0f3ccfa")
        ):
            raise ProjectError("Instalacao antiga sem ABI de migracao conferida. Use Criar.")
        hashes = manifest.get("files", {})
        if not isinstance(hashes, dict):
            raise ProjectError("Manifesto legado sem tabela de hashes; original preservado.")
        for name in (OLD_EXE, OLD_DLL, "image.bin"):
            if not isinstance(hashes.get(name), str) or sha256(folder / name) != hashes[name]:
                raise ProjectError(f"Arquivo legado alterado: {name}; migracao recusada.")
        if any((folder / n).exists() for n in (NEW_EXE, NEW_DLL)):
            raise ProjectError(
                "Arquivos AkynoLeyend sem manifesto final ja existem; preserve-os antes de migrar."
            )
        converted, changes = brand_pe((folder / OLD_EXE).read_bytes())
        aliases = [
            (OLD_EXE, NEW_EXE),
            (OLD_DLL, NEW_DLL),
            (OLD_OPTIONS, NEW_OPTIONS),
            ("hookshot_shaders.bin", "AkynoLeyend_shaders.bin"),
            ("hookshot_programs.bin", "AkynoLeyend_programs.bin"),
            ("mkw_vk_pipelines.bin", "AkynoLeyend_pipelines.bin"),
            ("hookshot_pipelines.bin", "AkynoLeyend_pipeline_keys.bin"),
            ("hookshot_prepared.bin", "AkynoLeyend_prepared.bin"),
        ]
        published = []
        with workspace_stage(prefix=".identity-", dir=folder) as directory:
            stage = Path(directory)
            (stage / NEW_EXE).write_bytes(converted)
            shutil.copyfile(folder / OLD_DLL, stage / NEW_DLL)
            for old, new in aliases[2:]:
                if (folder / old).is_file() and not (folder / new).exists():
                    shutil.copyfile(folder / old, stage / new)
            updated = dict(manifest, project="AkynoLeyend", files=dict(hashes))
            updated["files"].pop(OLD_EXE)
            updated["files"].pop(OLD_DLL)
            updated["files"][NEW_EXE] = sha256(stage / NEW_EXE)
            updated["files"][NEW_DLL] = sha256(stage / NEW_DLL)
            updated["identity_migration"] = {
                "schema": 1,
                "original_files": dict(hashes),
                "changes": changes,
                "translated_instructions_changed": False,
            }
            try:
                for path in stage.iterdir():
                    path.replace(folder / path.name)
                    published.append(folder / path.name)
                write_json(folder / NEW_MANIFEST, updated)
            except (OSError, ProjectError):
                for path in published:
                    path.unlink(missing_ok=True)
                raise
        backup = folder / "backup-identidade"
        try:
            backup.mkdir(exist_ok=True)
        except OSError:
            report("Identidade publicada; originais mantidos ao lado do jogo.")
            return updated
        for old, _ in aliases:
            if (folder / old).is_file() and not (backup / old).exists():
                try:
                    (folder / old).replace(backup / old)
                except OSError:
                    report(f"Original ainda em uso: {old}; nova identidade ja publicada.")
        if not (backup / OLD_MANIFEST).exists():
            try:
                (folder / OLD_MANIFEST).replace(backup / OLD_MANIFEST)
            except OSError:
                report(
                    "Manifesto original mantido ao lado do jogo; manifesto AkynoLeyend ja publicado."
                )
        report(
            "Identidade AkynoLeyend aplicada; instrucoes traduzidas, imagem, saves e objetos preservados. Backup em backup-identidade."
        )
        return updated


def organize_project(root: Path):
    history = root / "creditos/historico/instalacao-anterior"
    for name in ("ocarina", "OcarinaBuilder.exe", "builder/OcarinaBuilder"):
        path = root / name
        target = history / name
        if path.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            path.replace(target)
    for path in root.glob("LEIA-ME*.txt"):
        target = root / "creditos/historico" / path.name
        if target.exists():
            if target.read_bytes() == path.read_bytes():
                path.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            path.replace(target)
