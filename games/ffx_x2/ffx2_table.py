"""Validated fixed-record container used by researched Final Fantasy X-2 tables."""
from __future__ import annotations

from dataclasses import dataclass
import struct


HEADER_SIZE = 0x20


class FFX2TableError(ValueError):
    """Raised when an FFX-2 generic table violates its proved container layout."""


@dataclass(frozen=True)
class FFX2Table:
    data: bytes
    min_index: int
    max_index: int
    record_size: int
    record_bytes: int

    @property
    def record_count(self) -> int:
        return self.max_index - self.min_index + 1

    @property
    def records_end(self) -> int:
        return HEADER_SIZE + self.record_bytes

    def record_offset(self, record_id: int) -> int:
        if not self.min_index <= record_id <= self.max_index:
            raise FFX2TableError(
                f"Record ID must be between {self.min_index} and {self.max_index}: {record_id}"
            )
        return HEADER_SIZE + (record_id - self.min_index) * self.record_size

    def record(self, record_id: int) -> bytes:
        offset = self.record_offset(record_id)
        return self.data[offset:offset + self.record_size]


def parse_table(data: bytes) -> FFX2Table:
    """Parse the 32-bit-index FFX-2 table container used by FFXDataParser."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < HEADER_SIZE:
        raise FFX2TableError("FFX-2 table is smaller than its 0x20-byte header")
    raw = bytes(data)
    min_index, max_index, record_size, record_bytes = struct.unpack_from("<IIII", raw, 0x0C)
    if max_index < min_index:
        raise FFX2TableError(f"FFX-2 table index range is reversed: {min_index}..{max_index}")
    if record_size == 0:
        raise FFX2TableError("FFX-2 table record size is zero")
    record_count = max_index - min_index + 1
    expected = record_count * record_size
    if record_bytes != expected:
        raise FFX2TableError(
            f"FFX-2 table record byte count is inconsistent: {record_bytes} != {record_count} × {record_size}"
        )
    if HEADER_SIZE + record_bytes > len(raw):
        raise FFX2TableError("FFX-2 table fixed-record region is truncated")
    return FFX2Table(
        data=raw,
        min_index=min_index,
        max_index=max_index,
        record_size=record_size,
        record_bytes=record_bytes,
    )
