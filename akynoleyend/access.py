"""Read-only evidence for launch failures, independent of build verification."""

import ctypes
import datetime as dt
import errno
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import zipfile

from . import __version__
from .config import MANIFEST, ROOT
from .legacy import OLD_MANIFEST, OLD_EXE, OLD_DLL
from .errors import ProjectError
from .files import write_json

REQUIRED = (MANIFEST, "AkynoLeyend.exe", "AkynoLeyend.dll", "image.bin")


def error_info(error: OSError) -> dict:
    return {
        "type": type(error).__name__,
        "errno": error.errno,
        "winerror": getattr(error, "winerror", None),
        "message": str(error),
    }


def access_hint(error: OSError) -> str:
    code = getattr(error, "winerror", None)
    if code in (32, 33):
        return "Outro processo bloqueou o arquivo; feche a outra instancia ou o extrator e tente novamente."
    if isinstance(error, FileNotFoundError):
        return "O arquivo nao esta disponivel neste caminho; confira a pasta escolhida e o historico de protecao."
    if isinstance(error, IsADirectoryError):
        return "Este caminho e uma pasta, mas deveria ser um arquivo."
    return (
        "A causa do bloqueio ainda precisa ser identificada. Execute suporte/Diagnosticar-Acesso.cmd; "
        "preserve work e jogo. Nao e necessario recompilar para coletar o diagnostico."
    )


class FileAccessError(ProjectError):
    def __init__(self, path: Path, error: OSError, operation: str = "ler"):
        self.path, self.original, self.operation = path, error, operation
        code = getattr(error, "winerror", None)
        detail = f"WinError {code}" if code is not None else f"errno {error.errno}"
        super().__init__(f"Nao foi possivel {operation} {path} ({detail}). {access_hint(error)}")


def regular_file(path: Path) -> None:
    """Do not hide an access failure behind Path.is_file() returning False."""
    try:
        mode = path.stat().st_mode
        if stat.S_ISDIR(mode):
            raise IsADirectoryError(errno.EISDIR, "o caminho e uma pasta", str(path))
        if not stat.S_ISREG(mode):
            raise OSError(errno.EINVAL, "o caminho nao e um arquivo regular", str(path))
    except OSError as error:
        raise FileAccessError(path, error, "consultar") from error


