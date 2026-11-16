"""Launch only a complete build, with a unique diagnostic record per run."""

from contextlib import nullcontext
import datetime as dt
import os
import subprocess
from pathlib import Path

from . import __version__
from .coherence import require_host, compatible_previous_host
from .hardware import (snapshot, shader_workers as automatic_shader_workers, exit_explanation, low_ram_notice,
                       PLAY_RAM_FREE, heavy_processes, play_ram_notice)
from .config import MANIFEST, ROOT
from .cpu import ILLEGAL_INSTRUCTION_EXIT, build_march, detect as detect_cpu, illegal_instruction_message, launch_refusal
from .crash_report import collect_run
from .windows_paths import short_romfs
from .environment import CACHE_MODES, PROFILES, TEXTURE_MODES, VISUAL_MODES, runtime_environment
from .errors import ProjectError
from .files import read_json, sha256, write_json
from .romfs import require_romfs
from .access import FileAccessError, regular_file, save_access_report
from .runtime_failure import (
    DEVICE_LOST_EXIT,
    VIRTUAL_MEMORY_MESSAGE,
    low_memory_notice,
    memory_failure,
    renderer_failure,
    system_commit_mb,
)
from .graphics import (EXTENDED_OUTPUT_FEATURE, EXPERIMENTAL_SCALES, TEMPORAL, graphics_environment,
                       has_fixed_scale_hook, saved_temporal_options)
from .fsr_sdk import HOST_FEATURE as FSR_HOST_FEATURE, sdk_directory


CLOSED_LINE = b"display: window closed, exiting"
EXIT_GRACE_SECONDS = 20


def wait_game(child, log: Path, grace: float = EXIT_GRACE_SECONDS, poll: float = 1.0):
    """The game's exit status, and how long it was left after its window closed when it did not end by itself.

    A closed window makes the game write its log and call ExitProcess. Seen with the DLSS runtime loaded (2 of 3 runs,
    none of the others): the process then stayed alive in Windows' unloading of the DLLs, for over 90 s once and over
    10 minutes once, holding its memory. Nothing of the game runs at that point, so once the log has that line and
    `grace` seconds have passed, the process is ended here and the run counts as the exit the game asked for."""
    seen_at = None
    offset = 0
    while True:
        try:
            return child.wait(timeout=poll), None
        except subprocess.TimeoutExpired:
            pass
        now = dt.datetime.now().timestamp()
        if seen_at is None:
            try:
                with log.open("rb") as stream:
                    stream.seek(max(0, offset - len(CLOSED_LINE)))
                    data = stream.read()
                    offset = stream.tell()
            except OSError:
                data = b""
            if CLOSED_LINE in data:
                seen_at = now
        elif now - seen_at >= grace:
            child.kill()
            child.wait()
            return 0, {"seconds": grace, "after": CLOSED_LINE.decode()}


def snapshot_options(folder: Path, logs: Path, phase: str) -> dict:
    """Keep the small menu config with this run; never edit the user's options."""
    try:
        with (folder / "AkynoLeyend_opts.ini").open("rb") as source:
            data = source.read((64 << 10) + 1)
        if len(data) > 64 << 10:
            return {"status": "too_large"}
        name = f"opcoes-{phase}.ini"
        (logs / name).write_bytes(data)
        return {"status": "saved", "file": name}
    except FileNotFoundError:
        return {"status": "absent"}
    except OSError as error:
        return {"status": "unavailable", "error": str(error)}


