"""Read-only reuse of proven old game objects in an isolated validation workspace."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

from .build_support import object_key
from .errors import ProjectError


def isolated_game_jobs(jobs, *, root, work, previous_root, report=print):
    """Keep original include flags for cached GAME jobs; host jobs are never passed here.

    The previous root must use its usual work/ layout. Sources and include closure
    must be identical. Compiler, non-include flags and dependency bytes participate
    in the exact original object key. No compiler is invoked and no old file is written.
    """
    root, work, previous_root = (Path(p).resolve() for p in (root, work, previous_root))
    previous_work = previous_root / "work"
    if root == previous_root or work == previous_work or work in previous_work.parents or previous_work in work.parents:
        raise ProjectError("Reuso isolado exige work independente da instalacao anterior.")
    include_pairs = set()
    prepared = []

    def old_path(path):
        path = Path(path).resolve()
        for current, previous in ((work, previous_work), (root, previous_root)):
            if path == current or current in path.parents:
                return previous / path.relative_to(current)
        raise ProjectError("Caminho de compilacao fora da copia isolada: " + str(path))

    def checked_file(path):
        if not path.is_file() or path.is_symlink():
            raise ProjectError("Arquivo regular de reuso ausente ou com link: " + str(path))
        return path.read_bytes()

    def same_headers(current, previous):
        pair = (current, previous)
        if pair in include_pairs:
            return
        suffixes = {".h", ".hpp", ".inc", ".def", ".c", ".cc", ".cpp"}
        def tree(folder):
            if not folder.is_dir() or folder.is_symlink():
                raise ProjectError("Include de reuso ausente/com link: " + str(folder))
            result = {}
            for p in folder.rglob("*"):
                if p.is_symlink():
                    raise ProjectError("Link em include de reuso: " + str(p))
                if p.is_file() and p.suffix.lower() in suffixes:
                    result[p.relative_to(folder).as_posix()] = hashlib.sha256(p.read_bytes()).digest()
            return result
        if tree(current) != tree(previous):
            raise ProjectError("C/headers diferentes no reuso isolado: " + str(current))
        include_pairs.add(pair)

    # Validate the entire plan before copying the first object.
    for compiler, source, output, flags, dependencies in jobs:
        source, output = Path(source).resolve(), Path(output).resolve()
        if work not in source.parents or work not in output.parents:
            raise ProjectError("Reuso isolado aceita apenas jobs traduzidos dentro da work candidata.")
        original_source = old_path(source)
        if checked_file(source) != checked_file(original_source):
            raise ProjectError("C traduzido diferente no reuso: " + source.name)
        original_flags = []
        includes = 0
        for flag in flags:
            if flag.startswith("-I"):
                if flag == "-I":
                    raise ProjectError("Use caminhos de include anexados a -I no reuso isolado.")
                current = Path(flag[2:]).resolve()
                previous = old_path(current)
                same_headers(current, previous)
                original_flags.append("-I" + str(previous))
                includes += 1
            else:
                original_flags.append(flag)
        if not includes:
            raise ProjectError("Job sem includes verificaveis no reuso isolado.")
        key = object_key(compiler, str(original_source), original_flags, dependencies)
        original_output = old_path(output)
        stamp = Path(str(original_output) + ".sha256")
        if original_output.is_file() and stamp.is_file() and stamp.read_text() == key:
            chosen = original_output
        else:
            chosen = previous_work / "objcache" / (key + ".o")
            if not chosen.is_file():
                raise ProjectError("Objeto/chave original ausente ou diferente: " + source.name + "; nenhuma compilacao iniciada.")
        data = checked_file(chosen)
        if not data:
            raise ProjectError("Objeto original vazio: " + str(chosen))
        if output.exists() and os.path.samefile(chosen, output):
            raise ProjectError("Objeto candidato e original sao o mesmo arquivo/link; use copia independente.")
        job = (compiler, str(source), str(output), original_flags, dependencies)
        if object_key(compiler, str(source), original_flags, dependencies) != key:
            raise ProjectError("Chave divergente apos conferencia de reuso: " + source.name)
        prepared.append((job, chosen, key, hashlib.sha256(data).hexdigest()))

    for job, chosen, key, digest in prepared:
        output = Path(job[2])
        output.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=output.name+".", suffix=".reuse", dir=output.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            shutil.copyfile(chosen, temporary)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != digest:
                raise ProjectError("Objeto mudou durante leitura: " + str(chosen))
            temporary.replace(output)
            # Replace the stamp too: an existing hardlink must never write into the old work.
            fd, stamp_name = tempfile.mkstemp(prefix=output.name+".", suffix=".stamp", dir=output.parent)
            stamp_temp = Path(stamp_name)
            try:
                with os.fdopen(fd,"w") as stream:
                    stream.write(key)
                stamp_temp.replace(Path(str(output)+".sha256"))
            finally:
                stamp_temp.unlink(missing_ok=True)
        finally:
            temporary.unlink(missing_ok=True)
    report(f"Reuso isolado: {len(prepared)} objetos conferidos/copias independentes; instalacao anterior somente em leitura.")
    return [item[0] for item in prepared]
