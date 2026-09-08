"""FF7 Remake DataObject .uasset/.uexp reader and same-size writer.

The format contract is intentionally narrow: it implements the DataObject table
shape used by FINAL FANTASY VII REMAKE INTERGRADE. Unknown bytes are never
rebuilt; editable values are patched in place in the .uexp payload.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
import struct
from typing import Any


PACKAGE_TAG = 0x9E2A83C1
MAX_STRING_BYTES = 16 * 1024 * 1024
MAX_NAMES = 1_000_000
MAX_PROPERTIES = 100_000
MAX_ENTRIES = 10_000_000
MAX_ARRAY_ELEMENTS = 10_000_000

BOOLEAN = 1
BYTE = 2
BOOLEAN_BYTE = 3
INT16 = 4  # Upstream calls this UINT16 but FF7R's existing editor reads/writes signed LE int16.
INT32 = 7
FLOAT = 9
STRING = 10
NAME = 11

TYPE_NAMES = {
    BOOLEAN: "BOOL",
    BYTE: "BYTE",
    BOOLEAN_BYTE: "BOOL",
    INT16: "INT16",
    INT32: "INT32",
    FLOAT: "FLOAT",
    STRING: "STRING",
    NAME: "ENUM",
}

BOUNDS = {
    BYTE: (0, 255),
    INT16: (-32768, 32767),
    INT32: (-2147483648, 2147483647),
}


class FormatError(ValueError):
    """Raised when a package is malformed or outside the proved FF7R table shape."""


class Reader:
    def __init__(self, data: bytes | bytearray, label: str):
        self.data = data
        self.label = label
        self.pos = 0

    def seek(self, offset: int) -> None:
        if offset < 0 or offset > len(self.data):
            raise FormatError(f"{self.label}: offset {offset} is outside the file")
        self.pos = offset

    def read(self, size: int) -> bytes:
        if size < 0 or self.pos + size > len(self.data):
            raise FormatError(f"{self.label}: unexpected end of file at 0x{self.pos:X}")
        value = bytes(self.data[self.pos:self.pos + size])
        self.pos += size
        return value

    def unpack(self, fmt: str):
        size = struct.calcsize(fmt)
        try:
            value = struct.unpack_from(fmt, self.data, self.pos)[0]
        except struct.error as error:
            raise FormatError(f"{self.label}: unexpected end of file at 0x{self.pos:X}") from error
        self.pos += size
        return value

    def byte(self) -> int:
        return self.unpack("<B")

    def int16(self) -> int:
        return self.unpack("<h")

    def int32(self) -> int:
        return self.unpack("<i")

    def uint32(self) -> int:
        return self.unpack("<I")

    def int64(self) -> int:
        return self.unpack("<q")

    def float32(self) -> float:
        return self.unpack("<f")

    def boolean(self) -> bool:
        return self.byte() != 0

    def fstring(self) -> str:
        length = self.int32()
        if length == 0:
            return ""
        if length > 0:
            if length > MAX_STRING_BYTES:
                raise FormatError(f"{self.label}: FString is implausibly large ({length} bytes)")
            raw = self.read(length)
            try:
                return raw.rstrip(b"\0").decode("utf-8")
            except UnicodeDecodeError as error:
                raise FormatError(f"{self.label}: invalid UTF-8 FString") from error
        chars = -length
        byte_length = chars * 2
        if byte_length > MAX_STRING_BYTES:
            raise FormatError(f"{self.label}: FString is implausibly large ({byte_length} bytes)")
        raw = self.read(byte_length)
        try:
            return raw[:-2].decode("utf-16-le") if raw.endswith(b"\0\0") else raw.decode("utf-16-le")
        except UnicodeDecodeError as error:
            raise FormatError(f"{self.label}: invalid UTF-16 FString") from error


@dataclass(frozen=True)
class Property:
    name: str
    type_code: int
    is_array: bool

    @property
    def editable(self) -> bool:
        return self.type_code != STRING

    def api(self) -> dict[str, Any]:
        minimum = maximum = None
        if self.type_code in BOUNDS:
            minimum, maximum = BOUNDS[self.type_code]
        elif self.type_code in (BOOLEAN, BOOLEAN_BYTE):
            minimum, maximum = 0, 1
        return {
            "name": self.name,
            "label": humanize(self.name.removesuffix("_Array")),
            "type": TYPE_NAMES.get(self.type_code, f"TYPE_{self.type_code}"),
            "typeCode": self.type_code,
            "array": self.is_array,
            "editable": self.editable,
            "min": minimum,
            "max": maximum,
        }


@dataclass(frozen=True)
class FieldOffset:
    offset: int
    length: int | None = None


@dataclass
class Entry:
    index: int
    tag: str
    values: dict[str, Any]
    offsets: dict[str, FieldOffset]


@dataclass(frozen=True)
class UAsset:
    names: tuple[str, ...]
    export_name: str
    serial_size: int
    serial_offset: int


def humanize(value: str) -> str:
    value = value.replace("_", " ")
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or "Value"


def sha256_bytes(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_fname(reader: Reader, names: tuple[str, ...] | list[str]) -> str:
    index = reader.int32()
    reader.read(4)  # FName number; FF7R tables use the base name for display/editing.
    if index < 0 or index >= len(names):
        raise FormatError(f"{reader.label}: FName index {index} is outside the name table")
    return names[index]


def parse_uasset(data: bytes, label: str = "uasset") -> UAsset:
    reader = Reader(data, label)
    if reader.uint32() != PACKAGE_TAG:
        raise FormatError(f"{label}: invalid Unreal package tag")
    legacy_version = reader.int32()
    if legacy_version != -4:
        reader.int32()  # legacy UE3 version
    version = reader.int32()
    licensee_version = reader.int32() & 0xFFFF
    file_version = version & 0xFFFF
    if licensee_version != 0 or file_version != 0:
        raise FormatError(
            f"{label}: unsupported package version {version} / licensee {licensee_version}"
        )
    if legacy_version <= -2:
        custom_versions = reader.int32()
        if custom_versions != 0:
            raise FormatError(f"{label}: custom version tables are not supported")

    reader.int32()  # headers size
    reader.fstring()  # package group
    reader.int32()  # package flags
    names_count = reader.int32()
    names_offset = reader.int32()
    reader.int32()  # gatherable text count
    reader.int32()  # gatherable text offset
    exports_count = reader.int32()
    exports_offset = reader.int32()
    if names_count < 0 or names_count > MAX_NAMES:
        raise FormatError(f"{label}: unreasonable name count {names_count}")
    if exports_count != 1:
        raise FormatError(f"{label}: expected one DataObject export, found {exports_count}")

    reader.seek(names_offset)
    names: list[str] = []
    for _ in range(names_count):
        names.append(reader.fstring())
        reader.read(4)  # name hash

    reader.seek(exports_offset)
    reader.int32()  # class index
    reader.int32()  # super index
    reader.int32()  # template index
    reader.int32()  # package index
    export_name = _read_fname(reader, names)
    reader.uint32()  # object flags
    serial_size = reader.int64()
    serial_offset = reader.int64()
    reader.boolean()
    reader.boolean()
    reader.boolean()
    reader.read(16)
    reader.int32()
    reader.boolean()
    reader.boolean()
    if serial_size < 0 or serial_offset < 0:
        raise FormatError(f"{label}: invalid export size/offset")
    return UAsset(tuple(names), export_name, serial_size, serial_offset)


class DataObjectPackage:
    """One FF7R DataObject pair with byte-precise editable offsets."""

    def __init__(self, uasset_path: Path, uexp_path: Path, *, asset: str = ""):
        self.uasset_path = Path(uasset_path)
        self.uexp_path = Path(uexp_path)
        self.asset = asset or self.uasset_path.with_suffix("").as_posix()
        self.uasset_bytes = self.uasset_path.read_bytes()
        self.uexp_bytes = bytearray(self.uexp_path.read_bytes())
        self.uasset = parse_uasset(self.uasset_bytes, self.uasset_path.name)
        self.properties, self.entries = self._parse_uexp()
        self.source_sha256 = sha256_bytes(self.uexp_bytes)

    @classmethod
    def from_bytes(cls, uasset: bytes, uexp: bytes, *, asset: str = "fixture") -> "DataObjectPackage":
        obj = cls.__new__(cls)
        obj.uasset_path = Path(f"{asset}.uasset")
        obj.uexp_path = Path(f"{asset}.uexp")
        obj.asset = asset
        obj.uasset_bytes = bytes(uasset)
        obj.uexp_bytes = bytearray(uexp)
        obj.uasset = parse_uasset(obj.uasset_bytes, obj.uasset_path.name)
        obj.properties, obj.entries = obj._parse_uexp()
        obj.source_sha256 = sha256_bytes(obj.uexp_bytes)
        return obj

    def _parse_uexp(self) -> tuple[list[Property], list[Entry]]:
        reader = Reader(self.uexp_bytes, self.uexp_path.name)
        reader.read(0x0A)
        entries_count = reader.int32()
        props_count = reader.int32()
        if entries_count < 0 or entries_count > MAX_ENTRIES:
            raise FormatError(f"{reader.label}: unreasonable entry count {entries_count}")
        if props_count < 0 or props_count > MAX_PROPERTIES:
            raise FormatError(f"{reader.label}: unreasonable property count {props_count}")
        properties: list[Property] = []
        for _ in range(props_count):
            name = _read_fname(reader, self.uasset.names)
            type_code = reader.byte()
            if type_code not in TYPE_NAMES:
                raise FormatError(f"{reader.label}: unsupported property type {type_code} ({name})")
            properties.append(Property(name, type_code, name.endswith("_Array")))

        entries: list[Entry] = []
        for index in range(entries_count):
            tag = _read_fname(reader, self.uasset.names)
            values: dict[str, Any] = {}
            offsets: dict[str, FieldOffset] = {}
            for prop in properties:
                offset = reader.pos
                if prop.is_array:
                    length = reader.int32()
                    if length < 0 or length > MAX_ARRAY_ELEMENTS:
                        raise FormatError(f"{reader.label}: invalid array length {length} for {prop.name}")
                    value = [self._read_value(reader, prop.type_code, array=True) for _ in range(length)]
                    offsets[prop.name] = FieldOffset(offset, length)
                else:
                    value = self._read_value(reader, prop.type_code, array=False)
                    offsets[prop.name] = FieldOffset(offset)
                values[prop.name] = value
            entries.append(Entry(index, tag, values, offsets))
        return properties, entries

    def _read_value(self, reader: Reader, type_code: int, *, array: bool):
        if type_code == BOOLEAN:
            return bool(reader.byte()) if array else bool(reader.int32())
        if type_code in (BYTE, BOOLEAN_BYTE):
            value = reader.byte()
            return bool(value) if type_code == BOOLEAN_BYTE else value
        if type_code == INT16:
            return reader.int16()
        if type_code == INT32:
            return reader.int32()
        if type_code == FLOAT:
            return reader.float32()
        if type_code == STRING:
            return reader.fstring()
        if type_code == NAME:
            return _read_fname(reader, self.uasset.names)
        raise FormatError(f"{reader.label}: unsupported property type {type_code}")

    def api_payload(self, *, source_sha256: str | None = None, using_project: bool = False) -> dict:
        return {
            "asset": self.asset,
            "sourceSha256": source_sha256 or self.source_sha256,
            "activeSha256": sha256_bytes(self.uexp_bytes),
            "usingProject": using_project,
            "exportName": self.uasset.export_name,
            "names": list(self.uasset.names),
            "properties": [prop.api() for prop in self.properties],
            "records": [
                {"id": entry.index, "tag": entry.tag, "values": entry.values}
                for entry in self.entries
            ],
        }

    def _property(self, name: str) -> Property:
        for prop in self.properties:
            if prop.name == name:
                return prop
        raise ValueError(f"Unknown property: {name}")

    def apply_edits(self, edits: list[dict[str, Any]]) -> None:
        for edit in edits:
            if not isinstance(edit, dict):
                raise TypeError("Each edit must be an object")
            entry_index = int(edit.get("entry", -1))
            if entry_index < 0 or entry_index >= len(self.entries):
                raise IndexError(f"Entry index out of range: {entry_index}")
            prop_name = str(edit.get("property", ""))
            prop = self._property(prop_name)
            if not prop.editable:
                raise ValueError(f"{prop_name} is read-only because changing FString size is unsupported")
            entry = self.entries[entry_index]
            field = entry.offsets[prop_name]
            value = edit.get("value")
            if prop.is_array:
                if "index" not in edit:
                    raise ValueError(f"{prop_name} requires an array index")
                array_index = int(edit["index"])
                if field.length is None or array_index < 0 or array_index >= field.length:
                    raise IndexError(f"Array index out of range for {prop_name}: {array_index}")
                offset = field.offset + 4 + array_index * self._width(prop.type_code, array=True)
                self._write_value(offset, prop.type_code, value, array=True)
                entry.values[prop_name][array_index] = self._normalize(prop.type_code, value)
            else:
                if "index" in edit and edit["index"] is not None:
                    raise ValueError(f"{prop_name} is not an array")
                self._write_value(field.offset, prop.type_code, value, array=False)
                entry.values[prop_name] = self._normalize(prop.type_code, value)

    @staticmethod
    def _width(type_code: int, *, array: bool) -> int:
        if type_code == BOOLEAN:
            return 1 if array else 4
        if type_code in (BYTE, BOOLEAN_BYTE):
            return 1
        if type_code == INT16:
            return 2
        if type_code in (INT32, FLOAT):
            return 4
        if type_code == NAME:
            return 8
        raise ValueError("Variable-width string properties cannot be patched")

    def _normalize(self, type_code: int, value: Any):
        if type_code in (BOOLEAN, BOOLEAN_BYTE):
            if isinstance(value, str):
                folded = value.strip().casefold()
                if folded in {"true", "1"}:
                    return True
                if folded in {"false", "0"}:
                    return False
                raise ValueError(f"Expected a boolean, got {value!r}")
            if value in (0, 1, False, True):
                return bool(value)
            raise ValueError(f"Expected a boolean, got {value!r}")
        if type_code in BOUNDS:
            if isinstance(value, bool):
                raise ValueError("Expected an integer, got a boolean")
            number = int(value)
            if str(number) != str(value).strip() and not isinstance(value, int):
                try:
                    if float(value) != number:
                        raise ValueError
                except (TypeError, ValueError):
                    raise ValueError(f"Expected an integer, got {value!r}") from None
            minimum, maximum = BOUNDS[type_code]
            if number < minimum or number > maximum:
                raise ValueError(f"Value {number} is outside {minimum}..{maximum}")
            return number
        if type_code == FLOAT:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError("Float must be finite")
            try:
                packed = struct.pack("<f", number)
            except (OverflowError, struct.error) as error:
                raise ValueError("Float is outside the 32-bit range") from error
            return struct.unpack("<f", packed)[0]
        if type_code == NAME:
            if not isinstance(value, str) or value not in self.uasset.names:
                raise ValueError(f"FName must already exist in {self.uasset_path.name}: {value!r}")
            return value
        raise ValueError(f"Property type {type_code} cannot be edited")

    def _write_value(self, offset: int, type_code: int, value: Any, *, array: bool) -> None:
        value = self._normalize(type_code, value)
        try:
            if type_code == BOOLEAN:
                struct.pack_into("<B" if array else "<i", self.uexp_bytes, offset, int(value))
            elif type_code == BOOLEAN_BYTE:
                struct.pack_into("<B", self.uexp_bytes, offset, int(value))
            elif type_code == BYTE:
                struct.pack_into("<B", self.uexp_bytes, offset, value)
            elif type_code == INT16:
                struct.pack_into("<h", self.uexp_bytes, offset, value)
            elif type_code == INT32:
                struct.pack_into("<i", self.uexp_bytes, offset, value)
            elif type_code == FLOAT:
                struct.pack_into("<f", self.uexp_bytes, offset, value)
            elif type_code == NAME:
                index = self.uasset.names.index(value)
                struct.pack_into("<iI", self.uexp_bytes, offset, index, 0)
            else:
                raise ValueError(f"Property type {type_code} cannot be edited")
        except struct.error as error:
            raise FormatError(f"Edit for type {type_code} writes outside {self.uexp_path.name}") from error

    def write_uexp(self, target: Path) -> Path:
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = bytes(self.uexp_bytes)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(target)
        if target.stat().st_size != len(data):
            raise OSError(f"Short write: {target}")
        return target
