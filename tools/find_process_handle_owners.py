"""Find which Windows processes keep terminated process objects alive."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import sys


if os.name != "nt":
    raise SystemExit("Windows only")


NTDLL = ctypes.WinDLL("ntdll", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
SYSTEM_EXTENDED_HANDLE_INFORMATION = 64
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_DUP_HANDLE = 0x0040
SYNCHRONIZE = 0x00100000
DUPLICATE_SAME_ACCESS = 0x00000002


class HandleEntry(ctypes.Structure):
    _fields_ = [
        ("object", ctypes.c_void_p),
        ("owner_pid", ctypes.c_size_t),
        ("handle", ctypes.c_size_t),
        ("access", wintypes.ULONG),
        ("backtrace", wintypes.USHORT),
        ("type_index", wintypes.USHORT),
        ("attributes", wintypes.ULONG),
        ("reserved", wintypes.ULONG),
    ]


NTDLL.NtQuerySystemInformation.argtypes = [
    wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)
]
NTDLL.NtQuerySystemInformation.restype = wintypes.LONG
KERNEL32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
KERNEL32.OpenProcess.restype = wintypes.HANDLE
KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
KERNEL32.CloseHandle.restype = wintypes.BOOL
KERNEL32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]
KERNEL32.QueryFullProcessImageNameW.restype = wintypes.BOOL
KERNEL32.DuplicateHandle.argtypes = [
    wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
    ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
]
KERNEL32.DuplicateHandle.restype = wintypes.BOOL
KERNEL32.GetProcessId.argtypes = [wintypes.HANDLE]
KERNEL32.GetProcessId.restype = wintypes.DWORD
KERNEL32.GetCurrentProcess.restype = wintypes.HANDLE


def handle_table() -> list[HandleEntry]:
    size = 1 << 20
    while True:
        buffer = ctypes.create_string_buffer(size)
        needed = wintypes.ULONG()
        status = int(NTDLL.NtQuerySystemInformation(
            SYSTEM_EXTENDED_HANDLE_INFORMATION, buffer, size, ctypes.byref(needed)
        )) & 0xFFFFFFFF
        if status == 0:
            break
        if status != STATUS_INFO_LENGTH_MISMATCH:
            raise OSError(f"NtQuerySystemInformation failed: 0x{status:08X}")
        size = max(size * 2, int(needed.value) + (1 << 16))
    count = ctypes.c_size_t.from_buffer(buffer).value
    offset = ctypes.sizeof(ctypes.c_size_t) * 2
    array_type = HandleEntry * count
    return list(array_type.from_buffer_copy(buffer, offset))


def process_name(pid: int) -> str:
    handle = KERNEL32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        text = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(text))
        if KERNEL32.QueryFullProcessImageNameW(handle, 0, text, ctypes.byref(length)):
            return text.value
        return ""
    finally:
        KERNEL32.CloseHandle(handle)


def owners(target_pids: list[int]) -> list[dict]:
    opened = {}
    try:
        for pid in target_pids:
            handle = KERNEL32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
            )
            if handle:
                opened[int(handle)] = pid
        table = handle_table()
        current = os.getpid()
        objects = {
            int(entry.object): opened[int(entry.handle)]
            for entry in table
            if int(entry.owner_pid) == current and int(entry.handle) in opened
        }
        rows = []
        for entry in table:
            target = objects.get(int(entry.object or 0))
            if target is None:
                continue
            owner = int(entry.owner_pid)
            if owner == current and int(entry.handle) in opened:
                continue
            rows.append({
                "targetPid": target,
                "ownerPid": owner,
                "ownerPath": process_name(owner),
                "handle": f"0x{int(entry.handle):X}",
                "access": f"0x{int(entry.access):08X}",
            })
        if rows or len(objects) == len(target_pids):
            return rows

        # A terminated process can deny a fresh OpenProcess call while another
        # process still owns its last handle. Discover the process-object type
        # from a real handle to this process, then duplicate only handles of
        # that type and ask Windows for their target PIDs.
        self_handle = KERNEL32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, current
        )
        if not self_handle:
            return rows
        try:
            refreshed = handle_table()
            process_type = next((
                int(entry.type_index) for entry in refreshed
                if int(entry.owner_pid) == current
                and int(entry.handle) == int(self_handle)
            ), None)
            if process_type is None:
                return rows
            wanted = set(target_pids)
            by_owner: dict[int, wintypes.HANDLE] = {}
            try:
                for entry in refreshed:
                    if int(entry.type_index) != process_type:
                        continue
                    owner = int(entry.owner_pid)
                    owner_handle = by_owner.get(owner)
                    if owner_handle is None:
                        owner_handle = KERNEL32.OpenProcess(PROCESS_DUP_HANDLE, False, owner)
                        by_owner[owner] = owner_handle
                    if not owner_handle:
                        continue
                    duplicate = wintypes.HANDLE()
                    if not KERNEL32.DuplicateHandle(
                        owner_handle, wintypes.HANDLE(int(entry.handle)),
                        KERNEL32.GetCurrentProcess(), ctypes.byref(duplicate),
                        0, False, DUPLICATE_SAME_ACCESS,
                    ):
                        continue
                    try:
                        target = int(KERNEL32.GetProcessId(duplicate))
                    finally:
                        KERNEL32.CloseHandle(duplicate)
                    if target not in wanted or owner == current:
                        continue
                    rows.append({
                        "targetPid": target,
                        "ownerPid": owner,
                        "ownerPath": process_name(owner),
                        "handle": f"0x{int(entry.handle):X}",
                        "access": f"0x{int(entry.access):08X}",
                    })
            finally:
                for owner_handle in by_owner.values():
                    if owner_handle:
                        KERNEL32.CloseHandle(owner_handle)
            return rows
        finally:
            KERNEL32.CloseHandle(self_handle)
    finally:
        for handle in opened:
            KERNEL32.CloseHandle(handle)


if __name__ == "__main__":
    print(json.dumps(owners([int(value) for value in sys.argv[1:]]), indent=2))
