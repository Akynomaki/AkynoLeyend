"""Repair the known NUP reader before a first successful game build."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ORIGINAL = "aabc240ecde5084ddba80c53a49b55a871be188cf31c03d3c5bf1a8b82b650a1"
CORRECTED = "c1b9fb6f9bb6a6548d77d7a773a36fc852a37b40ba3c5285d27a1d8bcaef4374"
RELATIVE = Path("nx2/nup.py")

PROBE = r'''
import json, pathlib, shutil, sys, tempfile
root = pathlib.Path(sys.argv[1])
target = root / "nx2/nup.py"
ns = {"__name__": "nup_repair_probe", "__file__": str(target)}
exec(compile(target.read_bytes(), str(target), "exec"), ns)
data = b"synthetic extraction probe"
relative = "Event/EventSetting/EventSettingComponent/ActorStateSetting/IgnoreDissentPlayEventAndStartInterval.engineeventActorStateSetting.bgyml"
class Archive:
    def walk(self, part): return iter([(relative, (0, 0, len(data)))])
    def is_packed(self, record, name): return False
    def copy_to(self, record, stream, name, packed=None): stream.write(data)
temporary = tempfile.TemporaryDirectory(prefix="nup-probe-", dir=root / "work")
try:
    out = pathlib.Path(temporary.name) / ("long-path-" * 10) / ("validation-" * 7)
    count, size = ns["extract"](Archive(), {"romfs": 0}, out, only="romfs", quiet=True)
    file = pathlib.Path(ns["filesystem_path"](out / "romfs" / relative))
    assert file.read_bytes() == data and count == 1 and size == len(data)
    assert not list(file.parent.glob("*.part"))
    print(json.dumps({"module": str(target), "bytes_verified": size, "target_characters": len(str(file)),
                      "windows_executed": sys.platform == "win32"}))
finally:
    shutil.rmtree(ns["filesystem_path"](temporary.name), ignore_errors=False)
    temporary.cleanup()
'''


class RepairError(Exception):
    pass


def fingerprint(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


@contextmanager
def build_lock(root):
    work = root / "work"
    work.mkdir(exist_ok=True)
    with (work / "build.lock").open("a+b") as stream:
        try:
            if os.name == "nt":
                import msvcrt
                if stream.seek(0, os.SEEK_END) == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RepairError("Existe uma compilacao em andamento. Feche o Builder e tente novamente.") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomic_write(path, data):
    descriptor, temporary = tempfile.mkstemp(prefix=".nup-repair-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def probe(root):
    child = subprocess.run([sys.executable, "-I", "-B", "-X", "utf8", "-c", PROBE, str(root)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if child.returncode:
        raise RepairError("A verificacao de extracao falhou:\n" + child.stderr[-5000:])
    return json.loads(child.stdout)


def repair(root, payload, report=print):
    root = Path(root).resolve()
    target = (root / RELATIVE).resolve()
    if not all((root / n).is_file() for n in ["manage.py", "AkynoLeyendBuilder.exe", RELATIVE]):
        raise RepairError("Extraia a correcao na pasta que contem AkynoLeyendBuilder.exe e nx2.")
    if not target.is_relative_to(root):
        raise RepairError("O extrator aponta para fora da instalacao selecionada.")
    replacement = Path(payload).read_bytes()
    if fingerprint(replacement) != CORRECTED:
        raise RepairError("O arquivo de correcao esta incompleto ou foi alterado.")
    compile(replacement, str(target), "exec")
    with build_lock(root):
        previous = target.read_bytes()
        old_hash = fingerprint(previous)
        if old_hash not in {ORIGINAL, CORRECTED}:
            raise RepairError("Extrator diferente da revisao conhecida; nenhum arquivo foi substituido. SHA-256: " + old_hash)
        if old_hash == ORIGINAL:
            outputs = {root / "jogo"}
            request = root / "work/build-request.json"
            if request.is_file():
                plan = json.loads(request.read_text(encoding="utf-8"))
                output = Path(plan.get("output", str(root / "jogo")))
                if output.is_absolute():
                    outputs.add(output)
            if any((folder / "AkynoLeyend-build.json").is_file() for folder in outputs):
                raise RepairError("Ja existe um jogo compilado nesta instalacao. Este reparo e para a extracao que falhou antes do primeiro build; o jogo existente foi preservado.")
        backup = None
        if old_hash == ORIGINAL:
            folder = root / "work/repairs" / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
            folder.mkdir(parents=True)
            backup = folder / "nup.py.bak"
            backup.write_bytes(previous)
            try:
                atomic_write(target, replacement)
                verified = probe(root)
                if fingerprint(target.read_bytes()) != CORRECTED:
                    raise RepairError("O extrator foi alterado durante a verificacao.")
            except Exception:
                atomic_write(target, previous)
                report("A verificacao falhou; o extrator anterior foi restaurado.")
                raise
        else:
            verified = probe(root)
        result = {"changed": backup is not None, "before_sha256": old_hash, "after_sha256": CORRECTED,
                  "backup": str(backup) if backup else None, "verification": verified}
        log = root / "work/logs/reparo-extracao.json"
        log.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(log, (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        report("CORRECAO CONFIRMADA: extrator atualizado e arquivo sintetico verificado.")
        report("Abra o Builder e repita Criar com a mesma entrada e destino. Preserve work.")
        report("Registro: " + str(log))
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        repair(args.root, args.payload)
    except (RepairError, OSError, ValueError, SyntaxError, subprocess.TimeoutExpired) as error:
        print("ERRO: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
