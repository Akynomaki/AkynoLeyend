"""Install an explicitly selected update package, preserving local game data and toolchains."""
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import time
import uuid
import zipfile

from .errors import ProjectError
from .files import read_json, sha256, write_json, workspace_lock

BLOCKED = {"work", "jogo", "user", "atualizacoes", "diagnosticos", "analysis", ".git"}
INDEX = "update-package.json"


def package_notes(meta):
    """Bounded plain text for the launcher's update preview; never executable markup."""
    notes = meta.get("notes", {})
    if not isinstance(notes, dict) or any(key not in {"new", "fixes", "experimental", "known_issues"} for key in notes):
        raise ProjectError("Notas de atualizacao invalidas.")
    result = {}
    for key in ("new", "fixes", "experimental", "known_issues"):
        items = notes.get(key, [])
        if (not isinstance(items, list) or len(items) > 40 or
                any(not isinstance(x, str) or not x.strip() or len(x) > 1000 for x in items)):
            raise ProjectError("Notas de atualizacao invalidas ou longas demais.")
        result[key] = [item.strip() for item in items]
    return result


def relative_name(name):
    p = PurePosixPath(name)
    if (not name or p.is_absolute() or "\\" in name or p.as_posix() != name
            or any(x in {"", ".", ".."} or x.rstrip(" .") != x or any(c in x for c in '<>:"|?*') for x in p.parts)):
        raise ProjectError("Caminho invalido no pacote de atualizacao.")
    if p.parts[0].casefold() in BLOCKED or name.casefold() == "akynoleyend-launcher.json":
        raise ProjectError("O pacote tenta substituir dados locais preservados.")
    if p.parts[0].casefold() == "ferramentas" and (len(p.parts) != 3 or p.parts[1] != "prebuilt"):
        raise ProjectError("Use o pacote de atualizacao; SDKs completos nao sao substituidos por este fluxo.")
    return Path(*p.parts)


def _inspect_package(archive: Path):
    with zipfile.ZipFile(archive) as z:
        if INDEX not in z.namelist():
            raise ProjectError("Este ZIP nao possui indice de atualizacao. Selecione o pacote Atualizacao desta versao.")
        if z.getinfo(INDEX).file_size > 2 << 20:
            raise ProjectError("Indice de atualizacao excede o limite.")
        meta = json.loads(z.read(INDEX))
        files = meta.get("files")
        if meta.get("schema") != 1 or meta.get("kind") != "update" or not isinstance(meta.get("version"), str) or not isinstance(files, dict):
            raise ProjectError("Formato de atualizacao desconhecido.")
        package_notes(meta)
        entries = [i for i in z.infolist() if not i.is_dir()]
        names = [i.filename for i in entries]
        if len(entries) > 20000 or len(names) != len(set(n.casefold() for n in names)) or set(names) != set(files) | {INDEX}:
            raise ProjectError("Conteudo do ZIP diverge do indice ou possui nomes repetidos.")
        if sum(i.file_size for i in entries) > 2 << 30:
            raise ProjectError("Pacote de atualizacao excede 2 GiB descompactado.")
        for item in entries:
            relative_name(item.filename)
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ProjectError("Links nao sao aceitos no pacote.")
            if item.filename != INDEX:
                digest = files[item.filename]
                if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                    raise ProjectError("Hash invalido no indice.")
        for name in ("AkynoLeyendBuilder.exe", "manage.py", "VERSION", "ferramentas/prebuilt/AkynoLeyend.dll", "ferramentas/prebuilt/renderer.json"):
            if name not in files: raise ProjectError("Atualizacao incompleta: " + name)
        return meta


def inspect_package(archive: Path):
    try:
        return _inspect_package(archive)
    except (zipfile.BadZipFile, json.JSONDecodeError, AttributeError, TypeError, KeyError) as error:
        raise ProjectError("O arquivo nao e um pacote de atualizacao valido.") from error


