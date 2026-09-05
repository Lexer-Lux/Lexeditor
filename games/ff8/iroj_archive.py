"""Read Junction VIII IROJ archives without adopting its profile model.

The container format was documented from Junction VIII's MS-PL IrosArc
implementation (original developer: Iros <irosff@outlook.com>).  Lexeditor
uses the format only as an input container.  Load order and conflict handling
remain Lexeditor-owned.
"""

from __future__ import annotations

from dataclasses import dataclass
import lzma
from pathlib import Path, PurePosixPath
import struct

from .vendor.ff8ue.lzs import Lzs


SIGNATURE = 0x534F5249
MIN_VERSION = 0x10000
MAX_VERSION = 0x10002
FLAG_LZS = 0x1
FLAG_LZMA = 0x2
COMPRESSION_MASK = 0xF
MAX_ENTRIES = 1_000_000
MAX_EXPANDED_FILE = 512 * 1024 * 1024
WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul", *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


class IrojError(ValueError):
    """An IROJ archive is malformed or uses an unsupported feature."""


@dataclass(frozen=True)
class Entry:
    name: str
    flags: int
    offset: int
    stored_size: int


def _read_exact(stream, size: int) -> bytes:
    value = stream.read(size)
    if len(value) != size:
        raise IrojError("IROJ archive ends before its declared data")
    return value


def _u32(stream) -> int:
    return struct.unpack("<I", _read_exact(stream, 4))[0]


def _i32(stream) -> int:
    return struct.unpack("<i", _read_exact(stream, 4))[0]


def _i64(stream) -> int:
    return struct.unpack("<q", _read_exact(stream, 8))[0]


def safe_name(value: str) -> str:
    """Return one portable archive path or reject traversal and ambiguity."""
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (not normalized or normalized.startswith("/") or path.is_absolute()
            or any(part in ("", ".", "..") for part in path.parts)
            or any(any(ord(char) < 32 or char in '<>:"|?*' for char in part)
                   or part.endswith((" ", "."))
                   or part.split(".", 1)[0].casefold() in WINDOWS_RESERVED
                   for part in path.parts)):
        raise IrojError(f"Unsafe IROJ member path: {value!r}")
    return path.as_posix()


class Archive:
    """Validated, random-access view of one IROJ archive."""

    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.version = 0
        self.flags = 0
        self.entries: tuple[Entry, ...] = ()
        self._lookup: dict[str, Entry] = {}
        self._open()

    def _open(self) -> None:
        size = self.path.stat().st_size
        with self.path.open("rb") as stream:
            signature, version, flags, directory = struct.unpack(
                "<IIII", _read_exact(stream, 16))
            if signature != SIGNATURE:
                raise IrojError("IROJ signature does not match IROS")
            if not MIN_VERSION <= version <= MAX_VERSION:
                raise IrojError(f"Unsupported IROJ version: 0x{version:X}")
            if directory >= size:
                raise IrojError("IROJ directory offset is outside the archive")
            stream.seek(directory)
            count = _i32(stream)
            while count < 0:
                if count != -1:
                    raise IrojError("Unsupported IROJ directory forwarding record")
                forwarded = _i64(stream)
                if forwarded < 16 or forwarded >= size:
                    raise IrojError("IROJ directory forwarder is outside the archive")
                stream.seek(forwarded)
                count = _i32(stream)
            if count > MAX_ENTRIES:
                raise IrojError(f"IROJ contains too many entries: {count}")
            entries: list[Entry] = []
            seen: set[str] = set()
            for _ in range(count):
                record_start = stream.tell()
                record_size, filename_size = struct.unpack(
                    "<HH", _read_exact(stream, 4))
                minimum = 4 + filename_size + 4 + (4 if version < 0x10001 else 8) + 4
                if record_size < minimum or filename_size % 2:
                    raise IrojError("IROJ directory entry has an invalid size")
                try:
                    name = safe_name(_read_exact(stream, filename_size).decode("utf-16-le"))
                except UnicodeError as error:
                    raise IrojError("IROJ member name is not valid UTF-16LE") from error
                member_flags = _u32(stream)
                offset = _u32(stream) if version < 0x10001 else _i64(stream)
                stored_size = _i32(stream)
                if offset < 0 or stored_size < 0 or offset + stored_size > size:
                    raise IrojError(f"IROJ member is outside the archive: {name}")
                if member_flags & ~COMPRESSION_MASK:
                    raise IrojError(f"IROJ member uses unsupported flags: {name}")
                compression = member_flags & COMPRESSION_MASK
                if compression not in (0, FLAG_LZS, FLAG_LZMA):
                    raise IrojError(f"IROJ member uses unsupported compression: {name}")
                folded = name.casefold()
                if folded in seen:
                    raise IrojError(f"IROJ contains a duplicate member name: {name}")
                seen.add(folded)
                entries.append(Entry(name, member_flags, offset, stored_size))
                stream.seek(record_start + record_size)
            self.version = version
            self.flags = flags
            self.entries = tuple(entries)
            self._lookup = {entry.name.casefold(): entry for entry in entries}

    def names(self) -> tuple[str, ...]:
        return tuple(entry.name for entry in self.entries)

    def has(self, name: str) -> bool:
        return safe_name(name).casefold() in self._lookup

    def read(self, name: str) -> bytes:
        key = safe_name(name).casefold()
        try:
            entry = self._lookup[key]
        except KeyError as error:
            raise KeyError(name) from error
        with self.path.open("rb") as stream:
            stream.seek(entry.offset)
            stored = _read_exact(stream, entry.stored_size)
        compression = entry.flags & COMPRESSION_MASK
        if compression == 0:
            return stored
        if compression == FLAG_LZS:
            expanded = bytearray()
            for value in Lzs().decode(stored):
                expanded.append(value)
                if len(expanded) > MAX_EXPANDED_FILE:
                    raise IrojError(f"IROJ member expands beyond the safety limit: {entry.name}")
            return bytes(expanded)
        if len(stored) < 13:
            raise IrojError(f"Compressed IROJ member has no LZMA header: {entry.name}")
        expanded, properties_size = struct.unpack_from("<II", stored)
        if expanded > MAX_EXPANDED_FILE or properties_size < 5 or 8 + properties_size > len(stored):
            raise IrojError(f"Compressed IROJ member has invalid sizes: {entry.name}")
        properties = stored[8:8 + properties_size]
        code = properties[0]
        if code >= 9 * 5 * 5:
            raise IrojError(f"Compressed IROJ member has invalid LZMA properties: {entry.name}")
        lc = code % 9
        remainder = code // 9
        lp, pb = remainder % 5, remainder // 5
        dictionary = struct.unpack_from("<I", properties, 1)[0]
        try:
            decoder = lzma.LZMADecompressor(
                format=lzma.FORMAT_RAW,
                filters=[{"id": lzma.FILTER_LZMA1, "dict_size": max(dictionary, 4096),
                          "lc": lc, "lp": lp, "pb": pb}],
            )
            value = decoder.decompress(stored[8 + properties_size:], max_length=expanded + 1)
        except lzma.LZMAError as error:
            raise IrojError(f"Could not decompress IROJ member: {entry.name}") from error
        if len(value) != expanded or not decoder.eof:
            raise IrojError(f"IROJ member expanded to the wrong size: {entry.name}")
        return value
