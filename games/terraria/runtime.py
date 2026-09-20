"""Fail-closed tModLoader runtime identification without launching the game."""
from __future__ import annotations

from ctypes import POINTER, byref, c_uint, c_void_p, c_wchar_p, cast, create_string_buffer
from ctypes import wintypes
import ctypes
import os
from pathlib import Path
import re
from typing import Callable

SUPPORTED_TML_VERSION = (2026, 7, 3, 0)
SUPPORTED_TML_DISPLAY = "2026.07.3.0"
_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)\.(\d+)$")


def parse_build_identifier(value: str) -> dict:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("tModLoader.dll has no readable product version")
    payload = raw.split("+", 1)[1] if "+" in raw else raw
    parts = [part.strip() for part in payload.split("|")]
    token = parts[0].removeprefix("v")
    match = _VERSION.fullmatch(token)
    if not match:
        raise ValueError(f"Unrecognized tModLoader product version: {raw}")
    version = tuple(int(part) for part in match.groups())
    purpose = parts[3] if len(parts) > 3 else ""
    return {
        "raw": raw,
        "version": version,
        "versionText": ".".join(str(part) for part in version),
        "displayVersion": f"{version[0]}.{version[1]:02d}.{version[2]}.{version[3]}",
        "purpose": purpose,
    }


def windows_product_version(path: Path) -> str:
    if os.name != "nt":
        raise ValueError("Windows file-version metadata is only available on Windows")
    target = Path(path).resolve()
    if not target.is_file():
        raise ValueError(f"tModLoader runtime file is missing: {target}")
    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, POINTER(wintypes.DWORD)]
    version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, c_void_p]
    version.GetFileVersionInfoW.restype = wintypes.BOOL
    version.VerQueryValueW.argtypes = [c_void_p, wintypes.LPCWSTR, POINTER(c_void_p), POINTER(c_uint)]
    version.VerQueryValueW.restype = wintypes.BOOL

    handle = wintypes.DWORD()
    size = version.GetFileVersionInfoSizeW(str(target), byref(handle))
    if not size:
        raise ValueError("Could not read tModLoader.dll version metadata")
    buffer = create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(target), 0, size, buffer):
        raise ValueError("Could not read tModLoader.dll version metadata")

    pointer = c_void_p()
    length = c_uint()
    translations: list[tuple[int, int]] = []
    if version.VerQueryValueW(buffer, r"\VarFileInfo\Translation", byref(pointer), byref(length)) and length.value >= 4:
        words = cast(pointer, POINTER(wintypes.WORD))
        for index in range(0, length.value // 2, 2):
            translations.append((int(words[index]), int(words[index + 1])))
    translations.extend([(0x0409, 0x04B0), (0x0000, 0x04B0)])
    seen: set[tuple[int, int]] = set()
    for language, codepage in translations:
        if (language, codepage) in seen:
            continue
        seen.add((language, codepage))
        query = fr"\StringFileInfo\{language:04x}{codepage:04x}\ProductVersion"
        value_pointer = c_void_p()
        value_length = c_uint()
        if version.VerQueryValueW(buffer, query, byref(value_pointer), byref(value_length)) and value_pointer.value:
            text = cast(value_pointer, c_wchar_p).value
            if text and text.strip():
                return text.strip()
    raise ValueError("tModLoader.dll does not expose ProductVersion metadata")


def inspect_runtime(
    install_root: Path,
    *,
    platform_name: str | None = None,
    version_reader: Callable[[Path], str] | None = None,
) -> dict:
    root = Path(install_root).resolve()
    result = {
        "installRoot": str(root),
        "runtimeVersion": "",
        "runtimeVersionRaw": "",
        "supportedRuntimeVersion": SUPPORTED_TML_DISPLAY,
        "runtimeSupported": False,
        "runtimeReason": "",
    }
    dll = root / "tModLoader.dll"
    if not dll.is_file():
        result["runtimeReason"] = f"tModLoader.dll is missing from {root}"
        return result
    platform_name = os.name if platform_name is None else platform_name
    if platform_name != "nt" and version_reader is None:
        result["runtimeReason"] = "tModLoader version verification requires Windows file-version metadata."
        return result
    reader = version_reader or windows_product_version
    try:
        parsed = parse_build_identifier(reader(dll))
    except (OSError, ValueError) as error:
        result["runtimeReason"] = str(error)
        return result
    result["runtimeVersionRaw"] = parsed["raw"]
    result["runtimeVersion"] = parsed["displayVersion"]
    if parsed["purpose"] and parsed["purpose"].casefold() != "stable":
        result["runtimeReason"] = f"Detected tModLoader {parsed['displayVersion']} {parsed['purpose']}; stable {SUPPORTED_TML_DISPLAY} is required."
        return result
    if parsed["version"] != SUPPORTED_TML_VERSION:
        result["runtimeReason"] = f"Detected tModLoader {parsed['displayVersion']}; supported stable version is {SUPPORTED_TML_DISPLAY}."
        return result
    result["runtimeSupported"] = True
    return result
