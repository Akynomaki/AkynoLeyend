"""Update a pinned compatible build using its generated files and existing object cache."""
from contextlib import contextmanager
from pathlib import Path
import shutil
import sys
import time

from . import __version__
from .build import publish, source_identity
from .coherence import R9_HOST_SOURCES, compatible_previous_host, require_host
from .config import ROOT, MANIFEST, BuildRequest, compile_jobs
from .cpu import DEFAULT_MARCH, build_march, detect as detect_cpu, supports, unsupported_message
from .errors import ProjectError
from .files import read_json, sha256, write_json, workspace_lock, workspace_stage
from .graphics import EXTENDED_OUTPUT_FEATURE
from .hardware import snapshot, usable_memory
from .hot import configure_hot
from .launch import checked_build
from .power import keep_awake
from .preflight import require_tools
from .process import run
from nx2.oot_output_size import OUTPUT_SITES_STAMP, extended_output_emitted


RENDERER_MISMATCH = ("O renderizador pronto deste pacote nao corresponde a esta instalacao (fontes, dependencias "
                     "ou SDK). A atualizacao foi interrompida sem compilar o renderizador; os arquivos anteriores "
                     "sao restaurados. Jogo, objetos e saves preservados.")


def require_ready_renderer(root: Path, tools: Path, environment) -> Path:
    """Maintenance never builds the renderer: only the package's verified DLL is accepted."""
    from .prebuilt import renderer_prebuilt
    deps = Path(environment.get("OCARINA_DEPS") or tools / "deps")
    ready = renderer_prebuilt(root, deps, Path(environment.get("OCARINA_PREBUILT_DIR") or tools / "prebuilt"),
                              environment, lambda _: None)
    if ready is None:
        raise ProjectError(RENDERER_MISMATCH)
    return ready


STEP_STAMP = "akyno-frame-step-v1"   # (nx2/upgrade_output.py: the step hook was checked in this work)
HOOKS_STAMP = "akyno-panel-hooks-r13-v5"   # (nx2/upgrade_output.py: the r13 panel hooks are all in this work)


def host_implements_stubbed(work: Path) -> bool:
    """(r12) a64_stubs.c still stubs an import host/ now defines (the HLE forms nx2/standalone.py implemented() reads): a
    duplicate symbol at the link until nx2/upgrade_output.py makes the stubs again from the lift's metadata"""
    import re
    stubs = work / "sa/gen/a64_stubs.c"
    if not stubs.is_file():
        return False
    stubbed = set(re.findall(r"^void (imp_\w+)\(Ctx", stubs.read_text(encoding="utf-8", errors="replace"), re.M))
    defined = set()
    for source in (ROOT / "host").glob("*.c"):
        text = source.read_text(encoding="utf-8", errors="replace")
        defined |= set(re.findall(r"^void (imp_\w+)\(Ctx", text, re.M))
        defined |= {"imp_" + n for n in re.findall(r"^HLE\((\w+)\)", text, re.M)}
    return bool(stubbed & defined)


@contextmanager
def upgrade_output_sites(work, environment, processes, report, step_only=False):
    gen = work / "sa/gen"
    had_stamp = (gen / OUTPUT_SITES_STAMP).is_file()
    had_step = (gen / STEP_STAMP).is_file()
    had_hooks = (gen / HOOKS_STAMP).is_file()
    with workspace_stage(prefix=".output-upgrade-", dir=work) as staging:
        try:
            report("@@stage compile Atualizando os ganchos do painel F1 e os imports do host" if step_only else
                   "@@stage compile Atualizando as dimensoes do jogo nos blocos traduzidos afetados")
            command = [sys.executable, "-I", "-u", str(ROOT/"nx2/upgrade_output.py"),
                       "--staging", str(staging), "--jobs", str(processes)] + (["--step-only"] if step_only else [])
            run(command, ROOT, environment, work/"logs/output-upgrade.log", report)
            yield
        except BaseException:
            if (staging / "ready").is_file():
                for previous in (staging / "gen").iterdir():
                    previous.replace(gen / previous.name)
                    for suffix in (".o", ".o.sha256"):
                        name = previous.stem + suffix
                        output = work / "sa/build/obj" / name
                        saved = staging / "obj" / name
                        if saved.is_file():
                            saved.replace(output)
                        else:
                            output.unlink(missing_ok=True)
            if not had_stamp:
                (gen / OUTPUT_SITES_STAMP).unlink(missing_ok=True)
            if not had_step:
                (gen / STEP_STAMP).unlink(missing_ok=True)
            if not had_hooks:
                (gen / HOOKS_STAMP).unlink(missing_ok=True)
            raise


