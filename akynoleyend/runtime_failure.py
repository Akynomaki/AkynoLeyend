"""Recognize explicit renderer failures without loading a whole diagnostic log."""
from pathlib import Path
import re

DEVICE_LOST_EXIT = 70
_LOST = re.compile(rb"\bvk: (?:GPU_FATAL device_lost\b|device lost: reading\b)")


def renderer_failure(path: Path) -> dict | None:
    # Bounded reads also handle a truncated/unterminated last line. A very long
    # line is scanned in overlapping pieces, never accumulated in memory.
    try:
        with path.open("rb") as stream:
            tail = b""
            while block := stream.read(64 << 10):
                data = tail + block
                match = _LOST.search(data)
                if match:
                    evidence = data[match.start():match.start() + 512].split(b"\n", 1)[0]
                    return {"kind": "device_lost", "exit_code": DEVICE_LOST_EXIT,
                            "evidence": evidence.decode("utf-8", errors="replace")}
                tail = data[-128:]
    except OSError as error:
        return {"kind": "log_unavailable", "error": str(error)}
    return None


COMMIT_LIMIT_EXIT = 0xC000012D   # STATUS_COMMITMENT_LIMIT: the host stops with it at the first refused commit
_COMMIT = re.compile(rb"system commit (\d+) MB used of (\d+) \((\d+) free\); this process (\d+) MB private")
_REFUSED = re.compile(rb"mem: OUT OF MEMORY|failed \(error 1455\)")
VIRTUAL_MEMORY_MESSAGE = (
    "Memoria virtual insuficiente: o Windows ficou sem memoria (RAM + arquivo de paginacao) para o jogo. "
    "Isto nao e falta de VRAM. Feche outros programas ou aumente o arquivo de paginacao do Windows e tente de novo. "
    "Os numeros estao no diagnostico desta tentativa (erros.log, linhas 'mem:').")


def memory_failure(path: Path, status) -> dict | None:
    """A run that ended because Windows had no commit left, from its exit code and the host's own 'mem:' lines.

    Read line by line with a bounded line length; nothing is kept but the last figures.
    """
    code = status & 0xFFFFFFFF if isinstance(status, int) else None
    if code in (None, 0):
        return None
    refused, last = False, None
    try:
        with path.open("rb") as stream:
            while line := stream.readline(4096):
                if b"mem:" not in line:
                    continue
                refused = refused or _REFUSED.search(line) is not None
                match = _COMMIT.search(line)
                if match:
                    last = tuple(int(x) for x in match.groups())
    except OSError:
        return None
    # (without the host's stop: the commit all but gone when the run died of something else)
    exhausted = last is not None and (last[2] < 1024 or last[0] * 100 >= last[1] * 97)
    if code != COMMIT_LIMIT_EXIT and not refused and not exhausted:
        return None
    result = {"kind": "virtual_memory", "exit_code": code, "refused_commit": refused or code == COMMIT_LIMIT_EXIT}
    if last:
        result.update({"commit_used_mb": last[0], "commit_limit_mb": last[1], "commit_free_mb": last[2],
                       "process_private_mb": last[3]})
    return result


# (r6) Before the game starts. Measured on this game: besides its 6.9 GB heap the process commits about 12 GB (the
# game's address regions, the renderer, and Windows' reservation for each allocation of video memory), so about
# 19 GB of commit in a scene. The idea of the notice is Hookshot v2.1.0's (its boot warning, "memory and swap below
# what the game needs"); the figures and the text are this project's.
COMMIT_NEEDED_MB = 19 * 1024
COMMIT_USED_MB = 11 * 1024


def system_commit_mb() -> tuple[int, int] | None:
    """(commit free, commit limit) in MB as this process may use them; None where Windows does not say."""
    try:
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [
                (name, ctypes.c_uint64)
                for name in ("phys_total", "phys_free", "commit_limit", "commit_free", "virtual_total",
                             "virtual_free", "extended")
            ]

        status = Status()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return status.commit_free >> 20, status.commit_limit >> 20
    except (AttributeError, OSError, ValueError):
        return None


def low_memory_notice(free_mb: int, limit_mb: int, needed_mb: int = COMMIT_NEEDED_MB) -> str | None:
    """The line said before the game starts when Windows has less commit free than a scene needs; None otherwise."""
    if free_mb >= needed_mb:
        return None
    # (r8, measured in Kokiri at 1080p with the heap on demand: about 10 GB of the process is memory it really uses,
    # whatever is left of the 21 GB it commits; below that no saving in the game makes the scene fit)
    certain = (
        " Com menos de %d GB livres a cena nao cabe: o jogo vai fechar ao carregar. Aumente o arquivo de paginacao "
        "antes de jogar." % (COMMIT_USED_MB // 1024)
        if free_mb < COMMIT_USED_MB else ""
    )
    return (
        "Aviso de memoria: o Windows tem %.1f GB de memoria virtual livre (limite %.1f GB: RAM + arquivo de "
        "paginacao) e o jogo usa cerca de %d GB numa cena. O jogo vai reservar o heap aos poucos para caber, "
        "mas pode fechar ao carregar uma area: feche outros programas ou aumente o arquivo de paginacao do "
        "Windows (por exemplo, tamanho fixo de 32 GB)."
        % (free_mb / 1024, limit_mb / 1024, needed_mb // 1024)
    ) + certain
