"""Collect an existing run and its matching linker map, without recompiling."""

import bisect
import ntpath
import os
from pathlib import Path, PurePosixPath
import re
import struct
import tempfile
import zipfile

from .errors import ProjectError
from .files import read_json, sha256


def image_base(executable: Path) -> int:
    with executable.open("rb") as stream:
        head = stream.read(64)
        if len(head) < 64 or head[:2] != b"MZ":
            raise ValueError("not a PE image")
        stream.seek(struct.unpack_from("<I", head, 60)[0])
        pe = stream.read(56)
    if len(pe) < 56 or pe[:4] != b"PE\0\0" or struct.unpack_from("<H", pe, 24)[0] != 0x20B:
        raise ValueError("not a PE32+ image")
    return struct.unpack_from("<Q", pe, 48)[0]


def map_offsets(map_file: Path, base: int, offsets: list[int]) -> list[str]:
    rows = []
    with map_file.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            match = re.match(
                r"\s*[0-9a-fA-F]{4}:[0-9a-fA-F]{8}\s+(\S+)\s+([0-9a-fA-F]{8,16})\b", line
            )
            if match:
                rows.append((int(match[2], 16), match[1]))
                continue
            match = re.match(r"\s*0x([0-9a-fA-F]+)\s+([A-Za-z_?$@][\w?$@.:]*)\s*$", line)
            if match:
                rows.append((int(match[1], 16), match[2]))
                continue
            # LLVM-MinGW/lld's COFF map uses an RVA, zero size and alignment,
            # then the symbol; object/section rows have a different alignment.
            match = re.match(
                r"\s*([0-9a-fA-F]{8,16})\s+0+\s+0\s+([A-Za-z_?$@][\w?$@.:]*)\s*$", line
            )
            if match:
                rows.append((base + int(match[1], 16), match[2]))
    if not rows:
        return ["Formato do mapa nao reconhecido; mapa completo incluido para analise."]
    rows.sort()
    keys = [row[0] for row in rows]
    lines = []
    for offset in dict.fromkeys(offsets):
        target = base + offset
        at = bisect.bisect_right(keys, target) - 1
        if at < 0 or target - rows[at][0] > 0x100000:
            lines.append(f"AkynoLeyend.exe+{offset:#x}: sem simbolo proximo")
        else:
            address, symbol = rows[at]
            lines.append(
                f"AkynoLeyend.exe+{offset:#x}: simbolo anterior {symbol}+{target - address:#x}"
            )
    return lines


def path_findings(metadata: dict, errors: str) -> list[str]:
    root = metadata.get("build", {}).get("romfs", "")
    runtime = metadata.get("runtime_romfs", root)
    findings = [
        f"RomFS original: {root}",
        f"Comprimento da raiz original: {len(root)} caracteres",
        f"RomFS passado ao runtime: {runtime}",
    ]
    seen = set()
    for match in re.finditer(r"fs: OpenFile\(([^\r\n]+?)\)([^\r\n]*)", errors):
        guest, result = match[1], match[2]
        mount, sep, relative = guest.partition(":/")
        rel = PurePosixPath(relative)
        if (
            not sep
            or mount not in {"content", "rom", "romfs"}
            or ".." in rel.parts
            or rel.is_absolute()
        ):
            continue
        full = ntpath.join(root, *rel.parts)
        if guest in seen or (
            len(full) < 260 and "not found" not in result and "failed" not in result
        ):
            continue
        seen.add(guest)
        exists = "nao verificado neste sistema"
        if os.name == "nt":
            wide = (
                full
                if full.startswith("\\\\?\\")
                else ("\\\\?\\UNC\\" + full[2:] if full.startswith("\\\\") else "\\\\?\\" + full)
            )
            try:
                exists = str(Path(wide).is_file())
            except OSError as error:
                exists = str(error)
        findings.append(
            f"{guest}: caminho original {len(full)} caracteres; "
            f"resultado no runtime {result.strip() or 'aberto'}; existe via caminho longo: {exists}"
        )
        if len(seen) >= 50:
            findings.append("Lista limitada aos primeiros 50 caminhos relevantes.")
            break
    return findings


