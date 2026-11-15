"""Apply and verify the 0.4.2 lifter fix in one explicitly selected installation."""

import argparse
import ast
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

RELATIVE = Path("third_party/a64-kit/lift/a64_lift.py")
ORIGINAL = "8d42fd0c7647b34ce1b438e07572119e2da3fa10b04c720cd8e580130b0c1787"
CORRECTED = "e75d9967c8ec3911a5ef75e28477ca2ac8b84bfd01f847377f5eaf0b14529946"

PROBE = r'''
import contextlib, io, json, os, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "nx2"))
import kit
import a64_lift
import oot_occlusion
import insn
import lift_fixes
insn.install()
lift_fixes.install()
os.environ["A64_LOCAL_REGS"] = "0"
os.environ["A64_LOCAL_FLAGS"] = ""
class Image:
    hooks = {}
    def __init__(self):
        self.entries = {oot_occlusion.MAIN + off for off in oot_occlusion.OFFSETS}
        self.entries.add(oot_occlusion.MAIN)
        self.words = {pc+d: w for pc in self.entries
                      for d,w in ((0,oot_occlusion.LDRB_W8_X0),(4,0xD65F03C0))}
    def word(self, pc): return self.words[pc]
    def in_code(self, pc): return pc in self.words
image = Image()
lifter = a64_lift.Lifter(image)
result = {"module": str(pathlib.Path(a64_lift.__file__).resolve()),
          "has_after": hasattr(lifter, "after"), "verified_sites": 0}
if result["has_after"]:
    with contextlib.redirect_stdout(io.StringIO()):
        sites = oot_occlusion.install(lifter, image)
    lifter.discover()
    load = "c->x[8] = 173;"
    for pc in sorted(image.entries):
        text, _ = lifter.emit_function(pc, {oot_occlusion.LDRB_W8_X0: (load, 0)})
        if pc == oot_occlusion.MAIN:
            assert "hos_occlusion_off" not in text
        else:
            assert text.count("extern volatile int hos_occlusion_off") == 1
            assert text.index(load) < text.index("if (hos_occlusion_off)")
            result["verified_sites"] += 1
    assert sites == result["verified_sites"] == 6
print(json.dumps(result))
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
        except OSError as exc:
            raise RepairError("Existe uma compilacao em andamento. Feche o Builder e tente novamente.") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomic_write(path, data):
    handle, name = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def probe(root):
    # A fresh cache prefix also rules out a stale .pyc without deleting user caches.
    with tempfile.TemporaryDirectory(prefix="akyno-lift-check-") as cache:
        child = subprocess.run(
            [sys.executable, "-I", "-B", "-X", "utf8", "-X", "pycache_prefix=" + cache,
             "-c", PROBE, str(root)],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
    if child.returncode:
        raise RepairError("A verificacao do tradutor falhou:\n" + child.stderr[-6000:])
    try:
        result = json.loads(child.stdout)
    except (ValueError, TypeError) as exc:
        raise RepairError("A verificacao retornou uma resposta inesperada: " + child.stdout[-2000:]) from exc
    if Path(result.get("module", "")).resolve() != (root / RELATIVE).resolve():
        raise RepairError("O Python carregou o tradutor de outra pasta: " + result.get("module", "?"))
    return result


def repair(root, payload, report=print):
    root = Path(root).expanduser().resolve()
    required = ("manage.py", "AkynoLeyendBuilder.exe", "nx2/kit.py", "nx2/oot_occlusion.py", "nx2/insn.py", "nx2/lift_fixes.py",
                "akynoleyend/__init__.py", RELATIVE)
    if any(not (root / item).is_file() for item in required):
        raise RepairError("Escolha a pasta AkynoLeyend-0.4.2 que contem AkynoLeyendBuilder.exe: " + str(root))
    version = ast.parse((root / "akynoleyend/__init__.py").read_text(encoding="utf-8-sig"))
    supported = any(isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                    and node.value.value == "0.4.2-rc.1"
                    and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
                    for node in version.body)
    if not supported:
        raise RepairError("Este aplicador atende somente ao AkynoLeyend 0.4.2-rc.1.")
    target = (root / RELATIVE).resolve()
    if not target.is_relative_to(root):
        raise RepairError("O caminho do tradutor aponta para fora da instalacao selecionada.")
    replacement = Path(payload).read_bytes()
    if fingerprint(replacement) != CORRECTED:
        raise RepairError("O arquivo de correcao esta incompleto ou nao corresponde a esta revisao.")
    ast.parse(replacement.decode("utf-8"))
    with build_lock(root):
        previous = target.read_bytes()
        old_hash = fingerprint(previous)
        if old_hash not in {ORIGINAL, CORRECTED}:
            raise RepairError("O tradutor possui alteracoes diferentes desta base; nenhum arquivo foi substituido.\n"
                              + str(target) + "\nSHA-256: " + old_hash)
        report("Instalacao selecionada: " + str(root))
        before = probe(root)
        report("Modulo carregado: " + before["module"])
        backup = None
        if old_hash == ORIGINAL:
            directory = root / "work/repairs" / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
            directory.mkdir(parents=True)
            backup = directory / "a64_lift.py.bak"
            backup.write_bytes(previous)
            try:
                atomic_write(target, replacement)
                after = probe(root)
                if not after.get("has_after") or after.get("verified_sites") != 6:
                    raise RepairError("O tradutor substituido nao passou na verificacao dos seis pontos.")
                if fingerprint(target.read_bytes()) != CORRECTED:
                    raise RepairError("O arquivo foi alterado durante a verificacao.")
            except Exception:
                atomic_write(target, previous)
                report("A verificacao falhou; o arquivo anterior foi restaurado.")
                raise
        else:
            after = before
            if not after.get("has_after") or after.get("verified_sites") != 6:
                raise RepairError("O arquivo ja corresponde a correcao, mas a verificacao de importacao falhou.")
        record = {"root": str(root), "module": after["module"], "changed": backup is not None,
                  "before_sha256": old_hash, "after_sha256": CORRECTED,
                  "verified_sites": after["verified_sites"], "backup": str(backup) if backup else None}
        log = root / "work/logs/reparo-lift.json"
        log.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(log, (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        report("CORRECAO CONFIRMADA: Lifter.after e os seis pontos foram verificados.")
        report("Abra este Builder: " + str(root / "AkynoLeyendBuilder.exe"))
        report("Clique Criar com a mesma entrada e destino. Mantenha a pasta work.")
        report("Registro: " + str(log))
        return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--payload", type=Path, default=Path(__file__).resolve().parent.parent / RELATIVE)
    args = parser.parse_args(argv)
    try:
        repair(args.root, args.payload)
    except (RepairError, OSError, subprocess.TimeoutExpired, SyntaxError) as exc:
        print("ERRO: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