def maintain_build(folder: Path, work: Path, tools: Path, *, jobs=None, report=print, reuse_game_from=None):
    if reuse_game_from is not None:
        previous_root = Path(reuse_game_from).resolve()
        stable_work, stable_game = previous_root / "work", previous_root / "jogo"
        for candidate, stable in ((work.resolve(), stable_work), (folder.resolve(), stable_game)):
            if candidate == stable or candidate in stable.parents or stable in candidate.parents:
                raise ProjectError("Reuso isolado exige jogo e work independentes da instalacao estavel.")
    with workspace_lock(work), keep_awake():
        manifest = checked_build(folder)
        identity = source_identity()
        if manifest.get("version") == __version__ and manifest.get("source_sha256") == identity:
            report("Build ja atualizado; nenhum compilador iniciado.")
            return manifest
        if not compatible_previous_host(manifest):
            raise ProjectError("Este build nao tem uma revisao gerada compativel conhecida para atualizacao. Use Criar com sua entrada local.")
        require_host(manifest)
        gen = work / "sa/gen"
        required = ["a64_table.c", "a64_hooks.c", "a64_suyu.c", "a64_stubs.c", "hos_image.c", "nvn2_exports.c"]
        if not all((gen/name).is_file() for name in required) or not list(gen.glob("code_*.c")):
            raise ProjectError("Os fontes gerados em work/sa/gen foram removidos. Restaure a pasta work correspondente ou use Criar; saves preservados.")
        image = work / "sa/image/image.bin"
        if not image.is_file() or sha256(image) != manifest["files"]["image.bin"]:
            raise ProjectError("A imagem de work nao corresponde ao jogo instalado. Nenhuma atualizacao aplicada.")
        plan = read_json(work / "build-request.json")
        if plan.get("game_build_id") != manifest.get("game_build_id") or Path(plan.get("output", "")).resolve() != folder.resolve():
            raise ProjectError("A pasta work pertence a outra compilacao ou pasta de saida. Nenhum arquivo do jogo foi alterado.")
        if reuse_game_from is not None:
            previous_root = Path(reuse_game_from).resolve()
            previous = checked_build(previous_root / "jogo")
            fields = ("version", "source_sha256", "game_build_id", "host_revision")
            if any(previous.get(k) != manifest.get(k) for k in fields) or previous.get("files") != manifest.get("files"):
                raise ProjectError("A candidata nao corresponde a instalacao escolhida para reuso em leitura.")
            if work.resolve() == previous_root / "work" or previous_root / "work" in work.resolve().parents:
                raise ProjectError("Reuso isolado nao pode escrever na work estavel.")
        report("@@stage read Conferindo atualizacao compativel")
        environment = require_tools(tools)
        environment.update({"OOT_WORK": str(work), "RX_RELEASE": "1",
                            "OCARINA_HELPER_CACHE": str(work/"helpers"),
                            "OCARINA_PREBUILT_DIR": str(tools/"prebuilt"),
                            "OCARINA_BUILD_RENDERER": "0"})
        configure_hot(ROOT, environment)
        # (r13j) the game's objects are reused, so the update keeps the level they were compiled for (cpu.py). At x86-64-v3 the
        # packaged renderer is used, as before; below it (a CPU without AVX2) the renderer is compiled from the sources for it
        march = build_march(manifest)
        if march != DEFAULT_MARCH:
            environment["RX_MARCH"] = march
            report(f"Este jogo foi compilado para {march}: o renderizador sera compilado dos fontes para este processador.")
        else:
            require_ready_renderer(ROOT, tools, environment)
            features = detect_cpu(tools)
            if features is not None and not supports(features, march):
                report("Aviso: " + unsupported_message(snapshot().get("cpu", ""), march, features))
        hardware = snapshot()
        processes = compile_jobs(jobs, usable_memory(hardware), hardware["logical_cpus"])
        started = time.monotonic()
        needs_output_upgrade = (reuse_game_from is None and not (gen / OUTPUT_SITES_STAMP).is_file()
                                and (EXTENDED_OUTPUT_FEATURE in manifest.get("host_features", [])
                                     or extended_output_emitted(gen)
                                     or manifest.get("source_sha256") in R9_HOST_SOURCES
                                     # (0.4.7 unified: the main line's 0.4.5-test.2 to 0.4.7 too, made from the same base)
                                     or str(manifest.get("version", "")).startswith(("0.4.5", "0.4.6", "0.4.7"))))
        # (r10: a work lifted before r9 has no step hook, and the panel's frame rate cap stayed at 60 after a ZIP update)
        # (r13: the panel's text and mouse camera rows need their hooks in the lifted code too)
        needs_step_upgrade = reuse_game_from is None and (not (gen / STEP_STAMP).is_file() or host_implements_stubbed(work)
                                                          or not (gen / HOOKS_STAMP).is_file())
        if needs_output_upgrade or needs_step_upgrade:
            with upgrade_output_sites(work, environment, processes, report, step_only=not needs_output_upgrade):
                updated = relink(folder, work, tools, environment, processes, manifest, started, report)
        else:
            updated = relink(folder, work, tools, environment, processes, manifest, started, report, reuse_game_from)
        report("@@done " + str(folder))
        report("Build atualizado. Entrada, saves e objetos do jogo preservados; shaders serao conferidos ao jogar.")
        return updated


