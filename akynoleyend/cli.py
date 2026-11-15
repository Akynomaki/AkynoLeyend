"""The public interface for build, prerequisite checks and runtime diagnostics."""

import argparse
from pathlib import Path

from . import __version__
from .build import build
from .game import verify_version, verify_nup
from .config import ROOT, BuildRequest, compile_jobs
from .environment import CACHE_MODES, EXPERIMENTS, PROFILES, TEXTURE_MODES, VISUAL_MODES
from .errors import ProjectError
from .launch import launch
from .crash_report import collect_run
from .preflight import inspect_tools
from .files import read_json
from .romfs import audit_romfs, require_romfs
from .access import FileAccessError, save_access_report
from .shader_prepare import prepare_shaders, update_renderer
from .graphics import RESOLUTIONS, SPEEDS, FILTERS, OUTPUTS, graphics_environment
from .hardware import snapshot, recommended_chunk, shader_workers, usable_memory
import json
from .legacy import organize_project


def absolute(value: str) -> Path:
    return Path(value).expanduser().resolve()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="AkynoLeyend: compilar e diagnosticar uma base independente."
    )
    result.add_argument("--version", action="version", version=__version__)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("hardware", help="Mostra CPU, memoria e plano automatico deste computador.")
    default_tools = ROOT / "ferramentas"
    doctor = commands.add_parser(
        "doctor", help="Verifica as ferramentas sem abrir ou compilar o jogo."
    )
    doctor.add_argument("--tools", type=absolute, default=default_tools)
    doctor.add_argument("--exefs", type=absolute)
    checker = commands.add_parser(
        "check", help="Confere a versao da entrada sem extrair ou compilar."
    )
    sources = checker.add_mutually_exclusive_group(required=True)
    sources.add_argument("--nup", type=absolute)
    sources.add_argument("--exefs", type=absolute)
    compiler = commands.add_parser("build", help="Compila a copia local do jogo.")
    compiler.add_argument("--nup", type=absolute)
    compiler.add_argument("--exefs", type=absolute)
    compiler.add_argument("--romfs", type=absolute)
    compiler.add_argument("--out", type=absolute, default=ROOT / "jogo")
    compiler.add_argument("--work", type=absolute, default=ROOT / "work")
    compiler.add_argument("--tools", type=absolute, default=default_tools)
    compiler.add_argument("--language", default="pt-BR")
    compiler.add_argument("--jobs", type=int)
    compiler.add_argument(
        "--chunk-mib",
        type=int,
        choices=(3, 6, 12, 24),
        default=None,
        help="Alvo dos blocos novos de C; omita para automatico. Limites salvos sao preservados.",
    )
    compiler.add_argument(
        "--renderer-source", action="store_true", help="Recompila tambem o renderizador generico."
    )
    compiler.add_argument(
        "--check",
        action="store_true",
        help="Confere o build ID de --exefs, sem compilar.",
    )
    player = commands.add_parser("run", help="Inicia um build validado e registra os resultados.")
    player.add_argument("--out", type=absolute, default=ROOT / "jogo")
    player.add_argument("--profile", choices=tuple(PROFILES), default="original")
    player.add_argument(
        "--cache-mode",
        choices=tuple(CACHE_MODES),
        default="original",
        help="Streaming/Equilibrado: leitura e pre-aquecimento limitados.",
    )
    player.add_argument(
        "--require-current-build",
        action="store_true",
        default=True,
        help="Recusa EXE/DLL de versao anterior ou de outra revisao dos fontes.",
    )
    player.add_argument(
        "--visual-mode",
        choices=tuple(VISUAL_MODES),
        default="patched",
        help="Correcoes visuais ou comparacao com correcoes desativadas.",
    )
    player.add_argument(
        "--texture-mode",
        choices=tuple(TEXTURE_MODES),
        default="auto",
        help="Comparacao ASTC: auto preserva BC3 elegivel; rgba8 ou cpu-rgba8 dispensam BC3.",
    )
    player.add_argument("--backend", choices=("vulkan", "opengl"), default="vulkan")
    player.add_argument("--resolution", choices=tuple(RESOLUTIONS))
    player.add_argument("--output-resolution", choices=tuple(OUTPUTS))
    player.add_argument("--speed", choices=tuple(SPEEDS))
    player.add_argument("--upscaling", choices=tuple(FILTERS))
    player.add_argument("--sharpness", type=int)
    player.add_argument(
        "--shader-workers",
        type=int,
        choices=range(1, 9),
        help="Threads de compilacao Vulkan, de 1 a 8 (experimental).",
    )
    player.add_argument("--framegen", type=int, choices=(0, 2, 3, 4, 5, 6, 7, 8, 9),
                        help="0 desligada, 2 a 8 fixa, 9 dinamica (segue o monitor; maximo e alvo no menu F1).")
    player.add_argument("--pacing", choices=("on", "off"))
    player.add_argument("--measure", action="store_true",
                        help="Grava a medicao de desempenho na pasta da execucao (tools/resumo_medicao.py resume).")
    player.add_argument("--experiment", choices=tuple(EXPERIMENTS), default="nenhum",
                        help="Teste A/B de desempenho, com --measure.")
    player.add_argument("--fps-counter", choices=("on", "off"))
    player.add_argument("--handheld", choices=("on", "off"))
    player.add_argument(
        "--prepare-again",
        action="store_true",
        help="Repete a preparacao do banco sem apagar caches.",
    )
    player.add_argument("--diagnostic", action="store_true")
    player.add_argument("--dry-run", action="store_true")
    player.add_argument(
        "--short-romfs", action="store_true", help="Testa o runtime com um alias curto de RomFS."
    )
    player.add_argument(
        "--trace-files",
        action="store_true",
        help="Registra arquivos abertos, sem ativar validacao Vulkan.",
    )
    player.add_argument(
        "--trace-runtime",
        action="store_true",
        help="Registra audio e pausas de frames, sem validacao Vulkan.",
    )
    player.add_argument(
        "--trace-lighting",
        action="store_true",
        help="Mede flashes/exposicao sem gravar um video de cada frame.",
    )
    player.add_argument(
        "--audio-backend",
        choices=("auto", "wasapi", "waveout"),
        default="auto",
        help="Saida de audio: WASAPI com fallback automatico, ou um backend explicito.",
    )
    player.add_argument(
        "--collect-crash",
        action="store_true",
        help="Empacota esta execucao e o mapa correspondente ao fechar.",
    )
    player.add_argument("--work", type=absolute, default=ROOT / "work")
    collector = commands.add_parser(
        "collect-crash", help="Empacota a ultima execucao existente, sem abrir ou compilar o jogo."
    )
    collector.add_argument("--out", type=absolute, default=ROOT / "jogo")
    collector.add_argument("--work", type=absolute, default=ROOT / "work")
    audit = commands.add_parser(
        "audit-romfs", help="Confere a raiz dos recursos sem compilar ou abrir o jogo."
    )
    audit.add_argument("--romfs", type=absolute)
    audit.add_argument("--out", type=absolute, default=ROOT / "jogo")
    access = commands.add_parser(
        "audit-access", help="Diagnostica acesso aos arquivos sem abrir ou compilar o jogo."
    )
    access.add_argument("--out", type=absolute, default=ROOT / "jogo")
    update = commands.add_parser(
        "update-renderer", help="Atualiza apenas a DLL Vulkan de um build local compativel."
    )
    update.add_argument("--out", type=absolute, default=ROOT / "jogo")
    update.add_argument("--work", type=absolute, default=ROOT / "work")
    maintain = commands.add_parser("maintain-build", help="Atualiza componentes usando os objetos ja compilados.")
    maintain.add_argument("--out", type=absolute, default=ROOT/"jogo")
    maintain.add_argument("--work", type=absolute, default=ROOT/"work")
    maintain.add_argument("--tools", type=absolute, default=default_tools)
    maintain.add_argument("--jobs", type=int)
    maintain.add_argument("--reuse-game-from", type=absolute, help="Raiz estavel somente em leitura para uma candidata isolada")
    stage_update = commands.add_parser("stage-update", help="Confere e prepara um pacote de atualizacao.")
    stage_update.add_argument("--archive", type=absolute, required=True)
    stage_update.add_argument("--out", type=absolute, default=ROOT/"jogo")
    stage_update.add_argument("--jobs", type=int)
    apply_update = commands.add_parser("apply-update", help="Aplica o pacote depois que a interface fecha.")
    apply_update.add_argument("--plan", type=absolute, required=True)
    apply_update.add_argument("--wait-pid", type=int, default=0)
    dlss = commands.add_parser(
        "dlss-runtime", help="Baixa o runtime do NVIDIA DLSS (nvngx_dlss.dll) depois de aceitar a licenca da NVIDIA."
    )
    dlss.add_argument("--accept-nvidia-license", action="store_true",
                      help="Aceito a licenca NVIDIA RTX SDKs do runtime do DLSS.")
    dlss.add_argument("--status", action="store_true", help="So informa se o runtime ja esta conferido.")
    saves = commands.add_parser(
        "export-saves", help="Traz o save do Ocarina de um emulador (Fritz, MDias, PokeDinner, Lichii) para o port."
    )
    saves.add_argument("--emulator", required=True, choices=("fritz", "mdias", "pokedinner", "lichii"))
    saves.add_argument("--out", type=absolute, default=ROOT / "jogo")
    saves.add_argument("--from", dest="from_dir", type=absolute,
                       help="Pasta do save ou pasta 'user' do emulador portatil, em vez da pasta padrao.")
    saves.add_argument("--profile", help="Perfil do emulador quando mais de um tem save (padrao: o salvo por ultimo).")
    saves.add_argument("--dry-run", action="store_true", help="So mostra o que seria copiado.")
    prepare = commands.add_parser(
        "prepare-shaders", help="Atualiza a DLL e prepara o banco privado de shaders."
    )
    prepare.add_argument("--out", type=absolute, default=ROOT / "jogo")
    prepare.add_argument("--work", type=absolute, default=ROOT / "work")
    prepare.add_argument("--texture-mode", choices=tuple(TEXTURE_MODES), default="auto")
    prepare.add_argument(
        "--shader-workers",
        type=int,
        choices=range(1, 9),
        help="Threads no pre-aquecimento Vulkan (1-8).",
    )
    prepare.add_argument(
        "--force", action="store_true", help="Refaz o banco sem apagar o cache do driver."
    )
    prepare.add_argument(
        "--no-start", action="store_true", help="Prepara os arquivos sem abrir o jogo."
    )
    return result