def collect_run(folder: Path, work: Path, logs: Path | None = None) -> Path:
    if logs is None:
        runs = sorted(
            path
            for path in (folder / "diagnosticos").glob("*")
            if path.is_dir() and (path / "execucao.json").is_file()
        )
        if not runs:
            raise ProjectError("Nenhuma execucao registrada na pasta selecionada.")
        logs = runs[-1]
    metadata = read_json(logs / "execucao.json")
    errors_path = logs / "erros.log"
    if errors_path.stat().st_size > 64 << 20:
        raise ProjectError("O log excede 64 MiB; preserve-o para analise separada.")
    errors = errors_path.read_text(encoding="utf-8", errors="replace")
    status = metadata.get("exit_code")
    if status is None and "CRASH:" not in errors:
        raise ProjectError(
            "Esta tentativa ainda nao tem encerramento registrado nem CRASH no log. "
            "Feche o jogo, aguarde o lancador registrar o resultado e repita a coleta. "
            "Se o lancador foi interrompido, preserve os logs dessa tentativa para analise separada."
        )
    lines = [
        "DIAGNOSTICO AKYNOLEYEND",
        f"Versao do lancador: {metadata.get('launcher_version')}",
        f"Perfil: {metadata.get('profile')}",
        f"Codigo: {status}",
    ]
    failure = metadata.get("runtime_failure")
    if isinstance(failure, dict):
        lines.extend(
            [
                f"Codigo original do processo: {metadata.get('process_exit_code', status)}",
                f"Falha do runtime: {failure.get('kind')}",
                str(failure.get("evidence", "")),
            ]
        )
    if isinstance(failure, dict) and failure.get("kind") == "virtual_memory":
        from .runtime_failure import VIRTUAL_MEMORY_MESSAGE
        lines.append(VIRTUAL_MEMORY_MESSAGE)
        lines.extend(line for line in errors.splitlines() if " mem: " in line and "first touch" not in line)
    if status is None:
        lines.append(
            "Coleta parcial: CRASH presente, mas encerramento do processo nao foi registrado."
        )
    if isinstance(status, int):
        lines.append(f"Codigo NTSTATUS (32 bits): {status & 0xFFFFFFFF:#010x}")
    lines.extend(line for line in errors.splitlines() if "CRASH:" in line)
    lines.extend(["", "CAMINHOS"] + path_findings(metadata, errors))
    mapped = work / "sa/build/AkynoLeyend.map"
    built = work / "sa/build/AkynoLeyend.exe"
    expected = metadata.get("build", {}).get("files", {}).get("AkynoLeyend.exe")
    from .legacy import OLD_EXE

    if not built.is_file():
        legacy = work / "sa/build" / OLD_EXE
        original = metadata.get("build", {}).get("identity_migration", {}).get("original_files", {})
        expected = original.get(OLD_EXE) or metadata.get("build", {}).get("files", {}).get(OLD_EXE)
        if legacy.is_file() and legacy.with_suffix(".map").is_file():
            built, mapped = legacy, legacy.with_suffix(".map")
    matching = False
    try:
        matching = bool(
            expected and mapped.is_file() and built.is_file() and sha256(built) == expected
        )
    except OSError as error:
        lines.append(f"Nao foi possivel conferir o build do mapa: {error}")
    lines.extend(["", "SIMBOLOS", f"Executavel ao lado do mapa corresponde ao crash: {matching}"])
    if matching:
        offsets = [
            int(match, 16)
            for match in re.findall(r"(?:AkynoLeyend|hookshot)\.exe\+0x([0-9a-fA-F]+)", errors)
        ]
        try:
            lines.extend(map_offsets(mapped, image_base(built), offsets))
        except (OSError, ValueError, struct.error) as error:
            lines.append(f"Nao foi possivel interpretar o mapa: {error}")
    else:
        lines.append(
            "Mapa ausente ou executavel diferente. Nao foram atribuidos simbolos a outro build."
        )
    report = logs / "diagnostico-crash.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="diagnostico-", suffix=".tmp", dir=logs.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    archive = logs.with_suffix(".zip")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as bundle:
            for name in (
                "execucao.json",
                "saida.log",
                "erros.log",
                "diagnostico-crash.txt",
                "opcoes-inicio.ini",
                "opcoes-fim.ini",
            ):
                if (logs / name).is_file():
                    bundle.write(logs / name, name)
            if matching:
                bundle.write(mapped, "AkynoLeyend.map")
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    return archive


def preserve_previous_crash(folder: Path, work: Path, report=print) -> None:
    """Save the old map before a new link replaces it; collection is best effort."""
    runs = sorted(
        path
        for path in (folder / "diagnosticos").glob("*")
        if path.is_dir() and (path / "execucao.json").is_file()
    )
    if not runs or runs[-1].with_suffix(".zip").is_file():
        return
    try:
        metadata = read_json(runs[-1] / "execucao.json")
        if metadata.get("exit_code") not in (None, 0):
            report("Diagnostico anterior preservado: " + str(collect_run(folder, work, runs[-1])))
    except (OSError, ProjectError) as error:
        report("Nao foi possivel preservar o diagnostico anterior: " + str(error))
