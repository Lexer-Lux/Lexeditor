"""Read a Windows executable's fixed file version without starting it."""

from __future__ import annotations

import ctypes
import os
from functools import lru_cache
from pathlib import Path


class _FixedFileInfo(ctypes.Structure):
    _fields_ = [
        ("signature", ctypes.c_uint32),
        ("structure_version", ctypes.c_uint32),
        ("file_version_ms", ctypes.c_uint32),
        ("file_version_ls", ctypes.c_uint32),
        ("product_version_ms", ctypes.c_uint32),
        ("product_version_ls", ctypes.c_uint32),
        ("file_flags_mask", ctypes.c_uint32),
        ("file_flags", ctypes.c_uint32),
        ("file_os", ctypes.c_uint32),
        ("file_type", ctypes.c_uint32),
        ("file_subtype", ctypes.c_uint32),
        ("file_date_ms", ctypes.c_uint32),
        ("file_date_ls", ctypes.c_uint32),
    ]


def _word(value: int, high: bool) -> int:
    return (value >> 16) & 0xFFFF if high else value & 0xFFFF


@lru_cache(maxsize=32)
def _read_version(path_text: str, modified_ns: int, size_bytes: int) -> str:
    del modified_ns, size_bytes
    if os.name != "nt":
        return ""
    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]
    version.GetFileVersionInfoSizeW.restype = ctypes.c_uint32
    version.GetFileVersionInfoW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
    ]
    version.GetFileVersionInfoW.restype = ctypes.c_int
    version.VerQueryValueW.argtypes = [
        ctypes.c_void_p, ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint),
    ]
    version.VerQueryValueW.restype = ctypes.c_int
    size = version.GetFileVersionInfoSizeW(path_text, None)
    if not size:
        return ""
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(path_text, 0, size, buffer):
        return ""
    value = ctypes.c_void_p()
    length = ctypes.c_uint()
    if not version.VerQueryValueW(buffer, "\\", ctypes.byref(value), ctypes.byref(length)):
        return ""
    if length.value < ctypes.sizeof(_FixedFileInfo):
        return ""
    info = ctypes.cast(value, ctypes.POINTER(_FixedFileInfo)).contents
    if info.signature != 0xFEEF04BD:
        return ""
    parts = (
        _word(info.file_version_ms, True),
        _word(info.file_version_ms, False),
        _word(info.file_version_ls, True),
        _word(info.file_version_ls, False),
    )
    return ".".join(str(part) for part in parts)


def game_version(root: str | None, required_paths: tuple[str, ...]) -> str:
    """Return the fixed version of the first required game executable."""
    if not root:
        return ""
    relative = next((path for path in required_paths if path.casefold().endswith(".exe")), "")
    if not relative:
        return ""
    executable = Path(root) / relative
    try:
        stat = executable.stat()
        return _read_version(str(executable.resolve()), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError):
        return ""
