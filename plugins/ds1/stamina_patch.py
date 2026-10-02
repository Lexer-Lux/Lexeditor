"""Exact-build, fixed-span stamina and encumbrance patches for Remastered.

All defaults preserve the original image exactly. The encumbrance patch keeps
the original stack frame, nonvolatile registers and unwind metadata intact.
Only original Lexeditor instructions are encoded here, not game-code dumps.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct

from core.plugin_files import atomic_write
from . import deployment

EXECUTABLE = "DarkSoulsRemastered.exe"
ORIGINAL_SIZE = 50286344
ORIGINAL_SHA256 = "a45aaa36dd2f6cc151670a639ea5547043cf38ea79ff4178b963c6ed71f98d7b"
BASELINE_OFFSET = 0x1A2A240
BASELINE_RVA = 0x1A2BE40
VANILLA_RATE = 45.0
MIN_RATE, MAX_RATE = 0.0, 200.0
BACKUP = EXECUTABLE + ".lexeditor-stamina-original"
OWNER = ".lexeditor-ds1-native.json"
LIGHT_OFFSET, MEDIUM_OFFSET = 0x1A29980, 0x1A29844
FACTOR_OFFSET, FACTOR_RVA = 0x3563EA, 0x356FEA
FRACTION_OFFSET, FRACTION_RVA = 0x2E0E7B, 0x2E1A7B
OVERLOAD_DISP_OFFSET = 0x2E0E1C
RECOVERY_KEYS = ("ultralightRecovery", "lightRecovery", "mediumRecovery",
                 "heavyRecovery", "overloadedRecovery")
DEFAULT_RULES = {
    "baseRecovery": 45.0, "lightLimit": 25.0, "mediumLimit": 50.0, "heavyLimit": 100.0,
    **dict(zip(RECOVERY_KEYS, (100.0, 100.0, 100.0, 80.0, 70.0))),
}
# Generated from encumbrance.S using encumbrance.ld. Tests rebuild when GNU
# binutils are available. Table words are populated from validated settings.
FACTOR_CODE = bytes.fromhex("488d0d09000000f3420f1034b1eb1a900000803f0000803f0000803fcdcc4c3f3333333f0000803f90")
FRACTION_CODE = bytes.fromhex("f30f1035e94133010f57edf30f5ed90f28d50f2f1d7a5507007755f30f1025a6997401f30f100dda9a74010f28d30f2fdc77190f2fd97706f30f5ed1eb22f30f5cd1f30f5ce1f30f5ed4eb14f30f5cd4f30f100d3b550700f30f5cccf30f5ed10f2fea76030f28d50f2fd676030f28d6f30f11542420488d44242090909090909090909090909090909090909090909090909090909090")


def rate_value(value) -> float:
    if type(value) not in (int, float) or not MIN_RATE <= value <= MAX_RATE:
        raise ValueError("Base recovery must be a finite number from 0 to 200")
    if not math.isfinite(value):
        raise ValueError("Base recovery must be a finite number from 0 to 200")
    return struct.unpack("<f", struct.pack("<f", value))[0]


def validate_rules(value: dict) -> dict:
    if type(value) is not dict or set(value) != set(DEFAULT_RULES):
        raise ValueError("Unsupported native rules")
    result = {"baseRecovery": rate_value(value["baseRecovery"])}
    for key in DEFAULT_RULES.keys() - {"baseRecovery"}:
        number = value[key]
        minimum = 0.01 if key.endswith("Limit") else 0.0
        if type(number) not in (int, float) or not minimum <= number <= 1000:
            raise ValueError("Load limits and recovery percentages must be finite and between 0 and 1000")
        if abs(round(number, 2) - number) > 1e-8:
            raise ValueError("Use at most two decimal places for load limits and percentages")
        result[key] = float(round(number, 2))
    if not result["lightLimit"] < result["mediumLimit"] < result["heavyLimit"]:
        raise ValueError("Load limits must increase: Light < Medium < Heavy")
    return result


def _pristine(source: bytes) -> None:
    if len(source) != ORIGINAL_SIZE or hashlib.sha256(source).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("Unsupported or externally modified Remastered executable")


def transform(original: bytes, rules: dict) -> bytes:
    """Return one deterministic patch projection of a verified pristine image."""
    rules = validate_rules(rules)
    _pristine(original)
    result = bytearray(original)
    struct.pack_into("<f", result, BASELINE_OFFSET, rules["baseRecovery"])
    if any(rules[key] != DEFAULT_RULES[key] for key in DEFAULT_RULES if key != "baseRecovery"):
        table = bytearray(FACTOR_CODE)
        for index, key in enumerate(RECOVERY_KEYS):
            struct.pack_into("<f", table, 16 + 4 * index, rules[key] / 100)
        struct.pack_into("<f", table, 36, rules["heavyLimit"] / 100)
        result[FACTOR_OFFSET:FACTOR_OFFSET + len(table)] = table
        result[FRACTION_OFFSET:FRACTION_OFFSET + len(FRACTION_CODE)] = FRACTION_CODE
        struct.pack_into("<f", result, LIGHT_OFFSET, rules["lightLimit"] / 100)
        struct.pack_into("<f", result, MEDIUM_OFFSET, rules["mediumLimit"] / 100)
        # Redirect only the classifier's comparison, never the globally shared 1.0.
        struct.pack_into("<i", result, OVERLOAD_DISP_OFFSET, FACTOR_RVA + 36 - 0x2E1A20)
    return original if result == original else bytes(result)


def identify(source: bytes, original: bytes | None = None) -> dict:
    """Recognize only vanilla or our exact reproducible projection, not a signature match."""
    if len(source) != ORIGINAL_SIZE:
        raise ValueError("Unsupported Remastered executable size")
    if hashlib.sha256(source).hexdigest() == ORIGINAL_SHA256:
        return dict(DEFAULT_RULES)
    if original is None:
        raise ValueError("A verified original is required to identify a modified executable")
    _pristine(original)
    rules = dict(DEFAULT_RULES)
    rules["baseRecovery"] = struct.unpack_from("<f", source, BASELINE_OFFSET)[0]
    if source[FACTOR_OFFSET:FACTOR_OFFSET+16] == FACTOR_CODE[:16]:
        for index, key in enumerate(RECOVERY_KEYS):
            rules[key] = round(struct.unpack_from("<f", source, FACTOR_OFFSET+16+index*4)[0] * 100, 2)
        for key, offset in (("lightLimit", LIGHT_OFFSET), ("mediumLimit", MEDIUM_OFFSET),
                            ("heavyLimit", FACTOR_OFFSET+36)):
            rules[key] = round(struct.unpack_from("<f", source, offset)[0] * 100, 2)
    rules = validate_rules(rules)
    if transform(original, rules) != source:
        raise ValueError("Executable contains changes not owned by the stamina/encumbrance editor")
    return rules


def checked(path: Path) -> Path:
    path = deployment._assert_no_reparse_ancestry(path)
    try:
        entry = path.lstat()
    except FileNotFoundError:
        return path
    if stat.S_ISREG(entry.st_mode) and entry.st_nlink != 1:
        raise ValueError("A protected stamina file has multiple hard links")
    return path


def read_file(path: Path, limit: int, *, optional: bool = False) -> bytes | None:
    path = checked(path)
    try:
        entry = path.lstat()
    except FileNotFoundError:
        if optional:
            return None
        raise ValueError(f"Required file is missing: {path.name}") from None
    if not stat.S_ISREG(entry.st_mode) or entry.st_size > limit:
        raise ValueError(f"Unsupported file type or size: {path.name}")
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise ValueError(f"File exceeds its size limit: {path.name}")
    return content


def ensure_game_closed() -> None:
    """Reuse the shared Win32 bindings but fail closed on enumeration errors."""
    if os.name != "nt":
        raise ValueError("Apply and Restore for stamina tweaks require Windows")
    from core import process_probe as probe
    from ctypes import wintypes
    kernel = probe._KERNEL32
    handle = kernel.CreateToolhelp32Snapshot(probe.TH32CS_SNAPPROCESS, 0)
    if handle in (None, 0, wintypes.HANDLE(-1).value):
        raise RuntimeError("Could not verify that Dark Souls Remastered is closed")
    try:
        entry = probe.PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ctypes.set_last_error(0)
        more = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            if entry.szExeFile.casefold() == EXECUTABLE.casefold():
                process = kernel.OpenProcess(probe.PROCESS_QUERY_LIMITED_INFORMATION,
                                             False, entry.th32ProcessID)
                if not process:
                    raise RuntimeError("Cannot inspect the game process; close it before applying")
                try:
                    code = wintypes.DWORD()
                    if not kernel.GetExitCodeProcess(process, ctypes.byref(code)):
                        raise RuntimeError("Could not verify the game process state")
                    if code.value == probe.STILL_ACTIVE:
                        raise RuntimeError("Close Dark Souls Remastered before applying or restoring")
                finally:
                    kernel.CloseHandle(process)
            ctypes.set_last_error(0)
            more = kernel.Process32NextW(handle, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise RuntimeError("Game process enumeration did not finish successfully")
    finally:
        kernel.CloseHandle(handle)


def _owner(game_root: Path) -> dict | None:
    content = read_file(game_root / OWNER, 4096, optional=True)
    if content is None:
        return None
    owner = json.loads(content)
    if (type(owner) is not dict or set(owner) != {"schema", "originalHash", "activeHash", "pendingHash"}
            or type(owner["schema"]) is not int or owner["schema"] != 1
            or owner["originalHash"] != ORIGINAL_SHA256):
        raise ValueError("Invalid native ownership record")
    for key in ("activeHash", "pendingHash"):
        value = owner[key]
        if key == "pendingHash" and value is None:
            continue
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Invalid native ownership hash")
    return owner


def _write_owner(game_root: Path, owner: dict) -> None:
    atomic_write(checked(game_root / OWNER), (json.dumps(owner, indent=2) + "\n").encode())


def inspect(game_root: Path) -> tuple[bytes, dict, bool]:
    game_root = checked(game_root)
    source = read_file(game_root / EXECUTABLE, ORIGINAL_SIZE)
    backup = read_file(game_root / BACKUP, ORIGINAL_SIZE, optional=True)
    owner = _owner(game_root)
    source_hash = hashlib.sha256(source).hexdigest()
    if owner is not None and backup is None:
        raise ValueError("The preserved original native executable is missing")
    if backup is not None:
        _pristine(backup)
    if owner is None and source_hash != ORIGINAL_SHA256:
        raise ValueError("The native ownership record or original backup is missing")
    if owner and source_hash not in (ORIGINAL_SHA256, owner["activeHash"], owner["pendingHash"]):
        raise ValueError("The native executable changed outside Lexeditor")
    rules = identify(source, backup)
    return source, rules, backup is not None


def install(game_root: Path, rules: dict, *, expected: bytes | None = None) -> None:
    """Explicit closed-game replacement with a bounded backup and durable intent."""
    rules = validate_rules(rules)
    ensure_game_closed()
    game_root = checked(game_root)
    live, backup = checked(game_root / EXECUTABLE), checked(game_root / BACKUP)
    before, _current, backup_ok = inspect(game_root)
    if expected is not None and before != expected:
        raise ValueError("The executable changed while Apply was being prepared")
    original = read_file(backup, ORIGINAL_SIZE) if backup_ok else before
    after = transform(original, rules)
    if after == before:
        return
    if not backup_ok:
        with backup.open("xb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        if read_file(backup, ORIGINAL_SIZE) != original:
            raise RuntimeError("The original executable backup did not verify")
    ensure_game_closed()
    checked(live)
    if inspect(game_root)[0] != before:
        raise ValueError("The executable changed before replacement")
    owner = {"schema": 1, "originalHash": ORIGINAL_SHA256,
             "activeHash": hashlib.sha256(before).hexdigest(),
             "pendingHash": hashlib.sha256(after).hexdigest()}
    _write_owner(game_root, owner)
    atomic_write(live, after)
    if read_file(live, ORIGINAL_SIZE) != after:
        raise RuntimeError("Executable verification failed; the original backup was retained")
    owner.update(activeHash=owner["pendingHash"], pendingHash=None)
    _write_owner(game_root, owner)