def verify_build(folder: Path) -> dict:
    manifest_path = folder / MANIFEST
    try:
        regular_file(manifest_path)
    except FileAccessError as error:
        if not isinstance(error.original, FileNotFoundError):
            raise
        raise ProjectError(
            "O jogo ainda nao foi compilado nesta pasta. Execute Compilar.cmd e aguarde @@done "
            "antes de abrir Jogar.cmd. Se escolheu outro destino, use Jogar.cmd --out PASTA."
        ) from error
    manifest = read_json(manifest_path)
    if manifest.get("schema") != 1 or manifest.get("project") != "AkynoLeyend":
        raise ProjectError("Esta pasta nao foi produzida pela base AkynoLeyend.")
    hashes = manifest.get("files", {})
    if not isinstance(hashes, dict):
        raise ProjectError("Manifesto de arquivos invalido; confira a pasta do jogo.")
    for name in ("AkynoLeyend.exe", "AkynoLeyend.dll", "image.bin"):
        path = folder / name
        if not isinstance(hashes.get(name), str):
            raise ProjectError(f"Manifesto sem hash de {name}; compilacao incompleta.")
        regular_file(path)
        try:
            actual = sha256(path)
        except OSError as error:
            raise FileAccessError(path, error, "ler para conferir o SHA-256 de") from error
        if actual != hashes[name]:
            raise ProjectError(
                f"Build incompleto ou arquivo alterado: {name}. Recompile antes de executar."
            )
    romfs = Path(manifest.get("romfs", ""))
    if not romfs.is_absolute():
        raise ProjectError(
            "A pasta romfs original nao esta disponivel no caminho registrado. Recompile apontando para ela."
        )
    require_romfs(romfs)
    return manifest


def checked_build(folder: Path) -> dict:
    try:
        manifest = verify_build(folder)
    except FileAccessError as error:
        # This is a pre-launch failure, not a new game session or a GPU crash.
        try:
            archive, _ = save_access_report(folder, failure=error)
            error.diagnostic_archive = archive
            print("Diagnostico de acesso para compartilhar:", archive, flush=True)
        except (ProjectError, OSError) as report_error:
            print("Nao foi possivel salvar o diagnostico de acesso:", report_error, flush=True)
        raise
    return manifest


