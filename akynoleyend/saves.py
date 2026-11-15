"""Bring an Ocarina of Time save from an emulator into this port (Ferramentas > EXPORTAR SAVES, `manage.py export-saves`).

Adapted from Hookshot's scripts/oot_saves.py (github.com/NotRexed/Hookshot, GPL-3.0; its guide is docs/saves.md there):
the emulators and this port keep the game's saves as the same files (account.sav, option.sav, slot_NN/progress.sav and
caption.sav, the same header), so the save is copied, never converted. What changed here: the emulators the launcher
offers (Fritz/Fritchii, MDias, PokeDinner, Lichii), one direction (emulator -> port), and the copy itself: the emulator's
folder is only read; the save is copied into a folder beside the port's, every file checked by SHA-256 against the
emulator's, and only then the port's save folder is moved to a backup and the new one put in its place (two renames on
the same disk). A failure before that leaves the port's save as it was.

Where the emulators keep the saves (each one's src/common/fs/fs_paths.h; Hookshot's docs/saves.md):
- Fritz (Fritchii), PokeDinner: %APPDATA%\\eden
- Lichii: %APPDATA%\\lichii since its build 150, %APPDATA%\\eden before (both are searched, lichii first)
- MDias (Eglantine_Litchii_forkMDias): a Lichii build (its lichii.exe), so as Lichii
then nand\\user\\save\\0000000000000000\\<profile>\\0400486024DEC000 (newer Eden code first reads
nand\\user\\save\\account\\<profile>\\0400486024DEC000\\0). A "user" folder beside the emulator (portable mode) is given
with --from. Only profiles that hold a save count: an emulator keeps an empty folder for its profile 000...0.

The port keeps its save in <jogo>\\user\\save\\5a3c9e1f0b7d24680000000000000001 (host/nn_applet.c user_uid, named by
host/nn_fs.c MountSaveData). Only that search is made: nothing else on the PC is read or written."""

import collections
import datetime
import hashlib
import os
import shutil
import stat
import subprocess
from pathlib import Path

from .errors import ProjectError

TITLE = "0400486024DEC000"
NO_ACCOUNT = "0000000000000000"
PORT_UID = "5a3c9e1f0b7d24680000000000000001"
SAVE_FILES = ("account.sav", "option.sav")

Emulator = collections.namedtuple("Emulator", "name display folders processes")
EDEN = ("eden",)
LICHII = ("lichii", "eden")
EMULATORS = {
    "fritz": Emulator("fritz", "Fritz (Fritchii)", EDEN, ("lichii", "fritchii")),
    "mdias": Emulator("mdias", "MDias (fork do Lichii)", LICHII, ("lichii",)),
    "pokedinner": Emulator("pokedinner", "PokeDinner", EDEN, ("eglantine", "eden")),
    "lichii": Emulator("lichii", "Lichii", LICHII, ("lichii",)),
}
GAME_PROCESS = "akynoleyend"   # (the game; the launcher is AkynoLeyendBuilder and does not hold the save)

# Where a profile's save sits under an emulator's data folder, from Hookshot's LAYOUTS (the Eden ones), in order
LAYOUTS = (
    ("nand", "user", "save", "account", "<id>", TITLE, "0"),
    ("nand", "user", "save", NO_ACCOUNT, "<id>", TITLE),
)


def appdata() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")


def data_folders(emulator: Emulator) -> list[Path]:
    return [appdata() / name for name in emulator.folders]


def subdirs(path: Path) -> list[str]:
    try:
        return sorted(entry.name for entry in os.scandir(path) if entry.is_dir(follow_symlinks=False))
    except OSError:
        return []


def slots(path: Path) -> list[str]:
    return [name for name in subdirs(path) if name.lower().startswith("slot_")]


def holds_save(path: Path) -> bool:
    return (path / "account.sav").is_file() or bool(slots(path))


def _walk(root: Path, parts: tuple, key):
    if not parts:
        yield key, root
        return
    for name in subdirs(root):
        if parts[0] == "<id>":
            yield from _walk(root / name, parts[1:], name)
        elif name.lower() == parts[0].lower():
            yield from _walk(root / name, parts[1:], key)


def find_saves(root: Path) -> dict[str, Path]:
    """{profile: save folder} under an emulator's data folder (or a portable user folder, or the save folder itself),
    only the profiles that hold a save; the first layout that has a profile wins for it."""
    root = Path(os.path.abspath(root))
    if holds_save(root):
        key = root
        while key.name.upper() in (TITLE, "0") and key.parent != key:
            key = key.parent
        return {key.name or str(root): root}
    found: dict[str, Path] = {}
    starts = [root, root / "user"]   # (a folder with the emulator's portable "user" folder in it)
    for start in starts:
        for layout in LAYOUTS:
            for key, path in _walk(start, layout, None):
                if key not in found and holds_save(path):
                    found[key] = path
    return found


def last_saved(path: Path) -> float:
    times = [0.0]
    for name in SAVE_FILES:
        try:
            times.append((path / name).stat().st_mtime)
        except OSError:
            pass
    for slot in slots(path):
        for name in ("progress.sav", "caption.sav"):
            try:
                times.append((path / slot / name).stat().st_mtime)
            except OSError:
                pass
    return max(times)


def locate(emulator: Emulator, override: Path | None) -> tuple[Path, dict[str, Path]]:
    if override is not None:
        if not Path(override).is_dir():
            raise ProjectError(f"Pasta nao encontrada: {override}")
        found = find_saves(Path(override))
        if not found:
            raise ProjectError(f"Nenhum save do Ocarina of Time em {override}.")
        return Path(override), found
    tried = data_folders(emulator)
    for folder in tried:
        found = find_saves(folder) if folder.is_dir() else {}
        if found:
            return folder, found
    raise ProjectError(
        f"Nenhum save do Ocarina of Time do {emulator.display} encontrado (procurado em "
        + ", ".join(str(f / "nand" / "user" / "save") for f in tried)
        + "). Abra o jogo no emulador, salve e tente de novo.")


