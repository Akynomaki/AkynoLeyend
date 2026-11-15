"""Private staging ACLs name the token user, not Windows' elevated default owner."""

import ctypes as c
import os
from pathlib import Path
import re

SID_PATTERN = re.compile(r"S-1-(?:[0-9]+-)*[0-9]+\Z")


def private_sddl(sid: str) -> str:
    if not SID_PATTERN.fullmatch(sid):
        raise ValueError("SID Windows invalido")
    # Keep private staging: SYSTEM, Administrators and this user only. No Everyone ACE.
    return f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;{sid})"


class Security:
    def __init__(self):
        if os.name != "nt":
            raise OSError("A API de permissoes requer Windows.")
        self.kernel = c.WinDLL("kernel32", use_last_error=True)
        self.adv = c.WinDLL("advapi32", use_last_error=True)
        pointer, dword, boolean = c.c_void_p, c.c_uint32, c.c_int32
        self.kernel.GetCurrentProcess.argtypes = []
        self.kernel.GetCurrentProcess.restype = pointer
        self.kernel.CloseHandle.argtypes = [pointer]
        self.kernel.CloseHandle.restype = boolean
        self.kernel.LocalFree.argtypes = [pointer]
        self.kernel.LocalFree.restype = pointer
        self.adv.OpenProcessToken.argtypes = [pointer, dword, c.POINTER(pointer)]
        self.adv.OpenProcessToken.restype = boolean
        self.adv.GetTokenInformation.argtypes = [pointer, c.c_int, pointer, dword, c.POINTER(dword)]
        self.adv.GetTokenInformation.restype = boolean
        self.adv.ConvertSidToStringSidW.argtypes = [pointer, c.POINTER(c.c_wchar_p)]
        self.adv.ConvertSidToStringSidW.restype = boolean
        self.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            c.c_wchar_p, dword, c.POINTER(pointer), c.POINTER(dword)]
        self.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = boolean
        self.adv.GetSecurityDescriptorDacl.argtypes = [
            pointer, c.POINTER(boolean), c.POINTER(pointer), c.POINTER(boolean)]
        self.adv.GetSecurityDescriptorDacl.restype = boolean
        self.adv.SetNamedSecurityInfoW.argtypes = [c.c_wchar_p, c.c_int, dword,
                                                  pointer, pointer, pointer, pointer]
        self.adv.SetNamedSecurityInfoW.restype = dword

    def user_sid(self) -> str:
        token = c.c_void_p()
        if not self.adv.OpenProcessToken(self.kernel.GetCurrentProcess(), 0x8, c.byref(token)):
            raise c.WinError(c.get_last_error())
        try:
            length = c.c_uint32()
            self.adv.GetTokenInformation(token, 1, None, 0, c.byref(length))  # TokenUser
            if not length.value or length.value > 1 << 20:
                raise c.WinError(c.get_last_error())
            data = c.create_string_buffer(length.value)
            if not self.adv.GetTokenInformation(token, 1, data, length, c.byref(length)):
                raise c.WinError(c.get_last_error())
            # TOKEN_USER begins with SID_AND_ATTRIBUTES; its first field is a SID pointer.
            sid = c.cast(data, c.POINTER(c.c_void_p))[0]
            text = c.c_wchar_p()
            if not self.adv.ConvertSidToStringSidW(sid, c.byref(text)):
                raise c.WinError(c.get_last_error())
            try:
                return text.value
            finally:
                self.kernel.LocalFree(c.cast(text, c.c_void_p))
        finally:
            self.kernel.CloseHandle(token)

    def protect_directory(self, path: Path) -> None:
        descriptor = c.c_void_p()
        if not self.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                private_sddl(self.user_sid()), 1, c.byref(descriptor), None):
            raise c.WinError(c.get_last_error())
        try:
            present, defaulted, acl = c.c_int32(), c.c_int32(), c.c_void_p()
            if not self.adv.GetSecurityDescriptorDacl(descriptor, c.byref(present), c.byref(acl), c.byref(defaulted)):
                raise c.WinError(c.get_last_error())
            if not present.value or not acl:
                raise OSError("O descritor de staging nao contem uma DACL explicita.")
            name = os.path.abspath(path)
            if not name.startswith("\\\\?\\"):
                name = "\\\\?\\UNC\\" + name[2:] if name.startswith("\\\\") else "\\\\?\\" + name
            # SE_FILE_OBJECT; DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION.
            status = self.adv.SetNamedSecurityInfoW(name, 1, 0x80000004, None, None, acl, None)
            if status:
                raise c.WinError(status)
        finally:
            self.kernel.LocalFree(descriptor)


def protect_staging(path: Path) -> None:
    Security().protect_directory(path)