def launch(
    folder: Path,
    profile: str = "original",
    diagnostic: bool = False,
    dry_run: bool = False,
    *,
    short_paths: bool = False,
    trace_files: bool = False,
    trace_runtime: bool = False,
    trace_lighting: bool = False,
    audio_backend: str = "auto",
    cache_mode: str = "original",
    texture_mode: str = "auto",
    visual_mode: str = "patched",
    require_current_build: bool = False,
    prepare_again: bool = False,
    collect_crash: bool = False,
    work: Path | None = None,
    backend: str = "vulkan",
    resolution: str | None = None,
    output_resolution: str | None = None,
    speed: str | None = None,
    upscaling: str | None = None,
    sharpness: int | None = None,
    framegen: int | None = None,
    pacing: bool | None = None,
    shader_workers: int | None = None,
    fps_counter: bool | None = None,
    handheld: bool | None = None,
    lite_scene: bool | None = None,
    auto_prepare: bool = True,
    measure: bool = False,
    experiment: str = "nenhum",
) -> int:
    graphics_options = dict(
        backend=backend,
        resolution=resolution,
        output_resolution=output_resolution,
        speed=speed,
        upscaling=upscaling,
        sharpness=sharpness,
        framegen=framegen,
        pacing=pacing,
        fps_counter=fps_counter,
        handheld=handheld,
        lite_scene=lite_scene,
    )
    graphics = graphics_environment(**graphics_options)
    if profile == "compatibilidade":
        trace_runtime = True
    manifest = checked_build(folder)
    if require_current_build:
        from .build import source_identity
        current_source = source_identity()
        current = manifest.get("version") == __version__ and manifest.get("source_sha256") == current_source
        compatible = compatible_previous_host(manifest)
        updated_previous = (compatible and manifest.get("renderer_version") == __version__
                            and manifest.get("runtime_source_sha256") == current_source)
        if not current and not updated_previous and not dry_run and compatible:
            from .maintenance import maintain_build
            print("Atualizando componentes compativeis antes de jogar; compilacao existente sera reaproveitada.", flush=True)
            manifest = maintain_build(folder, work or ROOT/"work", ROOT/"ferramentas")
            current = manifest.get("version") == __version__ and manifest.get("source_sha256") == current_source
            updated_previous = (compatible_previous_host(manifest) and manifest.get("renderer_version") == __version__
                                and manifest.get("runtime_source_sha256") == current_source)
        if not current and not updated_previous:
            raise ProjectError(
                "Este EXE/DLL nao corresponde aos fontes atuais. "
                "Se este e o Teste 1, use Ferramentas > Atualizar AkynoLeyend. "
                "Outras revisoes precisam de Criar/Compilar.cmd."
            )
        require_host(manifest)
    # (r13j) a build compiled for instructions this CPU lacks stops at once with 0xC000001D: said here, before it starts
    refusal = launch_refusal(manifest, ROOT / "ferramentas", snapshot().get("cpu", ""))
    if refusal:
        raise ProjectError(refusal)
    if output_resolution == "1080p" and "fullhd-video-budget-v1" not in manifest.get("host_features", []):
        raise ProjectError("Full HD exige o runtime atualizado. Use Atualizar build ou Aplicar componentes instalados no launcher.")
    has_jitter = FSR_HOST_FEATURE in manifest.get("host_features", [])
    if upscaling is None and has_jitter:
        saved_mode, saved_scale = saved_temporal_options(folder, resolution)
        if saved_mode:
            upscaling, resolution = saved_mode, saved_scale
            graphics_options.update(upscaling=upscaling, resolution=resolution)
            graphics = graphics_environment(**graphics_options)
    if has_jitter:
        graphics["AKYNO_TEMPORAL_MENU"] = "1"
    if EXTENDED_OUTPUT_FEATURE in manifest.get("host_features", []):
        graphics["AKYNO_EXTENDED_OUTPUTS"] = "1"
    elif output_resolution in ("720p", "1600p"):
        raise ProjectError("720p e 2560×1600 exigem o host com os guardas de resolução. Instale a correção r9 em Atualizações.")
    if upscaling in TEMPORAL:
        if not has_jitter:
            raise ProjectError("FSR temporal, DLSS e DLAA exigem uma build gerada com os tres hooks de jitter da camera. Prepare-a com Criar e preserve o cache de objetos.")
        if TEMPORAL[upscaling][0] != "dlss":
            graphics["AKYNO_FSR_SDK_DIR"] = str(sdk_directory())
        else:
            from .dlss_runtime import installed, runtime_directory
            found = installed()
            if found:
                graphics["AKYNO_DLSS_DIR"] = str(found)
            else:
                print("NVIDIA DLSS: runtime ausente em %s. O jogo usara a ampliacao do proprio jogo com FSR 1. "
                      "Use 'Baixar DLSS da NVIDIA' no launcher (ou manage.py dlss-runtime) para aceitar a licenca e baixar."
                      % runtime_directory(), flush=True)
    if has_jitter and "AKYNO_FSR_SDK_DIR" not in graphics:
        try:
            graphics["AKYNO_FSR_SDK_DIR"] = str(sdk_directory())
        except ProjectError:
            pass   # spatial filters and NVIDIA's path work without the optional AMD pair
    if resolution in EXPERIMENTAL_SCALES:
        # Do not silently claim 125/150 on an EXE that cannot even read the
        # fixed-scale variable. This check is deliberately conservative.
        if not has_fixed_scale_hook(folder / "AkynoLeyend.exe"):
            raise ProjectError(
                "Este AkynoLeyend.exe nao contem o suporte nativo HOS_RES_SCALE. "
                "A opcao 125/150 nao sera aplicada: recompile o jogo pelo Builder "
                "com os fontes atualizados e sua entrada original. "
                "Nunca sobrescreva o EXE do jogo sem conferir seu manifesto."
            )
    if audio_backend not in {"auto", "wasapi", "waveout"}:
        raise ProjectError(f"Saida de audio desconhecida: {audio_backend}")
    environment = runtime_environment(
        os.environ, profile, diagnostic, cache_mode=cache_mode, texture_mode=texture_mode,
        measure=measure, experiment=experiment,
    )
    environment.update(graphics)
    if visual_mode not in VISUAL_MODES:
        raise ProjectError(f"Modo visual desconhecido: {visual_mode}")
    environment.update(VISUAL_MODES[visual_mode])
    if shader_workers is not None:
        if type(shader_workers) is not int or not 1 <= shader_workers <= 8:
            raise ProjectError("Workers de shaders devem estar entre 1 e 8.")
        environment["RX_VK_COMPILE_THREADS"] = str(shader_workers)
    elif profile != "rtx-1600" or cache_mode != "equilibrado":
        info = snapshot()
        background = cache_mode in {"streaming", "equilibrado"}
        environment["RX_VK_COMPILE_THREADS"] = str(automatic_shader_workers(info, background=background))
    if audio_backend != "auto":
        environment["HOS_AUDIO_BACKEND"] = audio_backend
    if trace_files:
        environment["HOS_FS_TRACE"] = "1"
    if trace_runtime:
        environment["HOS_AUDIO_STATS"] = "1"
        environment["HOS_VIDEO_LOG"] = "1"
        environment["RX_VK_SLOW_LOG"] = "25"
        environment["RX_VK_FAULT_BREADCRUMBS"] = "1"
    if prepare_again:
        environment["RX_VK_PREPARE_AGAIN"] = "1"
    if not dry_run and cache_mode != "preparacao" and "controller-prompts-v1" in manifest.get("host_features", []):
        from .prompts import prepare_prompts
        prepare_prompts(folder, manifest["romfs"])
    if auto_prepare and cache_mode != "preparacao":
        environment["RX_VK_SEED_PREPARE"] = "1"
        environment["AKYNO_LAUNCHER_PROGRESS"] = "1"
        if not dry_run:
            from .shader_prepare import prepare_shaders
            print("@@stage shaders Conferindo e preparando shaders automaticamente", flush=True)
            prepare_shaders(folder, work or ROOT / "work", start_game=False, verified_manifest=manifest)
    command = [
        str(folder / "AkynoLeyend.exe"),
        str(folder / "image.bin"),
        "--romfs",
        manifest["romfs"],
        "--user",
        str(folder / "user"),
    ]
    print("Perfil:", profile, "(validacao ativa)" if diagnostic else "")
    print("Modo de cache:", cache_mode)
    print("Modo de texturas:", texture_mode)
    print("Modo visual:", visual_mode, "(comparacao de regressao)" if visual_mode == "comparison" else "")
    if measure:
        print("Medicao de desempenho: ligada; experimento:", experiment,
              "| resumo depois: tools\\resumo_medicao.py <pasta da execucao>", flush=True)
    print("Renderizador:", backend, "| opcoes graficas:", graphics or "salvas no jogo")
    if resolution in EXPERIMENTAL_SCALES:
        print(
            f"Escala interna solicitada: {resolution}% (HOS_RES_SCALE={EXPERIMENTAL_SCALES[resolution]}; "
            "menu Insert identifica a escala experimental). O marcador nativo foi localizado no EXE, "
            "mas esta verificacao NAO mede pixels nem garante que o patch Max Resolution "
            "de outro emulador esteja presente. Procure 'vi: fixed scale active' no saida.log "
            "apos os primeiros quadros; se ausente, recompile o host.",
            flush=True,
        )
    if texture_mode != "auto":
        print(
            "Comparacao ASTC sem BC3: as texturas elegiveis podem ocupar ate 4x a memoria. "
            "Isso nao e um teto global de VRAM nem uma correcao confirmada de flashes.",
            flush=True,
        )
    print("Executavel SHA-256:", manifest["files"]["AkynoLeyend.exe"])
    built_version = manifest.get("version")
    if built_version and built_version != __version__:
        if manifest.get("renderer_version") == __version__:
            print(
                f"Runtime EXE: {built_version}; renderizador/lancador: {__version__}. "
                "A atualizacao da DLL ja foi aplicada, sem recompilar o C do jogo.",
                flush=True,
            )
        else:
            print(
                f"Motor compilado: {built_version}; lancador: {__version__}. "
                "suporte/Atualizar-Renderizador.cmd aplica a DLL nova em builds compativeis; Criar atualiza o conjunto completo.",
                flush=True,
            )
    for key, value in PROFILES[profile].items():
        print(f"  {key}={value}")
    for key in CACHE_MODES[cache_mode]:
        print(f"  {key}={environment[key]}")
    for key, value in TEXTURE_MODES[texture_mode].items():
        print(f"  {key}={value}")
    if dry_run:
        print("Verificacao concluida; o jogo nao foi iniciado.")
        return 0
    if os.name != "nt":
        raise ProjectError("O jogo requer Windows x64.")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    logs = folder / "diagnosticos" / f"{stamp}-{os.getpid()}"
    logs.mkdir(parents=True)
    if measure:   # (0.4.5-test.2: each game frame's time, float ms; tools/resumo_medicao.py)
        environment["AKYNO_FRAMETIMES"] = str(logs / "quadros.bin")
    if trace_lighting:
        # Existing native exposure/flash probes, without recording every frame to disk.
        metrics = logs / "luzes-frames.bin"
        environment["RX_VK_FRAMELOG"] = str(metrics)
        environment["RX_VK_FRAMELOG_DROP"] = "1"
        environment["RX_VK_EXPOSURE_LOG"] = "1"
        Path(str(metrics) + ".go").write_text("metrics only\n", encoding="ascii")
    metadata = {
        "launcher_version": __version__,
        "profile": profile,
        "cache_mode": cache_mode,
        "texture_mode": texture_mode,
        "visual_mode": visual_mode,
        "require_current_build": require_current_build,
        "graphics": {
            "backend": backend,
            "resolution": resolution,
            "output_resolution": output_resolution,
            "speed": speed,
            "upscaling": upscaling,
            "sharpness": sharpness,
            "framegen": framegen,
            "pacing": pacing,
            "fps_counter": fps_counter,
            "handheld": handheld,
            "lite_scene": lite_scene,
        },
        "prepare_again": prepare_again,
        "auto_prepare": auto_prepare,
        "measure": measure,
        "experiment": experiment,
        "prepare_only": cache_mode == "preparacao",
        "diagnostic": diagnostic,
        "trace_files": trace_files,
        "trace_runtime": trace_runtime,
        "trace_lighting": trace_lighting,
        "audio_backend": audio_backend,
        "short_romfs": short_paths,
        "runtime_helper": "paths-audio-2",
        "started": dt.datetime.now().astimezone().isoformat(),
        "command": command,
        "build": manifest,
        "resolution_override_check": (
            {"requested_scale": EXPERIMENTAL_SCALES[resolution],
             "exe_has_HOS_RES_SCALE_literal": True,
             "visual_result_verified": False,
             "other_emulator_max_resolution_mod": False}
            if resolution in EXPERIMENTAL_SCALES else None
        ),
        "environment": {
            key: value
            for key, value in environment.items()
            if key.startswith(("RX_", "HOS_", "VK_", "EDEN_", "AKYNO_"))
        },
    }
    metadata["graphics_options_before"] = snapshot_options(folder, logs, "inicio")
    write_json(logs / "execucao.json", metadata)
    print("Registros desta execucao:", logs)
    commit = system_commit_mb()
    if commit:
        metadata["commit_before"] = {"free_mb": commit[0], "limit_mb": commit[1]}
        notice = low_memory_notice(*commit)
        if notice:
            print(notice, flush=True)
    # (0.4.4, from the r13e branch) little RAM free before a shader preparation: it can take hours
    machine = snapshot()
    preparing = cache_mode == "preparacao" or bool(prepare_again)
    notice = low_ram_notice(machine, preparing=preparing)
    if notice:
        metadata["ram_free_mb_before"] = machine["ram_available"] >> 20
        print(notice, flush=True)
    elif cache_mode != "preparacao" and machine.get("ram_total") and machine["ram_available"] < PLAY_RAM_FREE:
        # (r13k: short of RAM for playing; the programs holding it named, as they are the cause, not the game)
        heavy = heavy_processes()
        notice = play_ram_notice(machine, heavy)
        if notice:
            metadata["ram_free_mb_before"] = machine["ram_available"] >> 20
            metadata["heavy_processes"] = [{"name": name, "private_mb": size >> 20} for name, size in heavy]
            print(notice, flush=True)
    with (
        (logs / "saida.log").open("wb") as output,
        (logs / "erros.log").open("wb") as errors,
    ):
        try:
            alias = (
                short_romfs(manifest["romfs"]) if short_paths else nullcontext(manifest["romfs"])
            )
            with alias as runtime_romfs:
                command[3] = runtime_romfs
                metadata["runtime_romfs"] = runtime_romfs
                write_json(logs / "execucao.json", metadata)
                if short_paths:
                    print(
                        "RomFS com caminho curto:",
                        runtime_romfs,
                        "(arquivos originais preservados)",
                        flush=True,
                    )
                child = subprocess.Popen(
                    command, cwd=folder, env=environment, stdout=output, stderr=errors
                )
                metadata["child_pid"] = child.pid
                write_json(logs / "execucao.json", metadata)
                try:
                    status, stalled = wait_game(child, logs / "erros.log")
                except KeyboardInterrupt:
                    child.terminate()
                    status = child.wait()
                    stalled = None
                if stalled is not None:
                    metadata["exit_stalled_after_close"] = stalled
                    print(f"O jogo fechou a janela e gravou o registro, mas o processo nao terminou em {stalled['seconds']} s; "
                          "o launcher o encerrou (nada do jogo ficou aberto).", flush=True)
        except (OSError, ProjectError) as error:
            metadata["launch_error"] = str(error)
            write_json(logs / "execucao.json", metadata)
            raise ProjectError(f"Nao foi possivel abrir o jogo: {error}") from error
    metadata["process_exit_code"] = status
    failure = renderer_failure(logs / "erros.log")
    if not failure and status == DEVICE_LOST_EXIT:
        # (r13d) 70 is only the renderer's own exit for a lost device (vk_replay.cpp); hosts before r13d lost its log line
        failure = {"kind": "device_lost", "exit_code": DEVICE_LOST_EXIT,
                   "evidence": "process exit code 70 (vk: GPU_FATAL device_lost); the log line is missing"}
    if failure:
        metadata["runtime_failure"] = failure
        if failure["kind"] == "device_lost":
            # Older renderers could lose the GPU, keep a black window alive,
            # and return zero when the user finally closed it.
            if status == 0:
                status = DEVICE_LOST_EXIT
            print(
                "Falha do renderizador: o dispositivo Vulkan foi perdido (device lost). "
                "A tela preta nao foi uma execucao concluida com sucesso. "
                "Os registros desta tentativa foram preservados.",
                flush=True,
            )
    memory = None if failure else memory_failure(logs / "erros.log", status)
    if memory:
        metadata["runtime_failure"] = memory
    illegal = None
    if not failure and not memory and isinstance(status, int) and status & 0xFFFFFFFF == ILLEGAL_INSTRUCTION_EXIT:
        # (r13j) 0xC000001D: an instruction the CPU does not run (cpu.py); which ones it lacks, from CPUID
        features = detect_cpu(ROOT / "ferramentas")
        march = build_march(manifest)
        illegal = illegal_instruction_message(snapshot().get("cpu", ""), march, features)
        metadata["runtime_failure"] = {"kind": "illegal_instruction", "exit_code": ILLEGAL_INSTRUCTION_EXIT,
                                       "march": march, "cpu_features": features}
    metadata.update({"exit_code": status, "finished": dt.datetime.now().astimezone().isoformat()})
    metadata["graphics_options_after"] = snapshot_options(folder, logs, "fim")
    write_json(logs / "execucao.json", metadata)
    print("Codigo de encerramento:", status, f"({status & 0xFFFFFFFF:#010x})")
    # (0.4.4, from the r13e branch: 0xC000013A, the console closed or the process cancelled. A renderer, memory or CPU failure
    # keeps its own reason)
    explanation = "" if memory or failure or illegal else exit_explanation(status, preparing=preparing)
    if explanation:
        print("@@error " + explanation, flush=True)
    if memory:
        figures = ""
        if "commit_limit_mb" in memory:
            figures = (f" (no fim: {memory['commit_used_mb']} MB usados de {memory['commit_limit_mb']} MB do sistema; "
                       f"o jogo com {memory['process_private_mb']} MB)")
        # (@@error: the line the interface shows as the reason of the failure)
        likely = "" if memory["refused_commit"] else "Provavel causa (o commit do sistema estava no limite): "
        print("@@error " + likely + VIRTUAL_MEMORY_MESSAGE + figures, flush=True)
    if illegal:
        print("@@error " + illegal, flush=True)
    if status == 0 and cache_mode == "preparacao":
        print("Preparacao de shaders concluida. Use Jogar.cmd para iniciar a partida.", flush=True)
    if collect_crash:
        try:
            archive = collect_run(folder, work or ROOT / "work", logs)
            print("Diagnostico para compartilhar:", archive, flush=True)
        except (OSError, ProjectError) as error:
            print("Nao foi possivel empacotar o diagnostico:", error, flush=True)
    return status
