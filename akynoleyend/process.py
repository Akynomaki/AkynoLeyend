"""One subprocess runner for all build stages, with a bounded error tail."""

import os
import signal
import subprocess
import sys
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .errors import ProjectError
from .power import no_throttle


def stop(child: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(child.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()


def run(
    command: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    log: Path,
    on_line: Callable[[str], None] = print,
) -> None:
    command = list(command)
    if command and Path(command[0]).resolve() == Path(sys.executable).resolve():
        command[1:1] = ["-X", "utf8"]
    log.parent.mkdir(parents=True, exist_ok=True)
    tail: deque[str] = deque(maxlen=16)
    with log.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("COMMAND " + subprocess.list2cmdline(command) + "\n")
        try:
            child = subprocess.Popen(
                command,
                cwd=cwd,
                env=dict(environment),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=os.name != "nt",
            )
        except OSError as error:
            raise ProjectError(f"Nao foi possivel iniciar {command[0]}: {error}") from error
        no_throttle(getattr(child, "_handle", None))
        try:
            assert child.stdout is not None
            for raw in child.stdout:
                line = raw.rstrip("\r\n")
                stream.write(line + "\n")
                stream.flush()
                tail.append(line)
                on_line(line)
            status = child.wait()
        except BaseException:
            stop(child)
            raise
        finally:
            if child.stdout is not None:
                child.stdout.close()
    if status:
        detail = "\n".join(tail)
        raise ProjectError(f"Etapa interrompida (codigo {status}). Registro: {log}\n{detail}")
