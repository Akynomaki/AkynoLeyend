"""Observe the installing computer; never import another machine's optimizer values."""

import ctypes
import os
import platform

GIB = 1 << 30


def snapshot() -> dict:
    total = free = commit = 0
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in
                ("total", "free", "page_total", "page_free", "virtual", "virtual_free", "extended")
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            total, free, commit = int(status.total), int(status.free), int(status.page_free)
    else:
        try:
            page = int(os.sysconf("SC_PAGE_SIZE"))
            total = page * int(os.sysconf("SC_PHYS_PAGES"))
            free = page * int(os.sysconf("SC_AVPHYS_PAGES"))
        except (OSError, ValueError, AttributeError):
            pass
    cpu = platform.processor() or platform.machine()
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    count = getattr(os, "process_cpu_count", os.cpu_count)() or 1
    return {"cpu": cpu, "logical_cpus": max(1, count), "ram_total": total,
            "ram_available": free, "commit_available": commit, "system": platform.system()}


def recommended_chunk(info: dict) -> int:
    # New boundaries only. Keep smaller units when memory or CPU concurrency is limited.
    return 12 if (info["ram_total"] >= 32 * GIB and info["ram_available"] >= 24 * GIB
                  and info["logical_cpus"] >= 8) else 6


# (0.4.4: the r13e branch's exit reasons. 0xC000001D, an illegal instruction, is cpu.py's: since r13j Criar compiles for the
# level the CPU runs, Jogar refuses a build the CPU cannot run, and the reason after the exit names what the CPU lacks from
# CPUID; the r13e text, "this package needs x86-64-v3", and its AVX2 warning before every start no longer hold)
ILLEGAL_INSTRUCTION = 0xC000001D
CONTROL_C_EXIT = 0xC000013A


def low_ram_notice(info: dict, *, preparing: bool) -> str:
    """A line for the console when free RAM is short for preparing shaders: with other programs holding the memory, the
    preparation went from 30 minutes to many hours (one worker, the system paging; seen on Intel with 2 GB of 32 free)."""
    if not preparing or not info.get("ram_total"):
        return ""
    free = info["ram_available"]
    if free >= 6 * GIB:
        return ""
    return ("Aviso: so %.1f GB de RAM livres de %.0f GB. A preparacao de shaders vai usar 1 worker e o Windows vai "
            "paginar: ela pode levar horas. Feche outros jogos e emuladores abertos antes de preparar."
            % (free / GIB, info["ram_total"] / GIB))


PLAY_RAM_FREE = 10 * GIB


def heavy_processes(min_bytes: int = 2 * GIB, limit: int = 3) -> list[tuple[str, int]]:
    """The other programs holding the most private memory (name, bytes), largest first: at most `limit`, each over min_bytes.
    Empty off Windows or when Windows refuses the count."""
    if os.name != "nt":
        return []
    try:
        from ctypes import wintypes
        psapi, kernel32 = ctypes.WinDLL("psapi"), ctypes.WinDLL("kernel32")

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in
                ("peak_ws", "ws", "peak_paged", "paged", "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile", "private")
            ]

        kernel32.OpenProcess.restype = wintypes.HANDLE
        ids = (wintypes.DWORD * 4096)()
        got = wintypes.DWORD()
        if not psapi.EnumProcesses(ids, ctypes.sizeof(ids), ctypes.byref(got)):
            return []
        own, found = os.getpid(), []
        for pid in ids[:got.value // ctypes.sizeof(wintypes.DWORD)]:
            if not pid or pid == own:
                continue
            handle = kernel32.OpenProcess(0x1000, False, pid)   # (PROCESS_QUERY_LIMITED_INFORMATION)
            if not handle:
                continue
            try:
                counters = Counters()
                counters.cb = ctypes.sizeof(counters)
                if not psapi.GetProcessMemoryInfo(wintypes.HANDLE(handle), ctypes.byref(counters), counters.cb):
                    continue
                if counters.private < min_bytes:
                    continue
                name = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(len(name))
                if kernel32.QueryFullProcessImageNameW(wintypes.HANDLE(handle), 0, name, ctypes.byref(size)):
                    found.append((os.path.basename(name.value), int(counters.private)))
            finally:
                kernel32.CloseHandle(wintypes.HANDLE(handle))
        found.sort(key=lambda item: -item[1])
        return found[:limit]
    except (AttributeError, OSError, ValueError):
        return []


def play_ram_notice(info: dict, heavy: list[tuple[str, int]]) -> str:
    """(r13k) A line for the console when free RAM is short for playing. The game takes 10 to 16 GB, and with an integrated GPU
    its video memory too comes out of the RAM: on Intel Graphics it reached 25.8 GB private with 9 GB free at the start (another
    emulator held 26 GB), and the system paged: the disk at 100%, uploads of 224 KB in 431 ms, 1.2 FPS for 22 s."""
    if not info.get("ram_total") or info["ram_available"] >= PLAY_RAM_FREE:
        return ""
    line = ("Aviso: so %.1f GB de RAM livres de %.0f GB. O jogo usa de 10 a 16 GB, e com a placa de video integrada ainda "
            "mais (a memoria de video dela sai da RAM). Com pouca RAM o Windows usa o disco no lugar dela e o jogo trava."
            % (info["ram_available"] / GIB, info["ram_total"] / GIB))
    if heavy:
        line += " Programas que mais ocupam memoria agora: " + ", ".join(
            "%s (%.1f GB)" % (name, size / GIB) for name, size in heavy) + ". Feche os que nao estiver usando."
    return line


def exit_explanation(status: int, *, preparing: bool = False) -> str:
    """The reason to show for an exit code the player cannot read, or an empty string (0xC000001D: cpu.py)."""
    code = status & 0xFFFFFFFF
    if code == CONTROL_C_EXIT:
        what = "A preparacao de shaders foi interrompida" if preparing else "O jogo foi interrompido"
        return (what + " (0xC000013A): a janela do console foi fechada, o processo foi cancelado ou o "
                "Windows encerrou a sessao. Nao e uma falha do jogo.")
    return ""


def usable_memory(info: dict) -> int:
    commit = info.get("commit_available", 0)
    return min(info["ram_available"], commit) if commit else info["ram_available"]


def shader_workers(info: dict, *, background: bool = False) -> int:
    free = usable_memory(info)
    if free <= 0:
        return 1
    memory = max(1, int(max(0, free - 2 * GIB) / (0.75 * GIB)))
    return min(2 if background else 4, max(1, info["logical_cpus"] // 2), memory)
