"""Read-only research probe for DS1 issue 902; NOT an ammunition-controls tweak.

Offline: python tools/ds1_ammunition_probe.py PATH/TO/DarkSoulsRemastered.exe
Windows, explicit process: add --pid PID for a best-effort four-slot sample.
No writes, injection, debug privilege, hooks, dumps, or game-code calls.
The Windows transport still requires installed-game validation. Use offline
mode by default. Static provenance and unresolved work: worklog/902.md.
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
from typing import Callable

BUILD_SHA256 = "a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b"
MAX_FILE = 64 * 1024 * 1024
GAME_DATA_RVA = 0x1C8A530
SLOTS = (("primaryArrow", 4), ("secondaryArrow", 6),
         ("primaryBolt", 5), ("secondaryBolt", 7))
# Minimal structural guards, not a game-code dump. These regions are readable
# on disk. They do not authorize a gameplay patch or arbitrary other builds.
GUARDS = (
    ("equipmentId", 0x31B750, "83fa1377084863c28b448124c383c8ffc3"),
    ("quantityIndex", 0x7478CD, "4863c2486354812483faff"),
    ("arrowQuantity", 0x747860, "83c2fa83fafe750a"),
    ("boltQuantity", 0x747920, "83c2fc83fafe750a"),
    ("ammoHud", 0x678CD0, "48895c2408488974241848897c2420"),
    ("ammoCount", 0x678A00, "4055565741564157488d6c24c9"),
    ("inputInterior", 0x396EAE, "c64424300080bf1d02000000"),
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
        self.image_base = struct.unpack_from("<Q", opt, 24)[0]
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
            for previous_rva, previous_span, previous_raw, previous_size in self.sections:
                if span and previous_span and max(rva, previous_rva) < min(
                        rva + span, previous_rva + previous_span):
                    raise ProbeError("Overlapping virtual sections")
                if raw_size and previous_size and max(raw, previous_raw) < min(
                        raw + raw_size, previous_raw + previous_size):
                    raise ProbeError("Overlapping raw sections")
            self.sections.append((rva, span, raw, raw_size))

    def read_rva(self, rva: int, size: int) -> bytes:
        if rva < 0 or size <= 0:
            raise ProbeError("Invalid RVA read")
        # Names are not unique: the supplied executable has TWO .text sections.
        for start, _span, raw, raw_size in self.sections:
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


def number(read: Read, address: int, fmt: str) -> int:
    return struct.unpack(fmt, read_exact(read, address, struct.calcsize(fmt)))[0]


def _sample(read: Read, module_base: int) -> tuple:
    singleton = number(read, module_base + GAME_DATA_RVA, "<Q")
    if not singleton:
        return (singleton, None, ())
    player_data = number(read, singleton + 0x10, "<Q")
    if not player_data:
        return (singleton, player_data, ())
    equip = player_data + 0x280
    inventory = read_exact(read, equip, 0x160)
    count = struct.unpack_from("<i", inventory, 0x130)[0]
    split = struct.unpack_from("<i", inventory, 0x140)[0]
    if not 0 <= count <= 1_000_000 or not 0 <= split <= 1_000_000:
        raise ProbeError("Invalid inventory bounds")
    result = []
    for name, slot in SLOTS:
        item_id = struct.unpack_from("<i", inventory, 0xA4 + slot * 4)[0]
        index = struct.unpack_from("<i", inventory, 0x24 + slot * 4)[0]
        quantity = None
        entry_address = None
        if item_id == -1:
            state = "unequipped"
        elif item_id < -1:
            raise ProbeError("Invalid equipped item ID")
        elif index < 0 or index >= count:
            state = "missingInventory"
        else:
            table = struct.unpack_from("<Q", inventory, 0x150 if index < split else 0x158)[0]
            # The second table uses the SAME absolute index, not index - split.
            entry_address = table + index * 0x1C if table else None
            if not table:
                raise ProbeError("Null inventory table")
            quantity = number(read, entry_address + 8, "<i")
            if quantity < 0:
                raise ProbeError("Negative inventory quantity")
            state = "empty" if quantity == 0 else "equipped"
        result.append((name, slot, item_id, index, entry_address, quantity, state))
    # Include identity, indices, pointers, and the captured header in stability
    # comparisons; equal displayed counts alone would not detect equipment swaps.
    return (singleton, player_data, inventory, tuple(result))


def sample_ammunition(read: Read, module_base: int) -> dict:
    """Read all four slots, retrying changed samples at most three times.

    Two equal samples are NOT an atomic snapshot, nor proof of shot-time
    consumption. No selected-ammunition index is consulted or written.
    """
    for _ in range(3):
        first = _sample(read, module_base)
        second = _sample(read, module_base)
        if first != second:
            continue
        if not first[1]:
            return {"state": "noPlayerData", "slots": []}
        return {"state": "sampled", "atomic": False,
                "slots": [{"name": name, "rawSlot": slot, "itemId": item,
                           "quantity": quantity, "state": state}
                          for name, slot, item, _index, _address, quantity, state in first[3]]}
    raise ProbeError("Equipment changed during sampling; no sample returned")


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
            # Only use readable structural guards, NOT transformed input helpers.
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--pid", type=int, help="opt-in read-only Windows sample; no automatic attachment")
    args = parser.parse_args(argv)
    try:
        report = inspect_executable(args.executable)
        if args.pid is not None:
            with WindowsReader(args.pid, args.executable) as process:
                report["ammunition"] = sample_ammunition(process.read, process.base)
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ProbeError) as error:
        print(json.dumps({"error": str(error), "gameplayPatchImplemented": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
