"""Inspect local Termous processes without reading credentials or command lines."""

import ctypes
import errno
import os
from pathlib import Path
import sys


def windows_processes():
    from ctypes import wintypes

    api = ctypes.WinDLL("kernel32", use_last_error=True)

    class ProcessEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                    ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
                    ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent", wintypes.DWORD), ("priority", wintypes.LONG),
                    ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260)]

    api.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    api.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ("Process32FirstW", "Process32NextW"):
        function = getattr(api, name)
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
        function.restype = wintypes.BOOL
    api.ProcessIdToSessionId.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    api.ProcessIdToSessionId.restype = wintypes.BOOL
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                             ctypes.POINTER(wintypes.DWORD)]
    api.QueryFullProcessImageNameW.restype = wintypes.BOOL
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    session = wintypes.DWORD()
    if not api.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)):
        raise ctypes.WinError(ctypes.get_last_error())
    snapshot = api.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    rows, unknown = [], False
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        available = api.Process32FirstW(snapshot, ctypes.byref(entry))
        while available:
            if entry.name.lower() == "termous.exe":
                candidate_session = wintypes.DWORD()
                if not api.ProcessIdToSessionId(entry.pid, ctypes.byref(candidate_session)):
                    unknown = True
                elif candidate_session.value == session.value:
                    handle = api.OpenProcess(0x1000, False, entry.pid)
                    if not handle:
                        unknown = True
                    else:
                        try:
                            size = wintypes.DWORD(32768)
                            buffer = ctypes.create_unicode_buffer(size.value)
                            if api.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                                rows.append({"pid": entry.pid, "executable_path": buffer.value})
                            else:
                                unknown = True
                        finally:
                            api.CloseHandle(handle)
            available = api.Process32NextW(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES is normal termination.
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        api.CloseHandle(snapshot)
    return rows, unknown


def mac_processes():
    api = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    api.proc_listpids.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_int]
    api.proc_listpids.restype = ctypes.c_int
    for name in ("proc_name", "proc_pidpath"):
        function = getattr(api, name)
        function.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        function.restype = ctypes.c_int
    # PROC_UID_ONLY limits enumeration to the current user, including GUI applications.
    size = api.proc_listpids(5, os.getuid(), None, 0)
    if size <= 0:
        raise OSError("Cannot enumerate current-user processes.")
    for _ in range(3):
        size += 4096
        buffer = (ctypes.c_int * ((size + 3) // 4))()
        count = api.proc_listpids(5, os.getuid(), buffer, ctypes.sizeof(buffer))
        if count <= 0:
            raise OSError("Cannot enumerate current-user processes.")
        if count < ctypes.sizeof(buffer):
            break
    else:
        raise OSError("Process list changed too quickly to obtain a complete snapshot.")
    rows, unknown = [], False
    for pid in buffer[:count // ctypes.sizeof(ctypes.c_int)]:
        if pid <= 0:
            continue
        name = ctypes.create_string_buffer(1024)
        if api.proc_name(pid, name, len(name)) <= 0:
            if ctypes.get_errno() != errno.ESRCH:
                unknown = True
            continue
        if name.value != b"Termous":
            continue
        path = ctypes.create_string_buffer(4096)
        if api.proc_pidpath(pid, path, len(path)) <= 0:
            unknown = True
        else:
            rows.append({"pid": pid, "executable_path": os.fsdecode(path.value)})
    return rows, unknown


def linux_processes(root=Path("/proc")):
    rows, unknown = [], False
    for entry in root.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            name = (entry / "comm").read_text().strip().lower()
            if name != "termous" and not (name.startswith(("termous-", "termous.")) and name != "termous-core"):
                continue
            executable = os.readlink(entry / "exe")
            if executable.endswith(" (deleted)"):
                unknown = True
            else:
                rows.append({"pid": int(entry.name), "executable_path": executable})
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (PermissionError, UnicodeError):
            unknown = True
    return rows, unknown


def processes():
    if sys.platform == "win32":
        return windows_processes()
    if sys.platform == "darwin":
        return mac_processes()
    if sys.platform.startswith("linux"):
        return linux_processes()
    raise ValueError("Unsupported platform.")