def pick(found: dict[str, Path], wanted: str | None) -> tuple[str, Path]:
    """The profile asked for, else the one saved last (an emulator with several profiles: the others are listed)."""
    if wanted:
        for key, path in found.items():
            if key.lower() == wanted.lower():
                return key, path
        raise ProjectError(f"Perfil {wanted} sem save; perfis com save: {', '.join(sorted(found))}")
    return max(found.items(), key=lambda item: last_saved(item[1]))


def running(emulator: Emulator) -> list[str]:
    """What holds a save now: the game of this port, or the emulator chosen."""
    if os.name != "nt":
        return []
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=30,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    names = set()
    for line in out.splitlines():
        image = line.split('","')[0].strip('"').lower()
        if image.endswith(".exe"):
            names.add(image[:-4])
    busy = []
    if GAME_PROCESS in names:
        busy.append("o jogo (AkynoLeyend.exe)")
    if any(p in names for p in emulator.processes):
        busy.append(emulator.display)
    return busy


def _is_link(path: Path) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & 0x400)


def save_files(source: Path) -> list[Path]:
    """The files to bring, relative to the save folder: account.sav, option.sav and every file of every slot_* folder.
    A link anywhere is refused (it would copy what it points to)."""
    names = slots(source)
    if not names:
        raise ProjectError(f"{source} nao tem pastas slot_*: nada para copiar.")
    files = []
    for name in SAVE_FILES:
        path = source / name
        if _is_link(path):
            raise ProjectError(f"{path} e um link: um save so tem arquivos e pastas. Nada foi copiado.")
        if path.is_file():
            files.append(Path(name))
    for slot in names:
        top = source / slot
        if _is_link(top):
            raise ProjectError(f"{top} e um link: um save so tem arquivos e pastas. Nada foi copiado.")
        for folder, dirs, entries in os.walk(top):
            for entry in dirs + entries:
                if _is_link(Path(folder) / entry):
                    raise ProjectError(f"{Path(folder) / entry} e um link: um save so tem arquivos e pastas. Nada foi copiado.")
            for entry in entries:
                files.append((Path(folder) / entry).relative_to(source))
    return sorted(files)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def export_saves(emulator_name: str, out: Path, *, source: Path | None = None, profile: str | None = None,
                 dry_run: bool = False, check_running: bool = True, report=print) -> dict:
    """Copy the emulator's save into the port's save folder under `out` (the game folder, jogo). Returns what was done."""
    emulator = EMULATORS.get(emulator_name.lower())
    if emulator is None:
        raise ProjectError("Emulador desconhecido: %s. Use %s." % (emulator_name, ", ".join(EMULATORS)))
    out = Path(out).resolve()
    if not out.is_dir():
        raise ProjectError(f"Pasta do jogo nao encontrada: {out}. Escolha a pasta de saida em Inicio.")
    folder, found = locate(emulator, source)
    key, src = pick(found, profile)
    report(f"{emulator.display}: save encontrado em {src}")
    others = sorted(k for k in found if k != key)
    if others:
        report("Outros perfis com save neste emulador (use --profile para escolher): " + ", ".join(others))
    saves = out / "user" / "save"
    target = saves / PORT_UID
    files = save_files(src)
    slot_names = slots(src)
    for slot in slot_names:
        progress = src / slot / "progress.sav"
        when = (datetime.datetime.fromtimestamp(progress.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
                if progress.is_file() else "sem progress.sav")
        report(f"  {slot}: {when}")
    result = {"emulator": emulator.name, "profile": key, "source": str(src), "target": str(target),
              "files": len(files), "slots": slot_names, "backup": None}
    if dry_run:
        report(f"Simulacao: {len(files)} arquivo(s) seriam copiados para {target}; nada foi alterado.")
        return result
    if check_running:
        busy = running(emulator)
        if busy:
            raise ProjectError("Feche " + " e ".join(busy) + " antes de exportar: um jogo aberto pode gravar o save de "
                               "novo e desfazer a copia. Nada foi alterado.")
    saves.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    stage = saves / f".exportando-{emulator.name}-{stamp}"
    shutil.rmtree(stage, ignore_errors=True)
    try:
        stage.mkdir()
        for relative in files:
            origin, copy = src / relative, stage / relative
            copy.parent.mkdir(parents=True, exist_ok=True)
            before = digest(origin)
            shutil.copy2(origin, copy, follow_symlinks=False)
            if digest(copy) != before or digest(origin) != before:
                raise ProjectError(f"A copia de {relative} nao confere com o original (o emulador estava gravando?). "
                                   "Nada foi alterado no save do port.")
        report(f"{len(files)} arquivo(s) copiados e conferidos (SHA-256).")
        backup = None
        if target.exists():
            backups = out / "user" / "save-backups"
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / f"{stamp}-antes-de-{emulator.name}"
            n = 1
            while backup.exists():
                n += 1
                backup = backups / f"{stamp}-antes-de-{emulator.name}-{n}"
            backup.mkdir()
            os.replace(target, backup / PORT_UID)
        try:
            os.replace(stage, target)
        except OSError:
            if backup is not None:   # (the port's save back where it was)
                os.replace(backup / PORT_UID, target)
            raise
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    result["backup"] = str(backup) if backup else None
    report(f"Save do {emulator.display} exportado para {target}.")
    if backup:
        report(f"O save anterior do port foi guardado em {backup}.")
    return result
