"""A single build pipeline, with source validation and a verifiable installation."""

import hashlib
import os
import shutil
import sys
import time
import stat
from collections.abc import Callable
from pathlib import Path

from . import __version__
from .coherence import HOST_REVISION
from .config import MANIFEST, ROOT, BuildRequest, compile_jobs, available_memory
from .errors import ProjectError
from .files import read_json, sha256, write_json, workspace_lock, workspace_stage
from .fsr_sdk import HOST_FEATURE as FSR_HOST_FEATURE, jitter_emitted
from .graphics import EXTENDED_OUTPUT_FEATURE, executable_has_literal
from nx2.oot_output_size import extended_output_emitted
from .preflight import require_tools
from .cpu import DEFAULT_MARCH, choose_march, detect as detect_cpu, missing as cpu_missing
from .prebuilt import renderer_identity
from .process import run
from .game import verify_version, verify_nup
from .hot import configure_hot, has_fresh_hot_source
from .progress import CompileProgress
from .power import keep_awake
from .romfs import require_romfs, directory_state
from .timing import BuildTimings
from .hardware import snapshot, recommended_chunk, usable_memory
from .crash_report import preserve_previous_crash

REQUIRED_OUTPUTS = ("AkynoLeyend.exe", "AkynoLeyend.dll")


def source_identity(root: Path = ROOT) -> str:
    """Hash the source that participates in this build, not user game data."""
    digest = hashlib.sha256()
    # (NVIDIA's DLSS SDK builds only the renderer, which has its own identity, and is never handed out: a player's tree
    # without it has the same identity as this one)
    ngx_sdk = root / "third_party" / "nvidia-dlss-sdk"
    for name in ("nx2", "host", "gpu", "third_party", "akynoleyend", "profiles"):
        for path in sorted((root / name).rglob("*")):
            if ngx_sdk in path.parents:
                continue
            if path.is_file() and path.suffix in {
                ".c",
                ".cpp",
                ".h",
                ".hpp",
                ".inc",
                ".py",
                ".txt",
                ".json",
            }:
                digest.update(path.relative_to(root).as_posix().encode() + b"\0")
                digest.update(path.read_bytes())
    return digest.hexdigest()


def check_output(output: Path) -> None:
    if not output.exists() or not any(output.iterdir()):
        return
    from .legacy import OLD_MANIFEST, OLD_PROJECT
    marker = output / MANIFEST
    if not marker.exists():
        marker=output/OLD_MANIFEST
    if not marker.is_file() or read_json(marker).get("project") not in {"AkynoLeyend",OLD_PROJECT}:
        raise ProjectError(
            "Escolha uma pasta de saida vazia ou criada por esta base: " + str(output)
        )


def cached_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.stat().st_mode)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise ProjectError(f"Arquivo do cache inacessivel: {path}: {error}. "
                           "Confira o acesso antes de repetir a extracao; os dados foram preservados.") from error


# (0.4.5) readers whose extraction is byte for byte the current one's: nx2/nup.py c1b9fb6f (0.4.3 to 0.4.4) wrote the same
# files on one thread; 0.4.5 writes them on several and decompresses a wrapped .zs once. A cache it marked is not repaired
SAME_OUTPUT_READERS = ("c1b9fb6f9bb6a6548d77d7a773a36fc852a37b40ba3c5285d27a1d8bcaef4374",)


def nup_identity(nup: Path, work: Path, report: Callable[[str], None]) -> str:
    """SHA-256 of the .nup, remembered for the same file (0.4.5: 25 GB read on every Criar, 193 s on the 3500X's SATA SSD).
    Reused only when the path, size and modification time are the ones it was computed for; anything else reads it again."""
    record = work / "inputs" / "nup-identity.json"
    info = nup.stat()
    key = {"path": str(nup.resolve()), "size": info.st_size, "mtime_ns": info.st_mtime_ns}
    try:
        known = read_json(record) if record.is_file() else {}
        if all(known.get(name) == value for name, value in key.items()) and len(str(known.get("sha256", ""))) == 64:
            report("Identidade do arquivo de entrada: a mesma do ultimo uso (caminho, tamanho e data iguais).")
            return known["sha256"]
    except (OSError, ValueError, TypeError, AttributeError, ProjectError):
        pass
    report("Calculando a identidade do arquivo de entrada...")
    identity = sha256(nup)
    try:
        record.parent.mkdir(parents=True, exist_ok=True)
        write_json(record, {**key, "sha256": identity})
    except OSError:
        pass
    return identity


