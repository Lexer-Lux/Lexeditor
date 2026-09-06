"""Inspect the pinned publisher patcher's payload; never install it ourselves.

Format: Albeoris/Memoria v2025.07.04, Memoria.Patcher/Program.cs,
Run/ExtractFiles. Hashes describe uncompressed files, not an invented layout.
"""
from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import io
from pathlib import Path
import re
import struct

MAGIC = b"MEMORIA\0"
MAX_PATCHER_BYTES = 120 * 1024 * 1024
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024 * 1024
MAX_FILES = 20000
_RESERVED = re.compile(r"(?i)^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)")


@dataclass(frozen=True)
class PayloadFile:
    relative_path: str
    size: int
    sha256: str


def _read(stream, size: int) -> bytes:
    value = stream.read(size)
    if len(value) != size:
        raise ValueError("The Memoria patcher payload is truncated")
    return value


def _part(value: str) -> str:
    if (not value or value in {".", ".."} or value[-1:] in {".", " "}
            or any(ord(char) < 32 or char in '/\\:<>"|?*' for char in value)
            or _RESERVED.match(value)):
        raise ValueError("The Memoria patcher contains an unsafe path component")
    return value


def inspect_payload(patcher: Path) -> tuple[PayloadFile, ...]:
    """Validate footer, bounded gzip data, path dictionary and every file hash."""
    if not 24 <= patcher.stat().st_size <= MAX_PATCHER_BYTES:
        raise ValueError("The Memoria patcher size is outside the allowed limit")
    data = patcher.read_bytes()
    # The unsigned footer is last; Authenticode appends a certificate to it.
    # The publisher scans near -0x2800 for signed releases. Bound our scan too.
    footer = data.rfind(MAGIC, max(0, len(data) - 65536))
    if footer < 0 or footer + 24 > len(data):
        raise ValueError("The Memoria patcher footer was not found")
    remaining, offset = struct.unpack_from("<qq", data, footer + 8)
    if not (0 < remaining <= MAX_PAYLOAD_BYTES and 0 <= offset < footer
            and data[offset:offset + 2] == b"\x1f\x8b"):
        raise ValueError("The Memoria patcher footer is invalid")
    parts: dict[int, str] = {}
    files: list[PayloadFile] = []
    seen: set[str] = set()
    with gzip.GzipFile(fileobj=io.BytesIO(data[offset:footer])) as stream:
        while remaining:
            if len(files) >= MAX_FILES:
                raise ValueError("The Memoria patcher has too many files")
            size, _ticks, count = struct.unpack("<IqB", _read(stream, 13))
            if size > remaining or count == 0:
                raise ValueError("The Memoria patcher file header is invalid")
            components = []
            for _ in range(count):
                token, = struct.unpack("<H", _read(stream, 2))
                key = token & 0x7fff
                if token & 0x8000:
                    if key in parts:
                        raise ValueError("The Memoria path dictionary repeats an ID")
                    length = _read(stream, 1)[0]
                    parts[key] = _part(_read(stream, length).decode("utf-8"))
                elif key not in parts:
                    raise ValueError("The Memoria path dictionary refers to an unknown ID")
                components.append(parts[key])
            name = "/".join(components)
            if name.casefold() in seen:
                raise ValueError("The Memoria patcher repeats a destination")
            seen.add(name.casefold())
            digest = hashlib.sha256()
            left = size
            while left:
                block = _read(stream, min(left, 1024 * 1024))
                digest.update(block)
                left -= len(block)
            files.append(PayloadFile(name, size, digest.hexdigest()))
            remaining -= size
        if stream.read(1):
            raise ValueError("The Memoria payload has unexpected trailing records")
    return tuple(files)


def installation_files(files: tuple[PayloadFile, ...], root: Path) -> tuple[PayloadFile, ...]:
    """Resolve only the platform layout actually supported by the pinned patcher."""
    platforms = [name for name in ("x64", "x86")
                 if (root / name / "FF9_Data" / "Managed").is_dir()]
    if any("{PLATFORM}" in entry.relative_path.split("/") for entry in files):
        # The pinned publisher's x64-only branch writes {PLATFORM} files into
        # x86, not x64. Refuse before mutation instead of reporting an install.
        if platforms != ["x64", "x86"]:
            raise RuntimeError("This pinned Memoria patcher requires the original x64 and x86 Managed folders. Restore the complete Steam installation before installing.")
    result = []
    seen = set()
    for entry in files:
        targets = platforms if "{PLATFORM}" in entry.relative_path.split("/") else (None,)
        for platform in targets:
            name = entry.relative_path.replace("{PLATFORM}", platform) if platform else entry.relative_path
            if "{" in name or "}" in name or name.casefold() in seen:
                raise ValueError("The Memoria patcher has an ambiguous destination")
            seen.add(name.casefold())
            result.append(PayloadFile(name, entry.size, entry.sha256))
    return tuple(result)
