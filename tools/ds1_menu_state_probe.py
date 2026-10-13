"""Read-only research probe for DS1 issue 754; NOT a favorite-items tweak.

Offline: python tools/ds1_menu_state_probe.py PATH/TO/DarkSoulsRemastered.exe
Windows, explicit process: add --pid PID --samples N for a best-effort
menu-state capture. No writes, injection, debug privilege, hooks, dumps,
or game-code calls. The Windows transport still requires installed-game
validation. Use offline mode by default. Static provenance and unresolved
work: worklog/754.md.

Capture recipe: start sampling, then open and close the Equipment menu a
few times. Samples taken with the menu open differ from closed ones in
the bytes the native slice will gate on.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time
from typing import Callable

BUILD_SHA256 = "a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b"
MAX_FILE = 64 * 1024 * 1024
MENU_RVA = 0x1C7B648
MENU_FLOAT = 0xC2C
MENU_WINDOW = 0xC00
MENU_WINDOW_SIZE = 64
GAME_DATA_RVA = 0x1C8A530
# Minimal structural guards, verified against the pinned on-disk build.
GUARDS = (
    ("frameHook", 0x39761A, "e8119cffff"),
    ("uiFlags", 0x71AC10, "48895c2408"),
    ("quantityIndex", 0x7478CD, "4863c2486354812483faff"),
)
Read = Callable[[int, int], bytes]


class ProbeError(ValueError):
    """Invalid build, unsafe address, incomplete read, or unstable sample."""


def checked_slice(data: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ProbeError("Truncated or out-of-range binary data")
    return data[offset:offset + size]


class PEImage:
    """The minimum bounds-checked PE32+ reader needed for the pinned probe."""

    def __init__(self, data: bytes):
        self.data = data
        if checked_slice(data, 0, 2) != b"MZ":
            raise ProbeError("Not a PE executable")
        pe = struct.unpack("<I", checked_slice(data, 0x3C, 4))[0]
        if checked_slice(data, pe, 4) != b"PE\0\0":
            raise ProbeError("Invalid PE signature")
        machine, count = struct.unpack("<HH", checked_slice(data, pe + 4, 4))
        opt_size = struct.unpack("<H", checked_slice(data, pe + 20, 2))[0]
        opt = checked_slice(data, pe + 24, opt_size)
        if machine != 0x8664 or opt_size < 112 or opt[:2] != b"\x0b\x02":
            raise ProbeError("Expected a Windows x64 PE32+ executable")
        if not 1 <= count <= 96:
            raise ProbeError("Invalid PE section count")
        self.image_size = struct.unpack_from("<I", opt, 56)[0]
        self.sections = []
        table = pe + 24 + opt_size
        for index in range(count):
            row = checked_slice(data, table + index * 40, 40)
            virtual_size, rva, raw_size, raw = struct.unpack_from("<IIII", row, 8)
            span = max(virtual_size, raw_size)
            if rva + span > self.image_size:
                raise ProbeError("Section extends beyond the image")
            checked_slice(data, raw, raw_size)
            self.sections.append((rva, raw, raw_size))

    def read_rva(self, rva: int, size: int) -> bytes:
        if rva < 0 or size <= 0:
            raise ProbeError("Invalid RVA read")
        # Names are not unique: the supplied executable has TWO .text sections.
        for start, raw, raw_size in self.sections:
            if start <= rva and rva + size <= start + raw_size:
                return checked_slice(self.data, raw + rva - start, size)
        raise ProbeError("RVA has no complete on-disk backing")


def inspect_executable(path: Path) -> dict:
    # Bounded even if a file grows after stat; no writable handle is opened.
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ProbeError("Executable exceeds the probe's 64 MiB limit")
    digest = hashlib.sha256(data).hexdigest()
    if digest != BUILD_SHA256:
        raise ProbeError("Unrecognized executable SHA-256; no offsets will be used")
    pe = PEImage(data)
    for name, rva, value in GUARDS:
        expected = bytes.fromhex(value)
        if pe.read_rva(rva, len(expected)) != expected:
            raise ProbeError(f"Static guard mismatch: {name}")
    return {"sha256": digest, "size": len(data), "recognizedBuild": True,
            "staticGuards": [name for name, _, _ in GUARDS],
            "gameplayPatchImplemented": False}


def read_exact(read: Read, address: int, size: int) -> bytes:
    # Conservative x64 user-space limit; never wrap a corrupt pointer.
    if not 0x10000 <= address or not 0 < size <= 4096 or address + size > 0x800000000000:
        raise ProbeError("Invalid or null memory address")
    data = read(address, size)
    if len(data) != size:
        raise ProbeError("Incomplete memory read")
    return data


def number(read: Read, address: int, fmt: str):
    return struct.unpack(fmt, read_exact(read, address, struct.calcsize(fmt)))[0]


def _sample(read: Read, module_base: int) -> tuple:
    menu = number(read, module_base + MENU_RVA, "<Q")
    if not menu:
        return (menu, None, None, None, None)
    window = read_exact(read, menu + MENU_WINDOW, MENU_WINDOW_SIZE)
    gate = struct.unpack_from("<f", window, MENU_FLOAT - MENU_WINDOW)[0]
    gamedata = number(read, module_base + GAME_DATA_RVA, "<Q")
    player = number(read, gamedata + 0x10, "<Q") if gamedata else None
    return (menu, window, gate, gamedata, player)


def sample_menu(read: Read, module_base: int) -> dict:
    """One stable menu-state sample, retrying changed reads at most three times.

    Two equal samples are NOT an atomic snapshot. Equal floats alone would
    not detect menu swaps, so the whole window joins the comparison.
    """
    for _ in range(3):
        first = _sample(read, module_base)
        second = _sample(read, module_base)
        if first != second:
            continue
        menu, window, gate, gamedata, player = first
        if not menu:
            return {"state": "noMenu", "atomic": False}
        return {"state": "sampled", "atomic": False,
                "menuGate": gate, "menuWindowHex": window.hex(),
                "playerLoaded": bool(player)}
    raise ProbeError("Menu state changed during sampling; no sample returned")


class ModuleEntry(ctypes.Structure):
    _fields_ = [(name, w.DWORD) for name in
                ("dwSize", "th32ModuleID", "th32ProcessID", "GlblcntUsage", "ProccntUsage")] + [
        ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", w.DWORD),
        ("hModule", w.HMODULE), ("szModule", w.WCHAR * 256), ("szExePath", w.WCHAR * 260)]


def _same_path(left: str | Path, right: str | Path) -> bool:
    return os.path.normcase(os.path.realpath(left)) == os.path.normcase(os.path.realpath(right))


class WindowsReader:
    """Explicit-PID transport with read/query rights only, never a debugger."""

    def __init__(self, pid: int, executable: Path):
        if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
            raise ProbeError("--pid requires 64-bit Python on Windows")
        if not 0 < pid <= 0xFFFFFFFF:
            raise ProbeError("Invalid process ID")
        if executable.name.casefold() != "darksoulsremastered.exe":
            raise ProbeError("Expected DarkSoulsRemastered.exe")
        self.handle = None
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        specs = {
            "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "CloseHandle": ([w.HANDLE], w.BOOL),
            "QueryFullProcessImageNameW": ([w.HANDLE, w.DWORD, w.LPWSTR,
                                            ctypes.POINTER(w.DWORD)], w.BOOL),
            "ReadProcessMemory": ([w.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)], w.BOOL),
            "CreateToolhelp32Snapshot": ([w.DWORD, w.DWORD], w.HANDLE),
            "Module32FirstW": ([w.HANDLE, ctypes.POINTER(ModuleEntry)], w.BOOL),
            "Module32NextW": ([w.HANDLE, ctypes.POINTER(ModuleEntry)], w.BOOL),
        }
        for name, (args, result) in specs.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        try:
            self.handle = self.api.OpenProcess(0x0010 | 0x1000, False, pid)
            if not self.handle:
                raise ctypes.WinError(ctypes.get_last_error())
            path = ctypes.create_unicode_buffer(32768)
            length = w.DWORD(len(path))
            if not self.api.QueryFullProcessImageNameW(self.handle, 0, path, ctypes.byref(length)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not _same_path(path.value, executable):
                raise ProbeError("PID does not belong to the specified executable")
            inspect_executable(Path(path.value))
            self.base = self._module_base(pid, executable)
            for name, rva, value in GUARDS:
                expected = bytes.fromhex(value)
                if read_exact(self.read, self.base + rva, len(expected)) != expected:
                    raise ProbeError(f"Live guard mismatch: {name}")
        except BaseException:
            self.close()
            raise

    def _module_base(self, pid: int, executable: Path) -> int:
        invalid = ctypes.c_void_p(-1).value
        snapshot = invalid
        for _ in range(3):
            snapshot = self.api.CreateToolhelp32Snapshot(0x00000008, pid)
            if snapshot != invalid:
                break
            if ctypes.get_last_error() != 24:  # ERROR_BAD_LENGTH: documented retry
                raise ctypes.WinError(ctypes.get_last_error())
        if snapshot == invalid:
            raise ProbeError("Module snapshot remained unstable")
        try:
            entry = ModuleEntry()
            entry.dwSize = ctypes.sizeof(entry)
            ok = self.api.Module32FirstW(snapshot, ctypes.byref(entry))
            for _ in range(4096):
                if not ok:
                    break
                if _same_path(entry.szExePath, executable):
                    if not entry.modBaseAddr:
                        raise ProbeError("Null module base")
                    return entry.modBaseAddr
                ok = self.api.Module32NextW(snapshot, ctypes.byref(entry))
            raise ProbeError("Executable module was not found")
        finally:
            self.api.CloseHandle(snapshot)

    def read(self, address: int, size: int) -> bytes:
        if not self.handle:
            raise ProbeError("Process handle is closed")
        if not 0 < size <= 4096:
            raise ProbeError("Unbounded process read refused")
        buffer = ctypes.create_string_buffer(size)
        actual = ctypes.c_size_t()
        if not self.api.ReadProcessMemory(self.handle, address, buffer, size, ctypes.byref(actual)):
            raise ctypes.WinError(ctypes.get_last_error())
        if actual.value != size:
            raise ProbeError("Partial ReadProcessMemory result")
        return buffer.raw

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def self_test() -> dict:
    """Exercise sampling against fake memory; no game contact at all."""
    base, menu, gamedata, player = 0x140000000, 0x20000000, 0x20001000, 0x20002000
    window = bytes(64)
    memory = {
        (base + MENU_RVA, 8): struct.pack("<Q", menu),
        (menu + MENU_WINDOW, 64): window[:MENU_FLOAT - MENU_WINDOW]
        + struct.pack("<f", 1.0) + window[MENU_FLOAT - MENU_WINDOW + 4:],
        (base + GAME_DATA_RVA, 8): struct.pack("<Q", gamedata),
        (gamedata + 0x10, 8): struct.pack("<Q", player),
    }

    def read(address: int, size: int) -> bytes:
        return memory[(address, size)]

    first = sample_menu(read, base)
    assert first["state"] == "sampled" and first["menuGate"] == 1.0
    assert first["playerLoaded"] is True

    def closed(address: int, size: int) -> bytes:
        if (address, size) == (menu + MENU_WINDOW, 64):
            return bytes(64)
        return read(address, size)

    second = sample_menu(closed, base)
    assert second["menuGate"] == 0.0
    assert first["menuWindowHex"] != second["menuWindowHex"]

    def gone(address: int, size: int) -> bytes:
        if (address, size) == (base + MENU_RVA, 8):
            return struct.pack("<Q", 0)
        return read(address, size)

    assert sample_menu(gone, base)["state"] == "noMenu"
    return {"selfTest": "passed", "cases": 3}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("executable", type=Path, nargs="?",
                        help="pinned DarkSoulsRemastered.exe (not needed for --self-test)")
    parser.add_argument("--pid", type=int, help="opt-in read-only Windows sample; no automatic attachment")
    parser.add_argument("--samples", type=int, default=1, help="menu-state samples to take")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between samples")
    parser.add_argument("--self-test", action="store_true", help="fake-memory check; no game contact")
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            print(json.dumps(self_test(), indent=2))
            return 0
        if args.executable is None:
            parser.error("the executable path is required without --self-test")
        if not 1 <= args.samples <= 3600 or not 0 <= args.interval <= 60:
            raise ProbeError("1-3600 samples with a 0-60 s interval")
        report = inspect_executable(args.executable)
        if args.pid is not None:
            with WindowsReader(args.pid, args.executable) as process:
                report["menu"] = []
                for index in range(args.samples):
                    if index:
                        time.sleep(args.interval)
                    report["menu"].append(sample_menu(process.read, process.base))
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ProbeError) as error:
        print(json.dumps({"error": str(error), "gameplayPatchImplemented": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
