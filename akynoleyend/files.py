"""Small filesystem operations shared by the build and launcher."""

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .errors import ProjectError


@contextmanager
def workspace_stage(*, prefix: str, dir: Path, _acl=None):
    """Keep staging private and readable by its creating user after an elevated build."""
    with tempfile.TemporaryDirectory(prefix=prefix, dir=dir) as name:
        folder = Path(name)
        if _acl is not None:
            _acl(folder)
        elif os.name == "nt":
            from .windows_acl import protect_staging
            protect_staging(folder)
        yield folder


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    """Publish a complete JSON document; never leave a half-written manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProjectError(f"Nao foi possivel ler {path}: {error}") from error
    if not isinstance(value, dict):
        raise ProjectError(f"Manifesto invalido: {path}")
    return value


def overlap(first: Path, second: Path) -> bool:
    a, b = first.resolve(), second.resolve()
    return a == b or a in b.parents or b in a.parents


def require_separate(output: Path, source: Path) -> None:
    if overlap(output, source):
        raise ProjectError(f"A pasta de saida deve ficar separada da entrada: {output} / {source}")


@contextmanager
def workspace_lock(folder: Path):
    """OS-owned lock: released even if the process crashes."""
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "build.lock").open("a+b") as stream:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ProjectError(f"Outra compilacao esta usando {folder}.") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