def prepare_inputs(
    request: BuildRequest, environment: dict[str, str], report: Callable[[str], None]
) -> tuple[Path, Path]:
    if request.nup is None:
        assert request.exefs and request.romfs
        verify_version(request.exefs)
        digest = hashlib.sha256()
        for source in sorted(request.exefs.rglob("*")):
            if source.is_file():
                digest.update(source.relative_to(request.exefs).as_posix().encode())
                digest.update(sha256(source).encode())
        digest.update(sha256(ROOT / "nx2/unpack.py").encode())
        private = request.work / "inputs" / digest.hexdigest()
        if not cached_file(private / "input.json"):
            private.parent.mkdir(parents=True, exist_ok=True)
            with workspace_stage(prefix="modules-", dir=private.parent) as directory:
                stage = Path(directory) / "modules"
                shutil.copytree(request.exefs, stage / "exefs")
                run(
                    [
                        sys.executable,
                        "-I",
                        "-u",
                        str(ROOT / "nx2/unpack.py"),
                        str(stage / "exefs"),
                    ],
                    ROOT,
                    environment,
                    request.work / "logs/unpack.log",
                    report,
                )
                write_json(
                    stage / "input.json",
                    {"source": str(request.exefs), "private_copy": True},
                )
                if private.exists():
                    raise ProjectError(f"Entrada incompleta em {private}; use outra pasta --work.")
                stage.replace(private)
        return private / "exefs", request.romfs
    verify_nup(request.nup)
    identity = nup_identity(request.nup, request.work, report)
    reader_identity = sha256(ROOT / "nx2/nup.py")
    inputs = request.work / "inputs" / identity
    complete = inputs / "input.json"
    romfs_state, romfs_error = directory_state(inputs / "romfs")
    if romfs_state == "inaccessible":
        raise ProjectError(f"RomFS do cache inacessivel: {inputs / 'romfs'}: {romfs_error}. Os dados foram preservados.")
    if cached_file(complete) and cached_file(inputs / "exefs/main") and romfs_state == "present":
        marker = read_json(complete)
        if marker.get("sha256") != identity:
            raise ProjectError(f"Identidade da extracao nao confere: {complete}")
        if marker.get("reader_sha256") not in (reader_identity, *SAME_OUTPUT_READERS):
            report(
                "Conferindo a extracao existente com o leitor atualizado; reparando entradas compactadas."
            )
            run(
                [
                    sys.executable,
                    "-I",
                    "-u",
                    str(ROOT / "nx2/nup.py"),
                    str(request.nup),
                    "--extract",
                    str(inputs),
                ],
                ROOT,
                environment,
                request.work / "logs/extract-repair.log",
                report,
            )
            verify_version(inputs / "exefs")
            marker["reader_sha256"] = reader_identity
            write_json(complete, marker)
        verify_version(inputs / "exefs")
        return inputs / "exefs", inputs / "romfs"
    inputs_state, inputs_error = directory_state(inputs)
    if inputs_state == "inaccessible":
        raise ProjectError(f"Entrada privada inacessivel: {inputs}: {inputs_error}")
    if inputs_state != "missing":
        raise ProjectError(f"Extracao incompleta ja existente: {inputs}. Confira o acesso ou use outra pasta --work; "
                           "nao foi iniciada uma segunda extracao.")
    inputs.parent.mkdir(parents=True, exist_ok=True)
    with workspace_stage(prefix="extract-", dir=inputs.parent) as directory:
        stage = Path(directory) / "game"
        run(
            [
                sys.executable,
                "-I",
                "-u",
                str(ROOT / "nx2/nup.py"),
                str(request.nup),
                "--extract",
                str(stage),
            ],
            ROOT,
            environment,
            request.work / "logs/extract.log",
            report,
        )
        verify_version(stage / "exefs")
        if not (stage / "romfs").is_dir():
            raise ProjectError("O arquivo nao produziu uma pasta romfs.")
        write_json(
            stage / "input.json",
            {"sha256": identity, "source": str(request.nup), "reader_sha256": reader_identity},
        )
        if inputs.exists():
            raise ProjectError(
                f"Extracao incompleta ja existente: {inputs}. Use outra pasta --work."
            )
        stage.replace(inputs)
    return inputs / "exefs", inputs / "romfs"