def relink(folder, work, tools, environment, processes, manifest, started, report, reuse_game_from=None):
    report("@@stage compile Atualizando apenas componentes alterados; objetos do jogo preservados")
    command = [sys.executable, "-I", "-u", str(ROOT/"nx2/build.py"), "--standalone",
               "--reuse-game-objects", "--jobs", str(processes)]
    if reuse_game_from is not None:
        command += ["--reuse-game-from", str(Path(reuse_game_from).resolve())]
    summary = work/"logs/compile-summary.json"
    summary.unlink(missing_ok=True)
    run(command, ROOT, environment, work/"logs/runtime-update.log", report)
    try:
        prebuilt_used = read_json(summary).get("renderer_prebuilt") is True
    except (OSError, ValueError, ProjectError):
        prebuilt_used = False
    if not prebuilt_used and build_march(manifest) == DEFAULT_MARCH:   # (r13j: below x86-64-v3 it is compiled for the CPU)
        raise ProjectError(RENDERER_MISMATCH)
    request = BuildRequest(output=folder, work=work, tools=tools,
                           language=manifest.get("language", "pt-BR"), jobs=processes)
    report("@@stage finish Publicando a atualizacao")
    names = ["AkynoLeyend.exe", "AkynoLeyend.dll", "image.bin", "SDL2.dll", "SDL3.dll", MANIFEST, "language.txt"]
    with workspace_stage(prefix=".runtime-backup-", dir=folder) as backup:
        for name in names:
            if (folder/name).is_file():
                shutil.copy2(folder/name, backup/name)
        try:
            updated = publish(request, Path(manifest["romfs"]), manifest["game_build_id"], processes, started,
                              build_march(manifest))
            updated["maintenance"] = {"from_version": manifest.get("version"),
                "previous_build_seconds": manifest.get("seconds"), "lift_repeated": False,
                "game_objects_required_from_cache": True, "runtime_features": "fullhd-video-budget-v1"}
            write_json(folder/MANIFEST, updated)
        except BaseException:
            for name in names:
                previous, target = backup/name, folder/name
                if previous.is_file():
                    previous.replace(target)
                else:
                    target.unlink(missing_ok=True)
            raise
    return updated
