"""Validated fixed-record table support for Final Fantasy X data files.

Many FFX kernel files share a compact header followed by fixed-size records and
optional trailing string data.  This module only models the proved common
container; game-specific record semantics live in separate modules.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct


HEADER_SIZE = 0x14
MAX_RECORDS = 0x10000


class FFXTableError(ValueError):
    """Raised when a fixed-record FFX table violates the proved container layout."""


@dataclass(frozen=True)
class FFXTable:
    data: bytes
    min_index: int
    max_index: int
    record_size: int
    total_record_bytes: int

    @property
    def count(self) -> int:
        return self.max_index - self.min_index + 1

    @property
    def records_offset(self) -> int:
        return HEADER_SIZE

    @property
    def records_end(self) -> int:
        return HEADER_SIZE + self.total_record_bytes

    def record_offset(self, record_id: int) -> int:
        if not self.min_index <= record_id <= self.max_index:
            raise IndexError(f"FFX table record is outside {self.min_index}..{self.max_index}: {record_id}")
        return HEADER_SIZE + (record_id - self.min_index) * self.record_size

    def record(self, record_id: int) -> bytes:
        offset = self.record_offset(record_id)
        return self.data[offset:offset + self.record_size]


def parse_table(data: bytes) -> FFXTable:
    """Parse the common FFX fixed-record container without interpreting records.

    Proven fields are little-endian u16 values at offsets 0x08..0x0F:
    minimum index, maximum index, individual record length, and the total byte
    length of the fixed-record region. Records begin at 0x14. Any bytes after
    that region are preserved as opaque trailing data.
    """
    raw = bytes(data)
    if len(raw) < HEADER_SIZE:
        raise FFXTableError(f"FFX table is shorter than its 0x{HEADER_SIZE:X}-byte header")
    min_index, max_index, record_size, total_length = struct.unpack_from("<HHHH", raw, 0x08)
    if max_index < min_index:
        raise FFXTableError(f"FFX table has an inverted index range: {min_index}..{max_index}")
    count = max_index - min_index + 1
    if count <= 0 or count > MAX_RECORDS:
        raise FFXTableError(f"FFX table has an unreasonable record count: {count}")
    if record_size <= 0:
        raise FFXTableError("FFX table has a zero record size")
    expected = count * record_size
    if total_length != expected:
        raise FFXTableError(
            f"FFX table record byte count does not match its index range: {total_length} != {expected}"
        )
    end = HEADER_SIZE + total_length
    if end > len(raw):
        raise FFXTableError("FFX table record region extends beyond the file")
    return FFXTable(
        data=raw,
        min_index=min_index,
        max_index=max_index,
        record_size=record_size,
        total_record_bytes=total_length,
    )