def publish(request: BuildRequest, romfs: Path, identity: str, jobs: int, started: float,
            march: str = DEFAULT_MARCH) -> dict:
    built = request.work / "sa/build"
    image = request.work / "sa/image/image.bin"
    files = {name: built / name for name in REQUIRED_OUTPUTS}
    files["image.bin"] = image
    for name in ("SDL2.dll", "SDL3.dll"):   # (r12: sdl2-compat and the SDL3 it runs on)
        if (built / name).is_file():
            files[name] = built / name
    missing = [str(path) for path in files.values() if not path.is_file()]
    if missing:
        raise ProjectError("A compilacao nao produziu todos os arquivos:\n" + "\n".join(missing))
    extended_output = extended_output_emitted(request.work / "sa/gen")
    if extended_output and not executable_has_literal(
        files["AkynoLeyend.exe"], "runtime-features: " + EXTENDED_OUTPUT_FEATURE
    ):
        raise ProjectError("O EXE ligado nao confirmou o suporte a 720p e 2560x1600. Publicacao interrompida.")
    request.output.mkdir(parents=True, exist_ok=True)
    with workspace_stage(prefix=".publish-", dir=request.output) as directory:
        stage = Path(directory)
        hashes = {}
        for name, source in files.items():
            shutil.copy2(source, stage / name)
            hashes[name] = sha256(stage / name)
        language = stage / "language.txt"
        language.write_text(request.language + "\n", encoding="utf-8")
        for path in stage.iterdir():
            path.replace(request.output / path.name)
        manifest = {
            "schema": 1,
            "project": "AkynoLeyend",
            "version": __version__,
            "host_revision": HOST_REVISION,
            "host_features": ["fullhd-video-budget-v1", "controller-prompts-v1"]
                             + ([FSR_HOST_FEATURE] if jitter_emitted(request.work) else [])
                             + ([EXTENDED_OUTPUT_FEATURE] if extended_output else []),
            "source_sha256": source_identity(),
            "game_build_id": identity,
            "files": hashes,
            "romfs": str(romfs.resolve()),
            "jobs": jobs,
            "language": request.language,
            "seconds": round(time.monotonic() - started, 2),
            "renderer": "vulkan",
            "renderer_version": __version__,
            "renderer_source_sha256": renderer_identity(ROOT, request.tools / "deps"),
            "toolchain": "llvm-mingw",
            # (r13j) the x86-64 level the game, the host and the renderer were compiled for (cpu.py; before r13j: x86-64-v3)
            "march": march,
        }
        # Published last. A mixed or interrupted update cannot pass the launcher's hash check.
        write_json(request.output / MANIFEST, manifest)
    return manifest


def build(request: BuildRequest, report: Callable[[str], None] = print) -> dict:
    request.validate()
    with workspace_lock(request.work), keep_awake():
        return _build_locked(request, report)


