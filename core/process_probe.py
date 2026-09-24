"""Tell a running game apart from a Windows zombie process entry.

`tasklist` lists processes that have already terminated but whose kernel object
is still alive because something else holds a handle to them. Those entries have
no threads, cannot be killed, and are not the game running. Treating them as a
running game blocks helper installs and shows a Stop button that cannot work, so
liveness is decided by asking the kernel whether the process is still active
rather than by whether a name appears in a list.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import subprocess


if os.name == "nt":
    TH32CS_SNAPPROCESS = 0x00000002
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _KERNEL32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _KERNEL32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _KERNEL32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _KERNEL32.Process32FirstW.restype = wintypes.BOOL
    _KERNEL32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _KERNEL32.Process32NextW.restype = wintypes.BOOL
    _KERNEL32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _KERNEL32.OpenProcess.restype = wintypes.HANDLE
    _KERNEL32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _KERNEL32.GetExitCodeProcess.restype = wintypes.BOOL
    _KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
    _KERNEL32.CloseHandle.restype = wintypes.BOOL


def _rows(executable: str, extra_filters: tuple[str, ...] = ()) -> list[dict]:
    if os.name == "nt" and not extra_filters:
        snapshot = _KERNEL32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot not in (None, 0, wintypes.HANDLE(-1).value):
            try:
                entry = PROCESSENTRY32W()
                entry.dwSize = ctypes.sizeof(entry)
                rows = []
                available = _KERNEL32.Process32FirstW(snapshot, ctypes.byref(entry))
                while available:
                    if entry.szExeFile.casefold() == executable.casefold():
                        rows.append({"name": entry.szExeFile,
                                     "pid": str(int(entry.th32ProcessID)),
                                     "threads": int(entry.cntThreads), "memory": ""})
                    available = _KERNEL32.Process32NextW(snapshot, ctypes.byref(entry))
                return rows
            finally:
                _KERNEL32.CloseHandle(snapshot)
    command = ["tasklist", "/FI", f"IMAGENAME eq {executable}"]
    for value in extra_filters:
        command += ["/FI", value]
    command += ["/FO", "CSV", "/NH"]
    try:
        listing = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=10, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in listing.splitlines():
        fields = [field.strip('"') for field in line.split('","')]
        if len(fields) < 2 or fields[0].casefold() != executable.casefold():
            continue
        found.append({
            "name": fields[0],
            "pid": fields[1],
            "memory": fields[4].strip() if len(fields) > 4 else "",
        })
    return found


def _is_live(pid: str | int) -> bool:
    """Ask the process object for its exit code; names and window status lie."""
    if os.name != "nt":
        return False
    handle = _KERNEL32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        return bool(_KERNEL32.GetExitCodeProcess(handle, ctypes.byref(code))) \
            and int(code.value) == STILL_ACTIVE
    finally:
        _KERNEL32.CloseHandle(handle)


def live_processes(executables) -> list[dict]:
    """Processes that are actually running.

    GetExitCodeProcess is what separates a real process from a terminated one
    Windows still lists. Window-manager status is not a liveness contract.
    """
    if os.name != "nt":
        return []
    live = []
    for executable in executables:
        live.extend(row for row in _rows(executable) if _is_live(row["pid"]))
    return live


def zombie_processes(executables) -> list[dict]:
    """Terminated processes Windows still lists.

    These have no threads left, so they cannot be killed. They clear when
    whatever holds a handle to them exits, or on the next restart.
    """
    if os.name != "nt":
        return []
    zombies = []
    for executable in executables:
        zombies.extend(row for row in _rows(executable) if not _is_live(row["pid"]))
    return zombies


def running(executables) -> list[dict]:
    """Every listed process, marked with whether it is actually alive."""
    live = {row["pid"] for row in live_processes(executables)}
    rows = []
    for executable in executables:
        for row in _rows(executable):
            rows.append({**row, "live": row["pid"] in live})
    return rows
