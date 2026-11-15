"""Opt-in short RomFS path for the inherited ANSI/MAX_PATH runtime.

Only the DOS device name is temporary. No game file is moved or copied.
Removal matches our exact target and never removes another mapping.
"""

from contextlib import contextmanager
import ctypes
import ntpath
import os

from .errors import ProjectError


def nt_target(path: str) -> str:
    path = ntpath.normpath(path)
    if path.startswith("\\\\?\\UNC\\"):
        return "\\??\\UNC\\" + path[8:]
    if path.startswith("\\\\?\\"):
        path = path[4:]
    if path.startswith("\\\\"):
        return "\\??\\UNC\\" + path[2:]
    drive, rest = ntpath.splitdrive(path)
    if len(drive) != 2 or not rest.startswith("\\"):
        raise ProjectError("O caminho de RomFS deve ser absoluto para criar um alias.")
    return "\\??\\" + path


class WindowsDrives:
    def __init__(self):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.query = kernel.QueryDosDeviceW
        self.query.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        self.query.restype = ctypes.c_uint32
        self.define = kernel.DefineDosDeviceW
        self.define.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_wchar_p]
        self.define.restype = ctypes.c_int
        self.logical = kernel.GetLogicalDrives
        self.logical.argtypes = []
        self.logical.restype = ctypes.c_uint32

    def available(self, letter: str) -> bool:
        if self.logical() & (1 << (ord(letter) - ord("A"))):
            return False
        buf = ctypes.create_unicode_buffer(32768)
        if self.query(letter + ":", buf, len(buf)):
            return False
        # An inaccessible or disconnected device is not an available name.
        return ctypes.get_last_error() == 2

    def create(self, letter: str, target: str) -> bool:
        return bool(self.define(0x1 | 0x8, letter + ":", target))

    def remove(self, letter: str, target: str) -> bool:
        return bool(self.define(0x1 | 0x2 | 0x4 | 0x8, letter + ":", target))


@contextmanager
def short_romfs(path: str, *, api=None):
    if api is None:
        if os.name != "nt":
            raise ProjectError("O alias de RomFS requer Windows.")
        api = WindowsDrives()
    target = nt_target(path)
    for code in range(ord("Z"), ord("D") - 1, -1):
        letter = chr(code)
        if api.available(letter) and api.create(letter, target):
            try:
                yield letter + ":\\"
            finally:
                if not api.remove(letter, target):
                    raise ProjectError(
                        f"Nao foi possivel remover o alias temporario {letter}: de RomFS. "
                        f"Feche o jogo e remova somente esse alias com subst {letter}: /D."
                    )
            return
    raise ProjectError(
        "Nao foi possivel reservar uma letra livre para o teste de RomFS. "
        "Nenhum mapeamento existente foi substituido."
    )