def clear_abandoned(updates: Path, keep=None, report=print):
    """(r10) Staged packages that were never installed: a pendente-* folder with no anterior/ (install_files makes it before
    replacing a file) was only checked, then the launcher was closed or another ZIP was chosen. Each one kept a whole package
    (60-125 MB) forever. A folder with anterior/ is kept: it may hold the files a failed update has to give back."""
    if not updates.is_dir():
        return 0
    removed = 0
    for folder in updates.glob("pendente-*"):
        if folder == keep or not folder.is_dir() or (folder / "anterior").exists():
            continue
        try:
            shutil.rmtree(folder)
            removed += 1
        except OSError as error:
            report("Pasta de atualizacao antiga mantida (" + folder.name + "): " + str(error))
    if removed:
        report("%d atualizacao(oes) conferida(s) e nao instalada(s) removida(s) de atualizacoes." % removed)
    return removed


def refuse_unknown_build(payload: Path, root: Path, output: Path, files: dict):
    """(r13c) The package's own maintain-build accepts only an installed game whose source identity its coherence.py lists. A
    package older than the installed revision (or made for another) was found out only after the launcher had closed and every
    file had been replaced, with a message that did not say why. Checked here, while staging, from the package's text: none of
    its code runs. A package with nothing to replace, or a folder without a compiled game, goes on as before."""
    manifest = output / "AkynoLeyend-build.json"
    if not manifest.is_file():
        return
    try:
        identity = json.loads(manifest.read_text(encoding="utf-8")).get("source_sha256")
    except (OSError, ValueError, AttributeError):
        return
    if not isinstance(identity, str) or len(identity) != 64:
        return
    if all((root / name).is_file() and sha256(root / name) == digest for name, digest in files.items()):
        return
    try:
        known = (payload / "akynoleyend" / "coherence.py").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    if '"' + identity + '"' not in known:
        raise ProjectError("Este pacote nao reconhece o jogo instalado (revisao " + identity[:8] + "): ele e mais antigo que a "
                           "versao instalada ou foi feito para outra. Nada foi alterado. Escolha o pacote mais recente.")


def stage_update(archive: Path, root: Path, output: Path, *, jobs=None, report=print):
    meta = inspect_package(archive)
    root = root.resolve()
    clear_abandoned(root / "atualizacoes", report=report)
    folder = root / "atualizacoes" / ("pendente-" + uuid.uuid4().hex)
    payload = folder / "arquivos"
    folder.mkdir(parents=True)
    try:
        if os.name == "nt":
            from .windows_acl import protect_staging
            protect_staging(folder)
        payload.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name, digest in meta["files"].items():
                dest = payload / relative_name(name)
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(name) as src, dest.open("wb") as target:
                    shutil.copyfileobj(src, target, 1 << 20)
                if sha256(dest) != digest: raise ProjectError("Arquivo danificado no pacote: " + name)
        if (payload/"VERSION").read_text().strip() != meta["version"]:
            raise ProjectError("Versao do pacote diverge dos fontes.")
        for name in ("AkynoLeyendBuilder.exe", "ferramentas/prebuilt/AkynoLeyend.dll"):
            with (payload/name).open("rb") as f:
                if f.read(2) != b'MZ': raise ProjectError("Binario Windows ausente no pacote: " + name)
        refuse_unknown_build(payload, root, output, meta["files"])
        plan = folder / "plano.json"
        write_json(plan, {"schema": 1, "root": str(root), "output": str(output.resolve()),
                          "version": meta["version"], "files": meta["files"], "jobs": jobs,
                          "notes": package_notes(meta)})
        report("Pacote conferido. Saves, ferramentas e objetos compilados serao preservados.")
        return plan
    except Exception:
        shutil.rmtree(folder)
        raise


def wait_for_parent(pid, timeout=90):
    if not pid: return
    if pid == os.getpid(): raise ProjectError("O atualizador nao pode esperar por si mesmo.")
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, 0, pid)
        if not handle: return
        try:
            if kernel.WaitForSingleObject(handle, int(timeout*1000)) != 0:
                raise ProjectError("A interface continua aberta; feche-a antes de aplicar o pacote.")
        finally: kernel.CloseHandle(handle)
    else:
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            try: os.kill(pid, 0)
            except ProcessLookupError: return
            time.sleep(0.1)
        raise ProjectError("A interface continua aberta.")