def main(arguments: list[str] | None = None) -> int:
    args = parser().parse_args(arguments)
    try:
        if args.command == "maintain-build":
            from .maintenance import maintain_build
            maintain_build(args.out, args.work, args.tools, jobs=args.jobs, reuse_game_from=args.reuse_game_from)
            return 0
        if args.command == "stage-update":
            from .updater import stage_update
            plan = stage_update(args.archive, ROOT, args.out, jobs=args.jobs)
            print("@@update_plan " + str(plan), flush=True)
            return 0
        if args.command == "apply-update":
            from .updater import apply_update
            return apply_update(args.plan, args.wait_pid)
        if args.command == "hardware":
            info = snapshot()
            target = recommended_chunk(info)
            info.update(chunk_mib=target, jobs=compile_jobs(None, usable_memory(info),
                        info["logical_cpus"], chunk_mib=target), shader_workers=shader_workers(info))
            print("@@hardware " + json.dumps(info, ensure_ascii=False), flush=True)
            return 0
        if args.command == "check":
            identity = verify_nup(args.nup) if args.nup else verify_version(args.exefs)
            print("@@check ok " + identity, flush=True)
            return 0
        if args.command == "doctor":
            failures = inspect_tools(args.tools)
            if args.exefs:
                print("Build ID:", verify_version(args.exefs))
            hardware = snapshot()
            chunk = recommended_chunk(hardware)
            print("CPU:", hardware["cpu"], "| threads disponiveis:", hardware["logical_cpus"])
            print("RAM total/disponivel (GiB):", round(hardware["ram_total"]/(1 << 30), 1),
                  round(hardware["ram_available"]/(1 << 30), 1))
            print("Processos de compilacao sugeridos:",
                  compile_jobs(None, usable_memory(hardware), hardware["logical_cpus"], chunk_mib=chunk))
            print("Alvo dos blocos novos (MiB):", chunk)
            from .cpu import DEFAULT_MARCH, choose_march, detect as detect_cpu, missing as cpu_missing
            features = detect_cpu(args.tools)
            if features is None:
                print("Instrucoes do processador: nao conferidas.")
            else:
                lacks = cpu_missing(features, DEFAULT_MARCH)
                print("Alvo de compilacao para este processador:", choose_march(features),
                      "" if not lacks else "(sem " + ", ".join(lacks) + ")")
            for failure in failures:
                print("ERRO:", failure)
            if not failures:
                print("Ferramentas verificadas. Isso nao constitui um teste do jogo ou da GPU.")
            return int(bool(failures))
        if args.command == "collect-crash":
            try:
                print("Diagnostico para compartilhar:", collect_run(args.out, args.work))
            except OSError as error:
                raise ProjectError(f"Nao foi possivel coletar o diagnostico: {error}") from error
            return 0
        if args.command == "audit-access":
            archive, good = save_access_report(args.out, windows_details=True)
            print("Diagnostico de acesso para compartilhar:", archive, flush=True)
            print(
                "Leitura inicial OK; use Jogar para validar os hashes."
                if good
                else "Ha arquivo ausente, bloqueado ou no formato errado. Veja acesso.txt no ZIP."
            )
            return int(not good)
        if args.command == "dlss-runtime":
            from .dlss_runtime import NOTICE, fetch, installed, runtime_directory
            if args.status:
                found = installed()
                print("DLSS: runtime conferido em %s" % found if found else
                      "DLSS: runtime ausente em %s" % runtime_directory(), flush=True)
                return 0 if found else 1
            print(NOTICE, flush=True)
            print("DLSS: pronto em", fetch(args.accept_nvidia_license), flush=True)
            return 0
        if args.command == "export-saves":
            from .saves import export_saves
            export_saves(args.emulator, args.out, source=args.from_dir, profile=args.profile, dry_run=args.dry_run,
                         report=lambda line: print(line, flush=True))
            return 0
        if args.command == "update-renderer":
            update_renderer(args.out, args.work)
            organize_project(ROOT)
            return 0
        if args.command == "prepare-shaders":
            return prepare_shaders(
                args.out,
                args.work,
                texture_mode=args.texture_mode,
                force=args.force,
                start_game=not args.no_start,
                shader_workers=args.shader_workers,
            )
        if args.command == "audit-romfs":
            root = args.romfs
            if root is None:
                root = absolute(read_json(args.out / "AkynoLeyend-build.json")["romfs"])
            print("\n".join(audit_romfs(root)))
            require_romfs(root)
            return 0
        if args.command == "build":
            if args.check:
                if bool(args.nup) == bool(args.exefs):
                    raise ProjectError(
                        "Informe --nup ARQUIVO ou --exefs PASTA para conferir a versao."
                    )
                identity = verify_nup(args.nup) if args.nup else verify_version(args.exefs)
                print("@@check ok " + identity, flush=True)
                return 0
            request = BuildRequest(
                output=args.out,
                chunk_mib=args.chunk_mib,
                renderer_from_source=args.renderer_source,
                work=args.work,
                tools=args.tools,
                nup=args.nup,
                exefs=args.exefs,
                romfs=args.romfs,
                language=args.language,
                jobs=args.jobs,
            )
            build(request)
            return 0
        graphics_environment(
            backend=args.backend,
            resolution=args.resolution,
            output_resolution=args.output_resolution,
            speed=args.speed,
            upscaling=args.upscaling,
            sharpness=args.sharpness,
            framegen=args.framegen,
            pacing=None if args.pacing is None else args.pacing == "on",
            fps_counter=None if args.fps_counter is None else args.fps_counter == "on",
            handheld=None if args.handheld is None else args.handheld == "on",
        )
        return launch(
            args.out,
            args.profile,
            args.diagnostic,
            args.dry_run,
            short_paths=args.short_romfs,
            trace_files=args.trace_files,
            trace_runtime=args.trace_runtime,
            audio_backend=args.audio_backend,
            trace_lighting=args.trace_lighting,
            backend=args.backend,
            resolution=args.resolution,
            output_resolution=args.output_resolution,
            speed=args.speed,
            upscaling=args.upscaling,
            sharpness=args.sharpness,
            framegen=args.framegen,
            pacing=None if args.pacing is None else args.pacing == "on",
            fps_counter=None if args.fps_counter is None else args.fps_counter == "on",
            handheld=None if args.handheld is None else args.handheld == "on",
            cache_mode=args.cache_mode,
            texture_mode=args.texture_mode,
            visual_mode=args.visual_mode,
            require_current_build=args.require_current_build,
            shader_workers=args.shader_workers,
            prepare_again=args.prepare_again,
            collect_crash=args.collect_crash,
            work=args.work,
            measure=args.measure,
            experiment=args.experiment,
        )
    except ProjectError as error:
        if isinstance(error, FileAccessError) and not getattr(error, "diagnostic_archive", None):
            try:
                archive, _ = save_access_report(args.out, failure=error)
                print("Diagnostico de acesso para compartilhar:", archive, flush=True)
            except (OSError, ProjectError) as report_error:
                print("Nao foi possivel salvar o diagnostico:", report_error, flush=True)
        print("@@error " + str(error), flush=True)
        return 1
    except OSError as error:
        target = Path(error.filename) if error.filename else getattr(args, "out", ROOT)
        failure = FileAccessError(target, error, "acessar")
        if args.command in {"run", "update-renderer", "prepare-shaders"}:
            try:
                archive, _ = save_access_report(args.out, failure=failure)
                print("Diagnostico de acesso para compartilhar:", archive, flush=True)
            except (OSError, ProjectError) as report_error:
                print("Nao foi possivel salvar o diagnostico:", report_error, flush=True)
        print("@@error " + str(failure), flush=True)
        return 1
    except KeyboardInterrupt:
        print("Compilacao interrompida. Os dados de entrada foram preservados.")
        return 130
