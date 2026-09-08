"""Additional fail-closed structural operations for FF7R DataObjects.

The core DataObject writer intentionally keeps its ordinary edit API fixed-size.
This companion implements only structural operations whose existing package
shape can be fully re-parsed and byte/readback validated:
- insertion into an already-declared fixed-width array;
- cloning one existing row under an FName already present in the package name map;
- replacing one scalar FString while repairing the export serialized size.

It never adds properties or FName-map entries. Row cloning is deliberately a
"clone an existing proved template" primitive rather than arbitrary schema
construction.
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
    MAX_ENTRIES,
    NAME,
    STRING,
    DataObjectPackage,
    FormatError,
    Reader,
    _read_fname,
)


FIXED_WIDTH_ARRAY_INSERT_SUPPORTED = True
EXISTING_FNAME_ROW_CLONE_SUPPORTED = True
SCALAR_FSTRING_REPLACE_SUPPORTED = True


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


def _encode_fstring(value: str) -> bytes:
    if not isinstance(value, str):
        raise TypeError("FF7R DataObject FString values must be strings")
    if "\0" in value:
        raise ValueError("FF7R DataObject FString values cannot contain NUL characters")
    try:
        raw = value.encode("ascii")
    except UnicodeEncodeError:
        raw = value.encode("utf-16-le")
        return struct.pack("<i", -(len(raw) // 2 + 1)) + raw + b"\0\0"
    return struct.pack("<i", len(raw) + 1) + raw + b"\0"


def _entry_bounds(package: DataObjectPackage, entry_index: int) -> tuple[int, int]:
    """Return the exact serialized byte range for one parsed table row."""
    if entry_index < 0 or entry_index >= len(package.entries):
        raise IndexError(f"Entry index out of range: {entry_index}")
    if not package.properties:
        raise FormatError("Cannot structurally clone a DataObject with no declared properties")

    entry = package.entries[entry_index]
    first = entry.offsets[package.properties[0].name].offset
    start = first - 8  # row-tag FName immediately precedes the first value
    if start < 0:
        raise FormatError(f"Entry {entry_index} has an invalid serialized start")

    reader = Reader(package.uexp_bytes, package.uexp_path.name)
    reader.seek(start)
    parsed_tag = _read_fname(reader, package.uasset.names)
    if parsed_tag != entry.tag:
        raise FormatError(
            f"Entry {entry_index} tag readback changed: expected {entry.tag!r}, found {parsed_tag!r}"
        )
    for prop in package.properties:
        if prop.is_array:
            length = reader.int32()
            if length < 0 or length > MAX_ARRAY_ELEMENTS:
                raise FormatError(f"Invalid array length {length} while locating {prop.name}")
            for _ in range(length):
                package._read_value(reader, prop.type_code, array=True)
        else:
            package._read_value(reader, prop.type_code, array=False)
    return start, reader.pos


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


def append_cloned_entry(
    package: DataObjectPackage,
    source_entry_index: int,
    new_tag: str,
) -> int:
    """Clone one existing row under an unused FName already in the package.

    This does not expand the package name map. The source row's serialized bytes
    are preserved exactly apart from the new row-tag FName, so variable-width
    fields, arrays and unknown semantic values retain the proved template shape.
    """
    if len(package.entries) >= MAX_ENTRIES:
        raise ValueError("DataObject is already at the maximum supported entry count")
    if not isinstance(new_tag, str) or new_tag not in package.uasset.names:
        raise ValueError(f"New row tag must already exist in {package.uasset_path.name}: {new_tag!r}")
    if any(entry.tag == new_tag for entry in package.entries):
        raise ValueError(f"DataObject row tag already exists: {new_tag}")

    source_start, source_end = _entry_bounds(package, source_entry_index)
    _last_start, table_end = _entry_bounds(package, len(package.entries) - 1)
    if source_end <= source_start or table_end > len(package.uexp_bytes):
        raise FormatError("Could not determine safe DataObject row boundaries")
    clone = bytearray(package.uexp_bytes[source_start:source_end])
    if len(clone) < 8:
        raise FormatError("Serialized DataObject row is too small to contain its FName tag")
    struct.pack_into("<iI", clone, 0, package.uasset.names.index(new_tag), 0)

    old_uasset_bytes = bytearray(package.uasset_bytes)
    old_uexp_bytes = bytearray(package.uexp_bytes)
    old_uasset = package.uasset
    old_properties = package.properties
    old_entries = package.entries
    old_count = len(package.entries)
    try:
        declared_count = struct.unpack_from("<i", package.uexp_bytes, 0x0A)[0]
        if declared_count != old_count:
            raise FormatError(
                f"DataObject entry-count field changed: expected {old_count}, found {declared_count}"
            )
        package.uexp_bytes[table_end:table_end] = clone
        struct.pack_into("<i", package.uexp_bytes, 0x0A, old_count + 1)
        package._adjust_export_serial_size(len(clone))
        package.properties, package.entries = package._parse_uexp()
        if len(package.entries) != old_count + 1:
            raise RuntimeError("FF7R cloned-row insertion failed entry-count readback")
        added = package.entries[-1]
        source = package.entries[source_entry_index]
        if added.tag != new_tag or added.values != source.values:
            raise RuntimeError("FF7R cloned-row insertion failed value/tag readback")
    except Exception:
        package.uasset_bytes = old_uasset_bytes
        package.uexp_bytes = old_uexp_bytes
        package.uasset = old_uasset
        package.properties = old_properties
        package.entries = old_entries
        raise
    return old_count


def replace_scalar_fstring(
    package: DataObjectPackage,
    entry_index: int,
    prop_name: str,
    value: str,
) -> None:
    """Replace one scalar FString, allowing a size change, then fully reparse."""
    if entry_index < 0 or entry_index >= len(package.entries):
        raise IndexError(f"Entry index out of range: {entry_index}")
    prop = package._property(prop_name)
    if prop.type_code != STRING or prop.is_array:
        raise ValueError(f"{prop_name} is not a scalar FString")
    encoded = _encode_fstring(value)
    field = package.entries[entry_index].offsets[prop_name]
    reader = Reader(package.uexp_bytes, package.uexp_path.name)
    reader.seek(field.offset)
    reader.fstring()
    old_end = reader.pos
    if old_end < field.offset or old_end > len(package.uexp_bytes):
        raise FormatError(f"{prop_name} FString range is outside {package.uexp_path.name}")

    old_uasset_bytes = bytearray(package.uasset_bytes)
    old_uexp_bytes = bytearray(package.uexp_bytes)
    old_uasset = package.uasset
    old_properties = package.properties
    old_entries = package.entries
    delta = len(encoded) - (old_end - field.offset)
    try:
        package.uexp_bytes[field.offset:old_end] = encoded
        package._adjust_export_serial_size(delta)
        package.properties, package.entries = package._parse_uexp()
        if package.entries[entry_index].values[prop_name] != value:
            raise RuntimeError(f"FF7R FString replacement failed readback for {prop_name}")
    except Exception:
        package.uasset_bytes = old_uasset_bytes
        package.uexp_bytes = old_uexp_bytes
        package.uasset = old_uasset
        package.properties = old_properties
        package.entries = old_entries
        raise
