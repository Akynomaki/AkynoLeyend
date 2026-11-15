"""Compile the legacy resolution guard changes and the frame-step hook (r10) with the installed game cache."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build as native
from oot_output_size import OUTPUT_SITES_STAMP, patched_source, plan
import oot_patches
from akynoleyend.build_support import object_key, require_cached_game_objects
from akynoleyend.errors import ProjectError

# (AkynoLeyend r10) The F1 panel's Game frame rate cap needs nx2/oot_patches.py's step hook in the lifted code. A lift made
# before r9 lacks it, and an update never lifts again: without this the cap stayed at 60 after every ZIP update. The same
# patch as the lift's, at the same two divides, both or neither; the stamp says the work was checked.
STEP_STAMP = "akyno-frame-step-v1"


def step_edits(gen, edits):
    """edits ({path: bytes}) with the step hook added: (edits, the sites hooked in the result)."""
    heads = [head.encode() for head, _, _ in oot_patches.STEP_SITES]
    found, hooked, mark = {}, 0, oot_patches.STEP_MARK.encode()
    for path in sorted(gen.glob("code_*.c")):
        data = edits.get(path) or path.read_bytes()
        # (a work can hold files with CRLF, written by an earlier text-mode patch: the hook's text is LF, so the file is
        # matched as LF and keeps its own line ends)
        crlf = b"\r\n" in data
        flat = data.replace(b"\r\n", b"\n") if crlf else data
        if not any(head in flat for head in heads):
            continue
        text, _ = oot_patches.patch_frame_seconds(flat.decode("utf-8"))
        hooked += text.count(oot_patches.STEP_MARK)
        after = text.encode("utf-8")
        if after == flat:
            after = data
        elif crlf:
            after = after.replace(b"\n", b"\r\n")
        found[path] = (data, after)
    if hooked != len(oot_patches.STEP_SITES):
        print("Limite de FPS: gancho encontrado em %d de %d divisoes; nada alterado (o limite fica em 60)."
              % (hooked, len(oot_patches.STEP_SITES)), flush=True)
        return edits, 0
    for path, (before, after) in found.items():
        if after != before:
            edits[path] = after
    return edits, hooked


# (AkynoLeyend r13) The panel's Text speed, Text size, Mouse camera and Disable camera centering rows need their hooks in the
# lifted code (nx2/oot_patches.py PANEL_HOOKS, Hookshot v2.1.0's). The stamp says every one of them is in this work.
HOOKS_STAMP = "akyno-panel-hooks-r13-v5"   # (v2: with ultrawide's three sites; v3 to v5: with the render distance's)


def hook_edits(gen, edits):
    """edits ({path: bytes}) with the r13 panel hooks added: (edits, the names of the hooks the work holds in the result).
    The lift's own patches (oot_patches.patch_panel_hooks), over the files as step_edits left them; a CRLF file is matched
    as LF and keeps its line ends."""
    heads = [head.encode() for head in (oot_patches.TEXT_HEAD, oot_patches.CAM_HEAD, oot_patches.WIDE_HUD_HEAD,
                                        oot_patches.WIDE_MOVIE_HEAD, oot_patches.WIDE_THUMB_HEAD)
             + oot_patches.FAR_HEADS]
    held = set()
    for path in sorted(gen.glob("code_*.c")):
        data = edits.get(path) or path.read_bytes()
        crlf = b"\r\n" in data
        flat = data.replace(b"\r\n", b"\n") if crlf else data
        if not any(head in flat for head in heads):
            continue
        text, names = oot_patches.patch_panel_hooks(flat.decode("utf-8"))
        held.update(names)
        after = text.encode("utf-8")
        if after == flat:
            continue
        edits[path] = after.replace(b"\n", b"\r\n") if crlf else after
    missing = [name for name, _, _ in oot_patches.PANEL_HOOKS if name not in held]
    if missing:
        print("Ganchos do painel: sem lugar neste jogo para: %s (essas linhas do F1 ficam sem efeito)." % ", ".join(missing),
              flush=True)
    return edits, held


def _stub_definitions(text):
    return [line for line in text.splitlines() if line.startswith("void ")]


def stub_edits(work, edits):
    """(AkynoLeyend r12) a64_stubs.c made again by the lift's own generator (nx2/standalone.py stubs_text) from the lift's
    metadata in the work: host/ now implements imports it stubbed (Hookshot v2.1.0's microphone streams, nn_audio_in.c),
    and a stub beside a host definition is a duplicate symbol at the link. Compared by its definitions (the demangled
    comments depend on the toolchain's llvm-cxxfilt). (edits, the stubs left)"""
    import json
    import standalone
    path = work / "sa/gen/a64_stubs.c"
    image_json = work / "sa/image/image.json"
    if not path.is_file() or not image_json.is_file():   # (no lift metadata: the stubs as they are)
        return edits, -1
    meta = json.loads(image_json.read_text(encoding="utf-8"))
    text, count = standalone.stubs_text(meta)
    if path.is_file() and _stub_definitions(path.read_text(encoding="utf-8", errors="replace")) == _stub_definitions(text):
        return edits, count
    edits[path] = text.encode("utf-8")
    print("Imports do host: a64_stubs.c refeito pelo gerador da traducao (%d stubs restantes)." % count, flush=True)
    return edits, count


def needs_upgrade(gen):
    """Whether this work still lacks the extended outputs, the step hook's check or the r13 panel hooks (maintenance asks
    before staging)."""
    return (not (gen / OUTPUT_SITES_STAMP).is_file() or not (gen / STEP_STAMP).is_file()
            or not (gen / HOOKS_STAMP).is_file())


def translated_jobs(gen, built):
    """Use the default standalone settings from nx2/build.py."""
    rt64 = Path(native.rtgen.write(str(built / "rt64")))
    cc = native.toolchain.need(native.toolchain.find("clang"))
    deps = b"".join((folder / name).read_bytes() for folder in (gen, rt64)
                    for name in sorted(p.name for p in folder.iterdir() if p.name.endswith(".h")))
    sources = sorted(gen.glob("code_*.c"))
    sources.extend(gen / name for name in (
        "a64_table.c", "a64_hooks.c", "a64_suyu.c", "a64_stubs.c", "hos_image.c", "nvn2_exports.c",
    ))
    sources.append(rt64 / "a64_rt.c")
    return {
        source: (cc, str(source), str(built / "obj" / (source.stem + ".o")),
                 native.flags(str(gen), str(rt64), "O2" if source.name.startswith("code_hot") else "O1", True),
                 deps)
        for source in sources
    }


def upgrade(work, staging, workers, step_only=False):
    gen = work / "sa/gen"
    built = work / "sa/build"
    edits = {}
    if not step_only and not (gen / OUTPUT_SITES_STAMP).is_file():
        edits = {path: patched_source(path, replacements) for path, replacements in plan(gen, legacy_only=True)}
    edits, step_sites = step_edits(gen, edits)
    edits, hooks = hook_edits(gen, edits)
    all_hooks = len(hooks) == len(oot_patches.PANEL_HOOKS)   # (else the next update looks again)
    edits, _ = stub_edits(work, edits)
    jobs = translated_jobs(gen, built)
    require_cached_game_objects(jobs.values(), native.OBJ_CACHE)
    if not edits:
        if not step_only:
            (gen / OUTPUT_SITES_STAMP).touch()
        if step_sites:   # (hooked already; without the hook the next update looks again)
            (gen / STEP_STAMP).touch()
        if all_hooks:
            (gen / HOOKS_STAMP).touch()
        print("Guardas de resolucao, gancho do limite de FPS e ganchos do painel ja estavam atualizados; nenhum bloco "
              "traduzido compilado.", flush=True)
        return
    changes = sorted(edits.items())

    old_gen, old_obj, compiled = (staging / name for name in ("gen", "obj", "compiled"))
    for directory in (old_gen, old_obj, compiled):
        directory.mkdir()
    # The copied local stamps and objects are also used if the later link/publish fails.
    for path, _ in changes:
        shutil.copy2(path, old_gen / path.name)
        cc, source, target, flags, deps = jobs[path]
        output = Path(target)
        stamp = output.with_suffix(".o.sha256")
        for previous in (output, stamp):
            if previous.is_file():
                shutil.copy2(previous, old_obj / previous.name)
        key = object_key(cc, source, flags, deps)
        if output.is_file() and stamp.is_file() and stamp.read_text() == key:
            native.cache_put(target, key)
    (staging / "ready").touch()

    # Keep quoted includes beside the staged C just as they are beside the
    # original C. The normal object key hashes the flags, contents and headers.
    for header in gen.glob("*.h"):
        shutil.copy2(header, compiled / header.name)
    selected = []
    for path, data in changes:
        candidate = compiled / path.name
        candidate.write_bytes(data)
        cc, _, output, flags, deps = jobs[path]
        selected.append((cc, str(candidate), str(compiled / Path(output).name), flags, deps))
    print("Codigo traduzido: atualizando %d bloco(s) pelo gerador (%s)." % (len(selected), ", ".join(p.name for p, _ in changes)), flush=True)
    with ThreadPoolExecutor(min(workers, len(selected))) as pool:
        results = list(pool.map(native.compile_one, selected))
    for source, _, error in results:
        if error:
            raise ProjectError(Path(source).name + ": " + error)
    # Until this point the original sources and local objects are untouched.
    # Both sets of keys exist now, so even a retry during replacement can proceed.
    for path, _ in changes:
        (compiled / path.name).replace(path)
    require_cached_game_objects(jobs.values(), native.OBJ_CACHE)
    if step_sites:
        (gen / STEP_STAMP).touch()
    if all_hooks:
        (gen / HOOKS_STAMP).touch()
    if hooks:
        print("Ganchos do painel no codigo traduzido: %s." % ", ".join(sorted(hooks)), flush=True)
    if not step_only:
        (gen / OUTPUT_SITES_STAMP).touch()
        print("720p e 2560x1600: guardas de largura, altura e memoria conferidos.", flush=True)
    if step_sites:
        print("Limite de FPS: o tempo do quadro nas %d divisoes do passo do jogo (acima de 60 passa a valer)." % step_sites,
              flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--jobs", type=int, required=True)
    parser.add_argument("--step-only", action="store_true", help="only the frame-step hook (the outputs are not this build's)")
    args = parser.parse_args()
    try:
        upgrade(Path(native.kit.WORK), args.staging, args.jobs, args.step_only)
    except (OSError, ValueError, ProjectError) as error:
        print("Atualizacao de resolucao interrompida: " + str(error), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
