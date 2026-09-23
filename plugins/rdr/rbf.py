"""Protected RDR1 RBF0 scalar parser/editor.

This module intentionally does not reserialize RBF documents. Public RDR1
format research establishes the RBF0 record tags and fixed-width primitive
payloads. Lexeditor parses enough structure to identify boolean, uint32 and
float leaves, then patches only the exact bytes which encode those leaves.
Strings, vectors, byte blocks and unknown tags remain read-only and their bytes
are preserved verbatim.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Any


MAGIC = b"RBF0"
TYPE_STRUCTURE = 0x00
TYPE_UINT32 = 0x10
TYPE_BOOL_TRUE = 0x20
TYPE_BOOL_FALSE = 0x30
TYPE_FLOAT = 0x40
TYPE_FLOAT3 = 0x50
TYPE_STRING = 0x60
SUPPORTED_TYPES = {
    TYPE_STRUCTURE, TYPE_UINT32, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE,
    TYPE_FLOAT, TYPE_FLOAT3, TYPE_STRING,
}
EDITABLE_TYPES = {TYPE_UINT32, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_FLOAT}
MAX_NAME_BYTES = 0x7FFF


@dataclass
class _Context:
    path: str
    pending_attributes: int


class _Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def need(self, count: int) -> None:
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError("RBF0 record extends beyond the file")

    def u8(self) -> int:
        self.need(1)
        value = self.data[self.pos]
        self.pos += 1
        return value

    def i16(self) -> int:
        self.need(2)
        value = struct.unpack_from("<h", self.data, self.pos)[0]
        self.pos += 2
        return value

    def i32(self) -> int:
        self.need(4)
        value = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return value

    def take(self, count: int) -> bytes:
        self.need(count)
        value = self.data[self.pos:self.pos + count]
        self.pos += count
        return value


def _decode_name(raw: bytes) -> str:
    try:
        value = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("RBF0 descriptor name is not ASCII") from error
    if not value or any(ord(char) < 0x20 for char in value):
        raise ValueError("RBF0 descriptor name is empty or contains control bytes")
    return value


def parse(data: bytes | bytearray | memoryview) -> dict[str, Any]:
    """Parse bounded RBF0 structure and return only safe scalar leaves.

    ``trailingBytes`` reports bytes after the root close marker; they remain
    unchanged because the editor only patches known fixed-width scalar spans.
    """
    raw = bytes(data)
    reader = _Reader(raw)
    if reader.take(4) != MAGIC:
        raise ValueError("Expected RBF0 header")

    descriptors: list[tuple[str, int]] = []
    stack: list[_Context] = []
    current: _Context | None = None
    root_seen = False
    root_closed = False
    scalars: list[dict[str, Any]] = []
    skipped = {"strings": 0, "float3": 0, "byteBlocks": 0}

    while reader.pos < len(raw):
        record_offset = reader.pos
        descriptor_index = reader.u8()

        if descriptor_index == 0xFF:
            if reader.u8() != 0xFF:
                raise ValueError("Malformed RBF0 close marker")
            if current is None:
                raise ValueError("RBF0 close marker has no open structure")
            if current.pending_attributes:
                raise ValueError(
                    "RBF0 structure closed before all advertised attributes were read"
                )
            if stack:
                current = stack.pop()
            else:
                current = None
                root_closed = True
                break
            continue

        if descriptor_index == 0xFD:
            if reader.u8() != 0xFF:
                raise ValueError("Malformed RBF0 byte-block marker")
            length = reader.i32()
            if length < 0:
                raise ValueError("RBF0 byte-block length is negative")
            reader.take(length)
            skipped["byteBlocks"] += 1
            continue

        type_offset = reader.pos
        data_type = reader.u8()
        if data_type not in SUPPORTED_TYPES:
            raise ValueError(f"Unsupported RBF0 data type 0x{data_type:02X}")

        if descriptor_index == len(descriptors):
            if descriptor_index >= 0xFD:
                raise ValueError("RBF0 descriptor table exceeds reserved index space")
            name_length = reader.i16()
            if name_length <= 0 or name_length > MAX_NAME_BYTES:
                raise ValueError("RBF0 descriptor name length is invalid")
            name = _decode_name(reader.take(name_length))
            descriptors.append((name, data_type))
        elif descriptor_index < len(descriptors):
            name = descriptors[descriptor_index][0]
        else:
            raise ValueError("RBF0 descriptor index refers past the descriptor table")

        if data_type == TYPE_STRUCTURE:
            reader.i16()
            reader.i16()
            pending = reader.i16()
            if pending < 0:
                raise ValueError("RBF0 structure has a negative attribute count")
            if current is None:
                if root_seen:
                    raise ValueError("RBF0 contains a second root structure")
                path = name
                root_seen = True
            else:
                stack.append(current)
                path = f"{current.path}/{name}"
            current = _Context(path=path, pending_attributes=pending)
            continue

        if current is None:
            raise ValueError("RBF0 primitive appears outside a structure")
        is_attribute = current.pending_attributes > 0
        if is_attribute:
            current.pending_attributes -= 1
        field_path = f"{current.path}/@{name}" if is_attribute else f"{current.path}/{name}"

        write_offset: int | None = None
        write_size = 0
        value: Any = None
        kind = ""

        if data_type == TYPE_UINT32:
            write_offset = reader.pos
            reader.need(4)
            value = struct.unpack_from("<I", raw, reader.pos)[0]
            reader.pos += 4
            write_size = 4
            kind = "uint32"
        elif data_type in {TYPE_BOOL_TRUE, TYPE_BOOL_FALSE}:
            write_offset = type_offset
            write_size = 1
            value = data_type == TYPE_BOOL_TRUE
            kind = "bool"
        elif data_type == TYPE_FLOAT:
            write_offset = reader.pos
            reader.need(4)
            value = struct.unpack_from("<f", raw, reader.pos)[0]
            reader.pos += 4
            write_size = 4
            kind = "float"
        elif data_type == TYPE_FLOAT3:
            reader.take(12)
            skipped["float3"] += 1
        elif data_type == TYPE_STRING:
            length = reader.i16()
            if length < 0:
                raise ValueError("RBF0 string length is negative")
            reader.take(length)
            skipped["strings"] += 1

        if data_type in EDITABLE_TYPES:
            assert write_offset is not None
            scalars.append({
                "recordOffset": record_offset,
                "descriptorIndex": descriptor_index,
                "name": name,
                "path": field_path,
                "role": "attribute" if is_attribute else "child",
                "kind": kind,
                "value": value,
                "typeOffset": type_offset,
                "writeOffset": write_offset,
                "writeSize": write_size,
                "rawHex": raw[write_offset:write_offset + write_size].hex(),
            })

    if not root_seen:
        raise ValueError("RBF0 contains no root structure")
    if not root_closed:
        raise ValueError("RBF0 root structure is not closed")

    return {
        "scalars": scalars,
        "descriptorCount": len(descriptors),
        "trailingBytes": len(raw) - reader.pos,
        "skipped": skipped,
    }


def supports(data: bytes | bytearray | memoryview) -> bool:
    try:
        return bool(parse(data)["scalars"])
    except (ValueError, struct.error):
        return False


def _expected_row(rows: list[dict[str, Any]], edit: dict) -> dict[str, Any]:
    offset = edit.get("recordOffset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 4:
        raise ValueError("RBF0 edit recordOffset must be a non-negative integer")
    matches = [row for row in rows if row["recordOffset"] == offset]
    if len(matches) != 1:
        raise ValueError("RBF0 edit no longer identifies exactly one scalar")
    row = matches[0]
    for key in ("path", "kind", "rawHex"):
        if str(edit.get(key, "")) != str(row[key]):
            raise ValueError(f"RBF0 scalar changed since it was loaded ({key})")
    return row


def _encode_value(row: dict[str, Any], value: Any) -> bytes:
    kind = row["kind"]
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError("RBF0 boolean edit must be true or false")
        return bytes([TYPE_BOOL_TRUE if value else TYPE_BOOL_FALSE])
    if kind == "uint32":
        if isinstance(value, bool):
            raise ValueError("RBF0 uint32 edit must be an integer")
        try:
            number = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError("RBF0 uint32 edit must be an integer") from error
        if str(value).strip() != str(number) and not isinstance(value, int):
            raise ValueError("RBF0 uint32 edit must be an integer")
        if not 0 <= number <= 0xFFFFFFFF:
            raise ValueError("RBF0 uint32 edit is outside 0..4294967295")
        return struct.pack("<I", number)
    if kind == "float":
        if isinstance(value, bool):
            raise ValueError("RBF0 float edit must be a number")
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError("RBF0 float edit must be a number") from error
        if not math.isfinite(number):
            raise ValueError("RBF0 float edit must be finite")
        try:
            encoded = struct.pack("<f", number)
        except (OverflowError, struct.error) as error:
            raise ValueError("RBF0 float edit is outside float32 range") from error
        if not math.isfinite(struct.unpack("<f", encoded)[0]):
            raise ValueError("RBF0 float edit is outside finite float32 range")
        return encoded
    raise ValueError(f"RBF0 scalar kind is not editable: {kind}")


def apply_scalar_edits(data: bytes, edits: list[dict]) -> tuple[bytes, int]:
    if not isinstance(edits, list):
        raise ValueError("RBF0 edits must be a list")
    document = parse(data)
    rows = document["scalars"]
    candidate = bytearray(data)
    seen: set[int] = set()
    changed = 0
    spans: list[tuple[int, int]] = []

    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("Each RBF0 edit must be an object")
        row = _expected_row(rows, edit)
        record_offset = row["recordOffset"]
        if record_offset in seen:
            raise ValueError("RBF0 scalar was edited more than once")
        seen.add(record_offset)
        encoded = _encode_value(row, edit.get("value"))
        start = row["writeOffset"]
        end = start + row["writeSize"]
        if len(encoded) != row["writeSize"]:
            raise AssertionError("RBF0 protected edit changed field width")
        if candidate[start:end] != encoded:
            candidate[start:end] = encoded
            spans.append((start, end))
            changed += 1

    result = bytes(candidate)
    reparsed = parse(result)
    by_offset = {row["recordOffset"]: row for row in reparsed["scalars"]}
    for edit in edits:
        offset = edit["recordOffset"]
        if offset not in by_offset:
            raise RuntimeError("RBF0 edited scalar disappeared after patch")

    if changed:
        covered = bytearray(len(data))
        for start, end in spans:
            covered[start:end] = b"\x01" * (end - start)
        if any(a != b for index, (a, b) in enumerate(zip(data, result)) if not covered[index]):
            raise RuntimeError("RBF0 patch changed bytes outside edited scalar spans")
    return result, changed