def _build_locked(request: BuildRequest, report: Callable[[str], None]) -> dict:
    check_output(request.output)
    preserve_previous_crash(request.output, request.work, report)
    report("@@stage read Verificando arquivos e ferramentas")
    report("Verificando compilador, bibliotecas e Python...")
    environment = require_tools(request.tools)
    # (r13j) the x86-64 level this PC's CPU runs (cpu.py): x86-64-v3 as before where it has AVX2, FMA and BMI1/2, else v2 or
    # x86-64. A level other than x86-64-v3 does not match the packaged renderer: nx2/build.py compiles it from the sources
    cpu_features = detect_cpu(request.tools)
    march = choose_march(cpu_features) if cpu_features is not None else DEFAULT_MARCH
    environment["RX_MARCH"] = march
    if cpu_features is None:
        report(f"Processador: instrucoes nao conferidas; compilando para {march}, como antes.")
    elif march == DEFAULT_MARCH:
        report(f"Processador: compilando para {march} (AVX2, FMA, BMI1/2).")
    else:
        report(f"Processador sem {', '.join(cpu_missing(cpu_features, DEFAULT_MARCH))}: compilando o jogo e o renderizador "
               f"para {march}. O renderizador pronto (x86-64-v3) nao serve neste PC e sera compilado dos fontes, "
               "sem NVIDIA DLSS (o SDK da NVIDIA nao vem no pacote); FSR continua.")
    environment["OCARINA_HELPER_CACHE"] = str(request.work / "helpers")
    environment["OCARINA_PREBUILT_DIR"] = str(request.tools / "prebuilt")
    environment["OCARINA_BUILD_RENDERER"] = "1" if request.renderer_from_source else "0"
    started = time.monotonic()
    request.work.mkdir(parents=True, exist_ok=True)
    timing = BuildTimings(request.work, report)
    exefs, romfs = timing.measure("inputs", prepare_inputs, request, environment, report)
    require_romfs(romfs)
    identity = verify_version(exefs)
    hardware = snapshot()
    chunk_mib = request.chunk_mib or recommended_chunk(hardware)
    environment.update(
        {
            "OOT_WORK": str(request.work),
            "OOT_EXEFS": str(exefs),
            "OOT_ROMFS": str(romfs),
            "RX_RELEASE": "1",
            "OCARINA_CHUNK_MIB": str(chunk_mib),
        }
    )
    configure_hot(ROOT, environment)
    write_json(
        request.work / "build-request.json",
        {
            "version": __version__,
            "game_build_id": identity,
            "jobs_requested": request.jobs,
            "chunk_mib_requested": request.chunk_mib,
            "chunk_mib_selected": chunk_mib,
            "cpu_features": cpu_features,
            "march": march,
            "hardware_before_lift": hardware,
            "chunk_policy": "use requested target for new boundaries; preserve existing boundaries",
            "renderer_from_source": request.renderer_from_source,
            "output": str(request.output),
            "tools": str(request.tools),
            "romfs": str(romfs),
        },
    )
    report("@@stage lift Traduzindo o codigo ARM64")
    timing.measure("lift", run,
        [
            sys.executable,
            "-I",
            "-u",
            str(ROOT / "nx2/lift.py"),
            "--standalone",
            "--write",
            "--exefs",
            str(exefs),
            "--work",
            str(request.work),
        ],
        ROOT,
        environment,
        request.work / "logs/lift.log",
        report,
    )
    if has_fresh_hot_source(request.work / "sa/gen"):
        timing.measure("split", run,
            [
                sys.executable,
                "-I",
                "-u",
                str(ROOT / "nx2/split_hot.py"),
                str(request.work / "sa/gen"),
            ],
            ROOT,
            environment,
            request.work / "logs/split.log",
            report,
        )
    else:
        note = "Sem funcoes separadas para otimizacao; compilando os arquivos normais."
        report(note)
        split_log = request.work / "logs/split.log"
        split_log.parent.mkdir(parents=True, exist_ok=True)
        split_log.write_text(note + "\n", encoding="utf-8")
    # Choose automatic parallelism after extraction/lifting have released memory.
    free = available_memory()
    hardware = snapshot()
    hardware["ram_available"] = free
    usable = usable_memory(hardware)
    jobs = compile_jobs(request.jobs, free_bytes=usable, cpus=hardware["logical_cpus"],
                        chunk_mib=chunk_mib)
    plan = read_json(request.work / "build-request.json")
    plan.update(jobs=jobs, available_memory_at_compile=free, cpu_count=os.cpu_count(),
                hardware_at_compile=hardware,
                jobs_mode="automatic" if request.jobs is None else "explicit")
    write_json(request.work / "build-request.json", plan)
    report(f"Compilacao: {jobs} processo(s), modo {plan['jobs_mode']}; "
           f"RAM disponivel {free / (1 << 30):.1f} GiB; "
           f"{hardware['logical_cpus']} threads disponiveis; alvo {chunk_mib} MiB por bloco novo.")
    report(f"@@stage compile Compilando com {jobs} processo(s)")
    progress = CompileProgress()

    def compile_report(line: str) -> None:
        report(line)
        fraction = progress.feed(line)
        if fraction is not None:
            report(f"@@progress {fraction:.6f}")

    timing.measure("compile", run,
        [
            sys.executable,
            "-I",
            "-u",
            str(ROOT / "nx2/build.py"),
            "--standalone",
            "--jobs",
            str(jobs),
        ],
        ROOT,
        environment,
        request.work / "logs/compile.log",
        compile_report,
    )
    report("@@stage finish Conferindo e publicando os arquivos")
    manifest = timing.measure("publish", publish, request, romfs, identity, jobs, started, march)
    report("@@done " + str(request.output))
    return manifest
