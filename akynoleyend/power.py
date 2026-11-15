"""Windows build power requests, scoped to this process and build duration.

Adapted from the supplied Hookshot pointer-lighting-2 builder. No power-plan
or priority setting is changed. Missing APIs do not prevent compilation.
"""

from contextlib import contextmanager
import ctypes
import os


def no_throttle(handle=None) -> bool:
    if os.name != "nt":
        return False
    try:
        class State(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint32) for name in ("version", "control", "state")]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        setter = kernel.SetProcessInformation
        setter.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        setter.restype = ctypes.c_int
        process = ctypes.c_void_p(int(handle)) if handle is not None else kernel.GetCurrentProcess()
        state = State(1, 1, 0)
        return bool(setter(process, 4, ctypes.byref(state), ctypes.sizeof(state)))
    except (AttributeError, OSError, TypeError, ValueError):
        return False


@contextmanager
def keep_awake(*, setter=None):
    if setter is None:
        if os.name != "nt":
            yield
            return
        try:
            setter = ctypes.WinDLL("kernel32", use_last_error=True).SetThreadExecutionState
            setter.argtypes = [ctypes.c_uint32]
            setter.restype = ctypes.c_uint32
        except (AttributeError, OSError):
            yield
            return
    previous = setter(0x80000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    try:
        yield
    finally:
        if previous:
            setter(previous)
