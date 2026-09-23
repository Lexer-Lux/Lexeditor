"""Read-only Chrono Trigger Steam resources.bin (ARC1) access.

The implementation follows the publicly documented PC layout in CTViewer and
ct_nx. It never rewrites the installed archive; writable output is handled by
project overlays and CTP packages.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib


MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_RESOURCE_BYTES = 64 * 1024 * 1024


class ArchiveError(ValueError):
    pass


@dataclass(frozen=True)
class ResourceEntry:
    path: str
    offset: int
    stored_size: int


def _decode(offset: int, payload: bytes) -> bytes:
    state = (0x19000000 + offset) & 0xFFFFFFFF
    out = bytearray(len(payload))
    for index, value in enumerate(payload):
        state = (state * 0x41C64E6D + 0x3039) & 0xFFFFFFFF
        out[index] = value ^ ((state >> 24) & 0xFF)
    return bytes(out)


def _inflate_block(decoded: bytes, *, limit: int, label: str) -> bytes:
    if len(decoded) < 4:
        raise ArchiveError(f"{label} block is truncated")
    declared = struct.unpack_from(">I", decoded, 0)[0]
    if declared > limit:
        raise ArchiveError(f"{label} declares {declared} bytes, above the {limit}-byte safety limit")
    try:
        result = zlib.decompress(decoded[4:], zlib.MAX_WBITS | 16)
    except zlib.error as error:
        raise ArchiveError(f"{label} gzip stream is invalid: {error}") from error
    if len(result) != declared:
        raise ArchiveError(f"{label} decoded to {len(result)} bytes; expected {declared}")
    return result


class ResourcesBin:
    """Bounded read-only accessor for the Steam ARC1 archive."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        try:
            self.size = self.path.stat().st_size
        except OSError as error:
            raise ArchiveError(f"Could not read resources.bin: {error}") from error
        if self.size < 16:
            raise ArchiveError("resources.bin is shorter than its 16-byte ARC1 header")
        with self.path.open("rb") as handle:
            header = _decode(0, handle.read(16))
        if header[:4] != b"ARC1":
            raise ArchiveError("resources.bin does not have the ARC1 signature")
        declared_size, index_offset, index_size = struct.unpack_from("<III", header, 4)
        if declared_size != self.size:
            raise ArchiveError(f"ARC1 file length is {self.size}; header declares {declared_size}")
        if index_offset < 16 or index_size < 4 or index_offset + index_size > self.size:
            raise ArchiveError("ARC1 index points outside resources.bin")
        with self.path.open("rb") as handle:
            handle.seek(index_offset)
            encoded_index = handle.read(index_size)
        index = _inflate_block(_decode(index_offset, encoded_index), limit=MAX_INDEX_BYTES, label="ARC1 index")
        if len(index) < 4:
            raise ArchiveError("ARC1 index is truncated")
        count = struct.unpack_from("<I", index, 0)[0]
        table_end = 4 + count * 12
        if table_end > len(index):
            raise ArchiveError("ARC1 entry table is truncated")
        entries: list[ResourceEntry] = []
        seen: set[str] = set()
        for number in range(count):
            name_offset, entry_offset, stored_size = struct.unpack_from("<III", index, 4 + number * 12)
            if name_offset < table_end or name_offset >= len(index):
                raise ArchiveError(f"ARC1 entry {number} has an invalid path offset")
            end = index.find(b"\0", name_offset)
            if end < 0:
                raise ArchiveError(f"ARC1 entry {number} path is unterminated")
            try:
                name = index[name_offset:end].decode("utf-8")
            except UnicodeDecodeError as error:
                raise ArchiveError(f"ARC1 entry {number} path is not UTF-8") from error
            if not name or name.startswith(("/", "\\")) or ".." in Path(name.replace("\\", "/")).parts:
                raise ArchiveError(f"ARC1 entry {number} has an unsafe path")
            if name in seen:
                raise ArchiveError(f"ARC1 contains duplicate path {name}")
            if stored_size < 4 or entry_offset < 16 or entry_offset + stored_size > index_offset:
                raise ArchiveError(f"ARC1 entry {name} points outside the data region")
            seen.add(name)
            entries.append(ResourceEntry(name, entry_offset, stored_size))
        self.entries = tuple(entries)
        self._entries = {entry.path: entry for entry in entries}

    def has(self, path: str) -> bool:
        return path in self._entries

    def paths(self, prefix: str = "") -> list[str]:
        return [entry.path for entry in self.entries if entry.path.startswith(prefix)]

    def extract(self, path: str, *, limit: int = MAX_RESOURCE_BYTES) -> bytes:
        entry = self._entries.get(path)
        if entry is None:
            raise KeyError(path)
        with self.path.open("rb") as handle:
            handle.seek(entry.offset)
            encoded = handle.read(entry.stored_size)
        if len(encoded) != entry.stored_size:
            raise ArchiveError(f"ARC1 entry {path} is truncated")
        return _inflate_block(_decode(entry.offset, encoded), limit=limit, label=path)
