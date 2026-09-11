"""Read-only parser for Chrono Trigger (Steam) ``resources.bin`` archives.

The Steam archive uses an offset-keyed XOR stream around an ARC1 header, a
compressed index, and individually gzip-compressed resource payloads.  This
module intentionally implements only reads; Lexeditor must never mutate the
installed archive in place.
"""

from __future__ import annotations

from dataclasses import dataclass
import gzip
from pathlib import Path
import struct
import zlib


_MASK32 = 0xFFFFFFFF
_HEADER_SIZE = 16
_MAGIC = b"ARC1"


class ResourceArchiveError(ValueError):
    """The supplied file is not a supported Chrono Trigger Steam archive."""


@dataclass(frozen=True)
class ResourceEntry:
    """One resource record stored in ``resources.bin``."""

    path: str
    offset: int
    stored_size: int


class ResourceArchive:
    """Parse and extract entries from one Chrono Trigger Steam archive."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.file_size = self.path.stat().st_size
        self.declared_size = 0
        self.index_offset = 0
        self.index_stored_size = 0
        self.entries: tuple[ResourceEntry, ...] = ()
        self._by_path: dict[str, ResourceEntry] = {}
        self._load_index()

    @staticmethod
    def decode(data: bytes, absolute_offset: int) -> bytes:
        """Apply the archive's symmetric offset-keyed byte stream."""
        state = (0x19000000 + int(absolute_offset)) & _MASK32
        output = bytearray(data)
        for index, value in enumerate(output):
            state = (state * 0x41C64E6D + 0x3039) & _MASK32
            output[index] = value ^ ((state >> 24) & 0xFF)
        return bytes(output)

    def _read_decoded(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > self.file_size:
            raise ResourceArchiveError(
                f"archive range is outside the file: offset={offset}, length={length}"
            )
        with self.path.open("rb") as stream:
            stream.seek(offset)
            raw = stream.read(length)
        if len(raw) != length:
            raise ResourceArchiveError("archive ended before the requested range")
        return self.decode(raw, offset)

    @staticmethod
    def _inflate_block(block: bytes, label: str) -> bytes:
        if len(block) < 4:
            raise ResourceArchiveError(f"{label} block is shorter than its size prefix")
        expected_size = int.from_bytes(block[:4], "big")
        if expected_size == 0:
            return b""
        try:
            payload = gzip.decompress(block[4:])
        except (OSError, EOFError, zlib.error) as error:
            raise ResourceArchiveError(f"{label} gzip payload is invalid") from error
        if len(payload) != expected_size:
            raise ResourceArchiveError(
                f"{label} size mismatch: expected {expected_size}, got {len(payload)}"
            )
        return payload

    def _load_index(self) -> None:
        if self.file_size < _HEADER_SIZE:
            raise ResourceArchiveError("archive is smaller than its 16-byte header")
        header = self._read_decoded(0, _HEADER_SIZE)
        if header[:4] != _MAGIC:
            raise ResourceArchiveError(
                f"unsupported resources.bin magic {header[:4]!r}; expected {_MAGIC!r}"
            )
        self.declared_size, self.index_offset, self.index_stored_size = struct.unpack_from(
            "<III", header, 4
        )
        if self.index_offset < _HEADER_SIZE:
            raise ResourceArchiveError("archive index overlaps the ARC1 header")
        index_block = self._read_decoded(self.index_offset, self.index_stored_size)
        index = self._inflate_block(index_block, "index")
        if len(index) < 4:
            raise ResourceArchiveError("archive index has no entry count")

        entry_count = struct.unpack_from("<I", index, 0)[0]
        table_end = 4 + entry_count * 12
        if table_end > len(index):
            raise ResourceArchiveError("archive index entry table is truncated")

        entries: list[ResourceEntry] = []
        by_path: dict[str, ResourceEntry] = {}
        for number in range(entry_count):
            row_offset = 4 + number * 12
            path_offset, data_offset, stored_size = struct.unpack_from("<III", index, row_offset)
            if path_offset < table_end or path_offset >= len(index):
                raise ResourceArchiveError(f"entry {number} has an invalid path offset")
            terminator = index.find(b"\x00", path_offset)
            if terminator < 0:
                raise ResourceArchiveError(f"entry {number} path is not NUL terminated")
            try:
                resource_path = index[path_offset:terminator].decode("utf-8")
            except UnicodeDecodeError as error:
                raise ResourceArchiveError(f"entry {number} path is not UTF-8") from error
            if not resource_path:
                raise ResourceArchiveError(f"entry {number} has an empty path")
            if data_offset < _HEADER_SIZE or data_offset + stored_size > self.file_size:
                raise ResourceArchiveError(f"entry {number} points outside the archive")
            if resource_path in by_path:
                raise ResourceArchiveError(f"duplicate resource path: {resource_path}")
            entry = ResourceEntry(resource_path, data_offset, stored_size)
            entries.append(entry)
            by_path[resource_path] = entry

        self.entries = tuple(entries)
        self._by_path = by_path

    def get(self, path: str) -> ResourceEntry:
        """Return one resource by its exact in-archive path."""
        try:
            return self._by_path[path]
        except KeyError as error:
            raise KeyError(f"resource not found: {path}") from error

    def declared_payload_size(self, entry: ResourceEntry | str) -> int:
        """Read only an entry's decoded 4-byte uncompressed-size prefix.

        This does not read or inflate the gzip payload. It is intended for
        lightweight archive-family clustering/reverse-engineering diagnostics.
        """
        record = self.get(entry) if isinstance(entry, str) else entry
        if record.stored_size < 4:
            raise ResourceArchiveError(f"{record.path} block is shorter than its size prefix")
        prefix = self._read_decoded(record.offset, 4)
        return int.from_bytes(prefix, "big")

    def read(self, entry: ResourceEntry | str) -> bytes:
        """Decode and decompress one resource without modifying the archive."""
        record = self.get(entry) if isinstance(entry, str) else entry
        block = self._read_decoded(record.offset, record.stored_size)
        return self._inflate_block(block, record.path)

    def matching(self, query: str = "") -> list[ResourceEntry]:
        """Return resource records matching a case-insensitive path fragment."""
        needle = query.strip().casefold()
        if not needle:
            return list(self.entries)
        return [entry for entry in self.entries if needle in entry.path.casefold()]
