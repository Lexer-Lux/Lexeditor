"""Narrow FF7 Rebirth IoStore-state DataObject reader/editor.

This module supports only fixed-width, in-place value edits demonstrated by
public Rebirth DataObject format work. It never rebuilds packages, resizes
arrays, or reinterprets unknown bytes. Saving patches values into an exact copy
of the source asset.

Format research:
- Synthlight/FF7R2-DataObject-Parser (CC BY-NC 4.0), documentation only.
- Yoraiz0r/FF7RebirthDataObjectEditor (MIT), behavior cross-check.

No source code from either project is vendored here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import struct
from typing import Any


class DataObjectError(ValueError):
    """The asset is not a safely supported Rebirth DataObject shape."""


_TYPES = {
    1: ("BoolProperty", "bool", 1, None, None),
    2: ("ByteProperty", "uint8", 1, 0, 0xFF),
    3: ("Int8Property", "int8", 1, -0x80, 0x7F),
    4: ("UInt16Property", "uint16", 2, 0, 0xFFFF),
    5: ("Int16Property", "int16", 2, -0x8000, 0x7FFF),
    6: ("UIntProperty", "uint32", 4, 0, 0xFFFFFFFF),
    7: ("IntProperty", "int32", 4, -0x80000000, 0x7FFFFFFF),
    8: ("Int64Property", "int64", 8, -(1 << 63), (1 << 63) - 1),
    9: ("FloatProperty", "float", 4, None, None),
    10: ("StrProperty", "string", 16, None, None),
    11: ("NameProperty", "name", 8, None, None),
}
_STRUCTS = {
    1: "<?", 2: "<B", 3: "<b", 4: "<H", 5: "<h",
    6: "<I", 7: "<i", 8: "<q", 9: "<f",
}


def _need(data: bytes | bytearray, offset: int, size: int, what: str) -> None:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise DataObjectError(f"{what} is outside the asset")


def _u32(data: bytes | bytearray, offset: int, what: str) -> int:
    _need(data, offset, 4, what)
    return struct.unpack_from("<I", data, offset)[0]


def _i32(data: bytes | bytearray, offset: int, what: str) -> int:
    _need(data, offset, 4, what)
    return struct.unpack_from("<i", data, offset)[0]


def _u64(data: bytes | bytearray, offset: int, what: str) -> int:
    _need(data, offset, 8, what)
    return struct.unpack_from("<Q", data, offset)[0]


def _align(position: int, boundary: int, base: int) -> int:
    relative = position - base
    return base + ((relative + boundary - 1) // boundary) * boundary


@dataclass(frozen=True)
class FName:
    text: str
    index: int
    number: int

    @property
    def display(self) -> str:
        return self.text if self.number == 0 else f"{self.text} [name-number {self.number}]"


@dataclass(frozen=True)
class Property:
    name: str
    type_id: int
    type_name: str
    kind: str
    is_array: bool


@dataclass
class Field:
    name: str
    type_id: int
    type_name: str
    kind: str
    value: Any
    offset: int
    size: int
    editable: bool
    minimum: int | None = None
    maximum: int | None = None
    note: str = ""

    def payload(self) -> dict:
        payload = {
            "name": self.name, "typeId": self.type_id, "type": self.type_name,
            "kind": self.kind, "value": self.value, "editable": self.editable,
            "minimum": self.minimum, "maximum": self.maximum, "note": self.note,
        }
        if self.kind == "array":
            payload["arrayCount"] = len(self.value) if isinstance(self.value, list) else 0
        return payload


@dataclass
class Record:
    key: FName
    fields: list[Field]

    def payload(self) -> dict:
        return {
            "key": self.key.display, "name": self.key.text,
            "nameIndex": self.key.index, "nameNumber": self.key.number,
            "fields": [field.payload() for field in self.fields],
        }


class DataObjectPackage:
    """Parsed Rebirth DataObject plus an exact mutable copy of its bytes."""

    def __init__(self, source: bytes, names: list[str], records: list[Record]):
        self.source_bytes = bytes(source)
        self.bytes = bytearray(source)
        self.names = list(names)
        self.records = records
        self.source_sha256 = hashlib.sha256(source).hexdigest()

    @classmethod
    def from_bytes(cls, source: bytes) -> "DataObjectPackage":
        data = bytes(source)
        if len(data) < 64:
            raise DataObjectError("DataObject is smaller than the 64-byte package summary")

        (
            names_offset, names_size, hashes_offset, hashes_size,
            import_offset, export_offset, bundles_offset, graph_offset, graph_size,
        ) = struct.unpack_from("<9i", data, 24)
        ordered = [names_offset, hashes_offset, import_offset, export_offset,
                   bundles_offset, graph_offset, graph_offset + graph_size]
        if any(value < 0 for value in ordered) or ordered != sorted(ordered):
            raise DataObjectError("Package summary offsets are not ordered")
        if graph_offset + graph_size > len(data):
            raise DataObjectError("Package graph data exceeds the asset")
        if names_size < 0 or names_offset + names_size > len(data):
            raise DataObjectError("Name map exceeds the asset")
        if hashes_size < 8 or hashes_size % 8:
            raise DataObjectError("Name hash map has an unsupported size")

        expected_names = hashes_size // 8 - 1
        names: list[str] = []
        cursor = names_offset
        for index in range(expected_names):
            _need(data, cursor, 2, f"name header {index}")
            data0, data1 = data[cursor], data[cursor + 1]
            cursor += 2
            utf16 = bool(data0 & 0x80)
            length = ((data0 & 0x7F) << 8) | data1
            byte_count = length * (2 if utf16 else 1)
            _need(data, cursor, byte_count, f"name {index}")
            raw = data[cursor:cursor + byte_count]
            cursor += byte_count
            try:
                text = raw.decode("utf-16-le" if utf16 else "ascii")
            except UnicodeDecodeError as error:
                raise DataObjectError(f"name {index} is not valid serialized text") from error
            names.append(text)
        if cursor > names_offset + names_size:
            raise DataObjectError("Serialized names overrun the declared name map")

        export_bytes = bundles_offset - export_offset
        if export_bytes != 72:
            raise DataObjectError(
                f"Expected one 72-byte Rebirth export entry; found {export_bytes} bytes")
        inner = graph_offset + graph_size
        _need(data, inner, 24, "DataObject export")

        tag = cls._read_fname(data, inner, names, "inner tag")
        if tag.text != "None":
            raise DataObjectError(f"Tagged inner assets are not supported (found {tag.display})")
        some_bool = _i32(data, inner + 8, "inner GUID flag")
        if some_bool != 0:
            raise DataObjectError(
                "GUID-bearing inner assets are outside this bounded DataObject integration")

        archive = inner + 12
        frozen_size = _u32(data, archive, "frozen size")
        padding = struct.unpack_from("<H", data, archive + 10)[0]
        frozen_start = archive + 12 + padding
        frozen_end = frozen_start + frozen_size
        _need(data, frozen_start, frozen_size, "frozen object")
        _need(data, frozen_end, 12, "frozen name counts")

        cursor = frozen_end
        num_vtables, num_script, num_minimal = struct.unpack_from("<iii", data, cursor)
        cursor += 12
        if min(num_vtables, num_script, num_minimal) < 0:
            raise DataObjectError("Frozen name counts are negative")
        if max(num_vtables, num_script, num_minimal) > 1_000_000:
            raise DataObjectError("Frozen name counts are implausibly large")

        for index in range(num_vtables):
            cls._read_fname(data, cursor, names, f"vtable {index}")
            count = _u32(data, cursor + 8, f"vtable patch count {index}")
            cursor += 12
            _need(data, cursor, count * 12, f"vtable patches {index}")
            cursor += count * 12

        for index in range(num_script):
            cls._read_fname(data, cursor, names, f"script name {index}")
            count = _u32(data, cursor + 8, f"script name offsets {index}")
            cursor += 12
            _need(data, cursor, count * 4, f"script name offsets {index}")
            cursor += count * 4

        offset_names: dict[int, FName] = {}
        for index in range(num_minimal):
            name = cls._read_fname(data, cursor, names, f"minimal name {index}")
            count = _u32(data, cursor + 8, f"minimal name offsets {index}")
            cursor += 12
            _need(data, cursor, count * 4, f"minimal name offsets {index}")
            for _ in range(count):
                relative = _u32(data, cursor, "minimal name offset")
                cursor += 4
                if relative >= frozen_size:
                    raise DataObjectError("Minimal-name offset points outside the frozen object")
                offset_names[relative] = name

        key_header = frozen_start
        index_header = key_header + 40
        property_header = index_header + 16
        entry_header = property_header + 16
        _need(data, key_header, 88, "frozen root proxy headers")

        key_pos, key_count = cls._sparse_target(data, key_header, frozen_start, "keys")
        property_pos, property_count = cls._array_target(
            data, property_header, frozen_start, "properties")
        entry_pos, entry_count = cls._array_target(
            data, entry_header, frozen_start, "entries")
        if key_count != entry_count:
            raise DataObjectError(
                f"Key/entry counts differ ({key_count} keys, {entry_count} entries)")

        keys: list[FName] = []
        for index in range(key_count):
            position = key_pos + index * 20
            _need(data, position, 20, f"key {index}")
            relative = position - frozen_start
            try:
                keys.append(offset_names[relative])
            except KeyError as error:
                raise DataObjectError(
                    f"Key {index} has no minimal-name identity at frozen offset {relative}") from error

        properties: list[Property] = []
        for index in range(property_count):
            position = property_pos + index * 12
            _need(data, position, 12, f"property {index}")
            relative = position - frozen_start
            try:
                name = offset_names[relative].text
            except KeyError as error:
                raise DataObjectError(
                    f"Property {index} has no minimal-name identity at frozen offset {relative}") from error
            type_id = _i32(data, position + 8, f"property type {index}")
            info = _TYPES.get(type_id)
            if info is None:
                raise DataObjectError(f"Property {name} uses unknown type id {type_id}")
            type_name, kind, _size, _minimum, _maximum = info
            properties.append(Property(
                name=name, type_id=type_id, type_name=type_name,
                kind=kind, is_array=name.endswith("_Array")))

        records: list[Record] = []
        cursor = entry_pos
        for key in keys:
            fields: list[Field] = []
            for prop in properties:
                field, cursor = cls._read_field(
                    data, cursor, frozen_start, frozen_end, names, offset_names, prop,
                    f"{key.display}.{prop.name}")
                fields.append(field)
            records.append(Record(key=key, fields=fields))

        return cls(data, names, records)

    @staticmethod
    def _read_fname(data: bytes, offset: int, names: list[str], what: str) -> FName:
        _need(data, offset, 8, what)
        index, number = struct.unpack_from("<iI", data, offset)
        if not 0 <= index < len(names):
            raise DataObjectError(f"{what} references name index {index}, outside the name map")
        return FName(names[index], index, number)

    @staticmethod
    def _pointer_target(data: bytes, header: int, frozen_start: int, what: str) -> int:
        packed = _u64(data, header, f"{what} pointer")
        signed = struct.unpack("<q", struct.pack("<Q", packed))[0]
        offset = signed >> 1
        target = header + offset
        if target < frozen_start or target > len(data):
            raise DataObjectError(f"{what} pointer leaves the frozen object")
        return target

    @classmethod
    def _array_target(cls, data: bytes, header: int, frozen_start: int,
                      what: str) -> tuple[int, int]:
        _need(data, header, 16, f"{what} array header")
        count, maximum = struct.unpack_from("<ii", data, header + 8)
        if count < 0 or maximum < count or count > 1_000_000:
            raise DataObjectError(f"{what} array count is invalid")
        if count == 0:
            return header, 0
        return cls._pointer_target(data, header, frozen_start, what), count

    @classmethod
    def _sparse_target(cls, data: bytes, header: int, frozen_start: int,
                       what: str) -> tuple[int, int]:
        _need(data, header, 40, f"{what} sparse-array header")
        count, maximum = struct.unpack_from("<ii", data, header + 8)
        if count < 0 or maximum != count or count > 1_000_000:
            raise DataObjectError(
                f"{what} sparse array is unsupported (count={count}, max={maximum})")
        if count == 0:
            return header, 0
        return cls._pointer_target(data, header, frozen_start, what), count

    @classmethod
    def _read_array_elements(cls, data: bytes, header: int, frozen_start: int,
                             frozen_end: int, offset_names: dict[int, FName],
                             prop: Property, count: int, what: str) -> list[Any]:
        if count == 0:
            return []
        cursor = cls._pointer_target(data, header, frozen_start, what)
        if not frozen_start <= cursor < frozen_end:
            raise DataObjectError(f"{what} array data leaves the frozen object")
        values: list[Any] = []
        type_name, _kind, size, _minimum, _maximum = _TYPES[prop.type_id]

        for index in range(count):
            item = f"{what}[{index}]"
            if prop.type_id in (4, 5):
                cursor = _align(cursor, 2, frozen_start)
            elif prop.type_id in (6, 7, 8, 9, 11):
                cursor = _align(cursor, 4, frozen_start)
            elif prop.type_id == 10:
                cursor = _align(cursor, 8, frozen_start)

            if cursor < frozen_start or cursor + size > frozen_end:
                raise DataObjectError(f"{item} leaves the frozen object")

            if prop.type_id in _STRUCTS:
                value = struct.unpack_from(_STRUCTS[prop.type_id], data, cursor)[0]
                # Preserve exact display for browser-unsafe 64-bit values.
                values.append(str(value) if prop.type_id == 8 else value)
            elif prop.type_id == 11:
                mapped = offset_names.get(cursor - frozen_start)
                if mapped is None:
                    raise DataObjectError(
                        f"{item} has no minimal-name identity at frozen offset "
                        f"{cursor - frozen_start}"
                    )
                values.append(mapped.display)
            elif prop.type_id == 10:
                packed = _u64(data, cursor, f"{item} string pointer")
                signed = struct.unpack("<q", struct.pack("<Q", packed))[0]
                target = cursor + (signed >> 1)
                char_count = _i32(data, cursor + 8, f"{item} string length")
                char_max = _i32(data, cursor + 12, f"{item} string capacity")
                if char_count < 0 or char_max < char_count:
                    raise DataObjectError(f"{item} string header is invalid")
                if char_count == 0:
                    values.append("")
                else:
                    byte_count = char_count * 2
                    if target < frozen_start or target + byte_count > frozen_end:
                        raise DataObjectError(f"{item} string data leaves the frozen object")
                    raw = data[target:target + byte_count]
                    try:
                        values.append(raw[:-2].decode("utf-16-le"))
                    except UnicodeDecodeError as error:
                        raise DataObjectError(f"{item} string data is not valid UTF-16") from error
            else:
                raise DataObjectError(f"Unsupported array element type {type_name}")
            cursor += size
        return values

    @classmethod
    def _read_field(cls, data: bytes, cursor: int, frozen_start: int,
                    frozen_end: int, names: list[str],
                    offset_names: dict[int, FName],
                    prop: Property, what: str) -> tuple[Field, int]:
        type_name, kind, size, minimum, maximum = _TYPES[prop.type_id]

        if prop.is_array:
            cursor = _align(cursor, 8, frozen_start)
            _need(data, cursor, 16, what)
            count, capacity = struct.unpack_from("<ii", data, cursor + 8)
            if count < 0 or capacity < count or count > 1_000_000:
                raise DataObjectError(f"{what} array header is invalid")
            values = cls._read_array_elements(
                data, cursor, frozen_start, frozen_end, offset_names, prop, count, what)
            return Field(
                prop.name, prop.type_id, type_name, "array", values,
                cursor, 16, False,
                note=(
                    f"Read-only {type_name} array with {count} element(s). "
                    "Public Rebirth format evidence proves pointed element decoding, "
                    "but array writes remain disabled pending live acceptance."
                )
            ), cursor + 16

        if prop.type_id in (6, 7, 9):
            cursor = _align(cursor, 4, frozen_start)
        elif prop.type_id == 10:
            cursor = _align(cursor, 8, frozen_start)
        elif prop.type_id == 11:
            cursor = _align(cursor, 4, frozen_start)

        _need(data, cursor, size, what)
        if prop.type_id in _STRUCTS:
            value = struct.unpack_from(_STRUCTS[prop.type_id], data, cursor)[0]
            editable = prop.type_id != 8
            note = (
                "64-bit integers are read-only in the browser until exact integer controls are implemented."
                if prop.type_id == 8
                else "Fixed-width in-place edit; every other asset byte is preserved."
            )
        elif prop.type_id == 11:
            # Frozen NameProperty bytes are placeholders. Rebirth's minimal-name
            # map assigns the actual FName to this frozen-object offset.
            mapped = offset_names.get(cursor - frozen_start)
            value = mapped.display if mapped is not None else ""
            editable = False
            note = "Existing frozen FName is read-only; name-map edits are not implemented."
        elif prop.type_id == 10:
            packed = _u64(data, cursor, f"{what} string pointer")
            signed = struct.unpack("<q", struct.pack("<Q", packed))[0]
            target = cursor + (signed >> 1)
            count = _i32(data, cursor + 8, f"{what} string length")
            if count <= 0:
                value = ""
            else:
                _need(data, target, count * 2, f"{what} string data")
                raw = data[target:target + count * 2]
                try:
                    value = raw[:-2].decode("utf-16-le")
                except UnicodeDecodeError:
                    value = "<invalid UTF-16>"
            editable = False
            note = "String is read-only because changing its length rebuilds the frozen object."
        else:
            raise DataObjectError(f"Unsupported type id {prop.type_id}")

        return Field(
            prop.name, prop.type_id, type_name, kind, value, cursor, size,
            editable, minimum=minimum, maximum=maximum, note=note
        ), cursor + size

    def record(self, name_index: int, name_number: int = 0) -> Record:
        for record in self.records:
            if record.key.index == name_index and record.key.number == name_number:
                return record
        raise DataObjectError(
            f"No record with name index {name_index} and number {name_number}")

    def apply_edits(self, edits: list[dict]) -> int:
        changed = 0
        for edit in edits:
            if not isinstance(edit, dict):
                raise DataObjectError("Every edit must be an object")
            try:
                name_index = int(edit["nameIndex"])
                name_number = int(edit.get("nameNumber", 0))
                property_name = str(edit["property"])
            except (KeyError, TypeError, ValueError) as error:
                raise DataObjectError("Edit identity is incomplete") from error
            record = self.record(name_index, name_number)
            field = next((item for item in record.fields if item.name == property_name), None)
            if field is None:
                raise DataObjectError(f"{record.key.display} has no {property_name} field")
            if not field.editable or field.type_id not in _STRUCTS:
                raise DataObjectError(f"{property_name} is read-only in this integration")
            value = edit.get("value")
            if field.type_id == 1:
                if not isinstance(value, bool):
                    raise DataObjectError(f"{property_name} must be true or false")
            elif field.type_id == 9:
                if isinstance(value, bool):
                    raise DataObjectError(f"{property_name} must be a finite number")
                try:
                    value = float(value)
                except (TypeError, ValueError) as error:
                    raise DataObjectError(f"{property_name} must be a finite number") from error
                if not math.isfinite(value):
                    raise DataObjectError(f"{property_name} must be a finite number")
            else:
                if isinstance(value, bool):
                    raise DataObjectError(f"{property_name} must be an integer")
                try:
                    numeric = float(value)
                    if not math.isfinite(numeric) or not numeric.is_integer():
                        raise ValueError
                    value = int(numeric)
                except (TypeError, ValueError) as error:
                    raise DataObjectError(f"{property_name} must be an integer") from error
                if field.minimum is not None and value < field.minimum:
                    raise DataObjectError(f"{property_name} must be at least {field.minimum}")
                if field.maximum is not None and value > field.maximum:
                    raise DataObjectError(f"{property_name} must be at most {field.maximum}")
            encoded = struct.pack(_STRUCTS[field.type_id], value)
            before = bytes(self.bytes[field.offset:field.offset + field.size])
            if encoded != before:
                self.bytes[field.offset:field.offset + field.size] = encoded
                field.value = value
                changed += 1
        return changed

    def to_bytes(self) -> bytes:
        return bytes(self.bytes)

    def payload(self) -> dict:
        active = self.to_bytes()
        return {
            "format": "FF7R2 IoStore-state DataObject",
            "sourceSha256": self.source_sha256,
            "activeSha256": hashlib.sha256(active).hexdigest(),
            "records": [record.payload() for record in self.records],
            "recordCount": len(self.records),
            "preservation": "Fixed-width scalar byte patches only; unknown bytes are preserved.",
        }