def install_files(plan, maintain=None):
    """Atomic file replacements and rollback, also exercised without a Windows UI."""
    data = read_json(plan)
    if data.get("schema") != 1 or not isinstance(data.get("files"), dict):
        raise ProjectError("Plano de atualizacao invalido.")
    root = Path(data["root"]).resolve()
    if plan.parent.parent.resolve() != root/"atualizacoes":
        raise ProjectError("Plano fora da pasta de atualizacoes desta instalacao.")
    payload, backup = plan.parent/"arquivos", plan.parent/"anterior"
    files = data["files"]
    for name, digest in files.items():
        rel = relative_name(name)
        if sha256(payload/rel) != digest: raise ProjectError("Pacote alterado depois da conferencia: " + name)
        target = root/rel
        if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != root.parent):
            raise ProjectError("Destino da atualizacao e um link: " + name)
    changed = []
    with workspace_lock(root/"atualizacoes"):
        try:
            for name in files:
                rel = relative_name(name); dest = root/rel
                if dest.is_file() and sha256(dest) == files[name]: continue
                if dest.exists():
                    old = backup/rel;old.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(dest, old)
                dest.parent.mkdir(parents=True, exist_ok=True)
                temp = dest.with_name(dest.name+'.update-'+uuid.uuid4().hex)
                try: shutil.copy2(payload/rel, temp);temp.replace(dest)
                finally: temp.unlink(missing_ok=True)
                changed.append(rel)
            if maintain is not None: maintain(data)
        except Exception as original:
            errors = []
            for rel in reversed(changed):
                try:
                    if (backup/rel).exists(): shutil.copy2(backup/rel, root/rel)
                    else: (root/rel).unlink(missing_ok=True)
                except OSError as e: errors.append(str(e))
            if errors: raise ProjectError("Atualizacao interrompida; reversao pendente em " + str(backup) + ': ' + '; '.join(errors)) from original
            # (r13c) every file is back: the copies are no longer needed, and a folder with anterior/ was kept forever
            # (clear_abandoned leaves it for a rollback still owed). Without them the next staging clears the folder
            shutil.rmtree(backup, ignore_errors=True)
            raise
    return data


def apply_update(plan: Path, wait_pid=0, *, restart=True):
    # (r10) The log is written from the first step: before, it was opened only by maintain-build, so a failure while
    # waiting for the launcher, checking the plan or replacing files left only a message box and the previous run's log.
    log = Path(plan).resolve().parent.parent/"ultima-atualizacao.log"
    def note(text):
        try:
            with log.open("a", encoding="utf-8") as f: f.write(text.rstrip("\n") + "\n")
        except OSError: pass
        print(text, flush=True)
    try: log.write_text("", encoding="utf-8")
    except OSError: pass
    def maintain(current):
        output = Path(current["output"])
        if not (output/"AkynoLeyend-build.json").is_file():
            note("Nenhum jogo compilado em " + str(output) + "; so os arquivos foram trocados."); return
        cmd = [sys.executable, "-I", "-X", "utf8", "-u", str(root/"manage.py"), "maintain-build", "--out", str(output)]
        if current.get("jobs") is not None: cmd += ["--jobs", str(current["jobs"])]
        with log.open("a", encoding="utf-8") as f:
            process = subprocess.Popen(cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace")
            for line in process.stdout:
                f.write(line); f.flush(); print(line, end="", flush=True)
            status = process.wait()
        if status: raise ProjectError("Atualizacao dos componentes interrompida. Consulte " + str(log))
    try:
        note("@@stage wait Esperando o launcher fechar (PID %d)" % wait_pid if wait_pid else "@@stage wait Iniciando")
        wait_for_parent(wait_pid)
        data = read_json(plan);root = Path(data["root"])
        note("Instalacao: " + str(root) + " · versao " + str(data.get("version")) + " · " + str(len(data.get("files", {})))
             + " arquivo(s)")
        install_files(plan, maintain)
    except Exception as error:
        note("@@error " + str(error))
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(error), "AkynoLeyend — atualização interrompida", 0x10)
        return 1
    # (the files are in place: what follows can no longer fail the update. Before, a folder that could not be removed
    # turned an installed update into "atualizacao interrompida", after the launcher had already been reopened)
    try: shutil.rmtree(plan.parent)
    except OSError as error: note("Pasta temporaria mantida (" + plan.parent.name + "): " + str(error))
    note("@@done Atualizacao instalada. Launcher reaberto de " + str(root))
    if restart:
        try: subprocess.Popen([str(root/"AkynoLeyendBuilder.exe")], cwd=root)
        except OSError as error: note("A atualizacao foi instalada, mas o launcher nao reabriu: " + str(error))
    return 0