def windows_read_probe(path: Path) -> dict:
    """Opening read-only retains GetLastError when the CRT reports only errno 13."""
    if os.name != "nt":
        return {"status": "not_windows"}
    from ctypes import wintypes

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = (wintypes.HANDLE,)
    api.CloseHandle.restype = wintypes.BOOL
    name = os.path.abspath(path)
    if not name.startswith("\\\\?\\"):
        name = "\\\\?\\UNC\\" + name[2:] if name.startswith("\\\\") else "\\\\?\\" + name
    # GENERIC_READ, share READ/WRITE/DELETE, OPEN_EXISTING: no creation or modification.
    handle = api.CreateFileW(name, 0x80000000, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        code = ctypes.get_last_error()
        return {"status": "blocked", "winerror": code, "message": ctypes.FormatError(code).strip()}
    api.CloseHandle(handle)
    return {"status": "open_read_ok"}


def inspect_file(path: Path) -> dict:
    result = {"path": str(path)}
    try:
        info = path.stat()
        result.update(
            kind="directory"
            if stat.S_ISDIR(info.st_mode)
            else "file"
            if stat.S_ISREG(info.st_mode)
            else "other",
            size=info.st_size,
            mode=oct(stat.S_IMODE(info.st_mode)),
        )
        attrs = getattr(info, "st_file_attributes", 0)
        result.update(
            windows_attributes=attrs,
            encrypted=bool(attrs & 0x4000),
            reparse_point=bool(attrs & 0x400),
        )
        if not stat.S_ISREG(info.st_mode):
            result["status"] = "not_a_file"
            return result
        with path.open("rb") as source:
            sample = source.read(16)
        result.update(status="readable", bytes_read=len(sample))
    except OSError as error:
        result.update(
            status="missing" if isinstance(error, FileNotFoundError) else "blocked",
            error=error_info(error),
        )
        try:
            result["native_read"] = windows_read_probe(path)
        except (OSError, AttributeError) as native_error:
            result["native_read"] = {"status": "unavailable", "message": str(native_error)}
    return result


def system_query(name: str, arguments: list[str]) -> dict:
    """Only small, read-only queries. No shell, recursion, ACL or security changes."""
    executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / name
    try:
        child = subprocess.run(
            [str(executable), *arguments],
            capture_output=True,
            timeout=6,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        encoding = "oem" if os.name == "nt" else "utf-8"
        return {
            "exit_code": child.returncode,
            "output": (child.stdout + child.stderr)[:32768].decode(encoding, errors="replace"),
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"error": str(error)}


def access_report(
    folder: Path, *, failure: FileAccessError | None = None, windows_details: bool = False
) -> dict:
    required = REQUIRED
    try:
        (folder / MANIFEST).stat()
    except FileNotFoundError:
        try:
            (folder / OLD_MANIFEST).stat()
            required = (OLD_MANIFEST, OLD_EXE, OLD_DLL, "image.bin")
        except OSError:
            pass
    except OSError:
        pass
    probes = [inspect_file(folder / name) for name in required]
    report = {
        "schema": 1,
        "phase": "before_game_start",
        "launcher_version": __version__,
        "time": dt.datetime.now().astimezone().isoformat(),
        "game_folder": str(folder),
        "files": probes,
        "game_started": False,
        "note": "Leitura inicial de ate 16 bytes; nao substitui a conferencia SHA-256 ao jogar.",
    }
    if failure is not None:
        report["failure"] = {
            "path": str(failure.path),
            "operation": failure.operation,
            **error_info(failure.original),
        }
    if windows_details and os.name == "nt":
        report["windows"] = {
            "user": system_query("whoami.exe", ["/user"]),
            "game_processes": system_query(
                "tasklist.exe", ["/FI", "IMAGENAME eq " + required[1], "/FO", "CSV"]
            ),
            "acls": [
                {"path": p["path"], **system_query("icacls.exe", [p["path"]])}
                for p in probes
                if p["status"] in {"blocked", "not_a_file"}
            ],
        }
    return report


def save_access_report(
    folder: Path,
    *,
    failure: FileAccessError | None = None,
    windows_details: bool = False,
    destination: Path | None = None,
) -> tuple[Path, bool]:
    report = access_report(folder, failure=failure, windows_details=windows_details)
    good = all(p["status"] == "readable" for p in report["files"])
    roots = (
        [destination]
        if destination
        else [
            ROOT / "diagnosticos-acesso",
            Path(tempfile.gettempdir()) / "AkynoLeyend-diagnosticos-acesso",
        ]
    )
    last_error = None
    for base in roots:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f") + f"-{os.getpid()}"
        location = base / stamp
        try:
            location.mkdir(parents=True)
            write_json(location / "acesso.json", report)
            lines = [
                "DIAGNOSTICO DE ACESSO AKYNOLEYEND",
                "Etapa: antes de iniciar o jogo",
                f"Lancador: {__version__}",
                f"Pasta do jogo: {folder}",
                "",
            ]
            if failure:
                lines += [str(failure), ""]
            for p in report["files"]:
                lines.append(f"{Path(p['path']).name}: {p['status']} ({p['path']})")
                if "error" in p:
                    lines.append("  " + str(p["error"]))
                if "native_read" in p:
                    lines.append("  Leitura Windows: " + str(p["native_read"]))
                if p.get("encrypted"):
                    lines.append(
                        "  Atributo EFS presente; isso sozinho nao prova a causa do bloqueio."
                    )
            lines += [
                "",
                "O relatorio nao contem executavel, dados do jogo ou saves.",
                "Nao foram alteradas permissoes, antivirus ou Registro do Windows.",
                "Arquivos legiveis neste teste ainda passam pelo SHA-256 quando voce usa Jogar.",
            ]
            (location / "acesso.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            archive = location.with_suffix(".zip")
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
                for name in ("acesso.json", "acesso.txt"):
                    output.write(location / name, name)
            return archive, good
        except OSError as error:
            last_error = error
    raise ProjectError(
        f"Nao foi possivel gravar o diagnostico de acesso: {last_error}"
    ) from last_error
