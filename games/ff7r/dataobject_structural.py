"""Additional fail-closed structural operations for FF7R DataObject arrays.

The core DataObject writer intentionally keeps its ordinary edit API fixed-size.
This companion implements only insertion into an already-declared fixed-width
array. It never adds properties, table rows, FStrings, or FName-map entries.
"""

from __future__ import annotations

import struct
from typing import Any

from .dataobject import (
    BOOLEAN,
    BOOLEAN_BYTE,
    BYTE,
    FLOAT,
    INT16,
    INT32,
    MAX_ARRAY_ELEMENTS,
    NAME,
    STRING,
    DataObjectPackage,
    FormatError,
)


FIXED_WIDTH_ARRAY_INSERT_SUPPORTED = True


def _encode_array_value(package: DataObjectPackage, type_code: int, value: Any) -> bytes:
    normalized = package._normalize(type_code, value)
    if type_code == BOOLEAN:
        return struct.pack("<B", int(normalized))
    if type_code == BOOLEAN_BYTE:
        return struct.pack("<B", int(normalized))
    if type_code == BYTE:
        return struct.pack("<B", normalized)
    if type_code == INT16:
        return struct.pack("<h", normalized)
    if type_code == INT32:
        return struct.pack("<i", normalized)
    if type_code == FLOAT:
        return struct.pack("<f", normalized)
    if type_code == NAME:
        return struct.pack("<iI", package.uasset.names.index(normalized), 0)
    raise ValueError(f"Property type {type_code} cannot be inserted")


def insert_array_element(
    package: DataObjectPackage,
    entry_index: int,
    prop_name: str,
    value: Any,
    *,
    array_index: int | None = None,
) -> int:
    """Insert one value into an existing fixed-width array and reparse.

    ``array_index=None`` appends. Any failure after byte insertion restores the
    complete in-memory package state before re-raising.
    """
    if entry_index < 0 or entry_index >= len(package.entries):
        raise IndexError(f"Entry index out of range: {entry_index}")
    prop = package._property(prop_name)
    if not prop.is_array:
        raise ValueError(f"{prop_name} is not an array")
    if prop.type_code == STRING:
        raise ValueError(f"{prop_name} is variable-width and cannot be structurally edited")

    entry = package.entries[entry_index]
    field = entry.offsets[prop_name]
    if field.length is None:
        raise FormatError(f"{prop_name} is missing its array length")
    if field.length >= MAX_ARRAY_ELEMENTS:
        raise ValueError(f"{prop_name} is already at the maximum supported array length")

    index = field.length if array_index is None else int(array_index)
    if index < 0 or index > field.length:
        raise IndexError(f"Array insertion index out of range for {prop_name}: {index}")

    normalized = package._normalize(prop.type_code, value)
    encoded = _encode_array_value(package, prop.type_code, normalized)
    width = package._width(prop.type_code, array=True)
    if len(encoded) != width:
        raise FormatError(f"Encoded {prop_name} element width does not match its declared type")

    element_offset = field.offset + 4 + index * width
    if element_offset < field.offset + 4 or element_offset > len(package.uexp_bytes):
        raise FormatError(f"Insertion for {prop_name} is outside {package.uexp_path.name}")

    old_uasset_bytes = bytearray(package.uasset_bytes)
    old_uexp_bytes = bytearray(package.uexp_bytes)
    old_uasset = package.uasset
    old_properties = package.properties
    old_entries = package.entries
    try:
        package.uexp_bytes[element_offset:element_offset] = encoded
        struct.pack_into("<i", package.uexp_bytes, field.offset, field.length + 1)
        package._adjust_export_serial_size(width)
        package.properties, package.entries = package._parse_uexp()

        updated = package.entries[entry_index].values[prop_name]
        if len(updated) != field.length + 1 or updated[index] != normalized:
            raise RuntimeError(f"FF7R structural insertion failed readback for {prop_name}[{index}]")
    except Exception:
        package.uasset_bytes = old_uasset_bytes
        package.uexp_bytes = old_uexp_bytes
        package.uasset = old_uasset
        package.properties = old_properties
        package.entries = old_entries
        raise
    return index


def append_array_element(
    package: DataObjectPackage,
    entry_index: int,
    prop_name: str,
    value: Any,
) -> int:
    """Append one value to an existing fixed-width DataObject array."""
    return insert_array_element(package, entry_index, prop_name, value, array_index=None)
