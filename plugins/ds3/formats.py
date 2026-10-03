"""Dark Souls III regulation/BND4/PARAM support.

Known fixed-width PARAM cells are patched in place. Row creation relocates
directory pointers and grows uncompressed binder members while retaining
existing payloads and unknown bytes. Compressed members are rejected.

The installed regulation, Game/Data0.bdt, is a 16-byte IV followed by
AES-256-CBC ciphertext, and the ciphertext holds a DCX container with one DFLT
(zlib) block. Measured on App Ver. 1.15.2 / Regulation 1.35 on 2026-09-25: the
container inflates to one 13,445,834-byte BND4 whose header carries the version
string 0135. SoulsFormats writes the same shape for its DarkSouls3 DCX type
DCX_DFLT_10000_44_9, and it pads with PKCS#7. This module reads both paddings
and writes that shape, so an export has the layout the installed game ships.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
import re
import struct
import zlib
from pathlib import Path
import xml.etree.ElementTree as ET
from core.numeric_values import integer_value

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


DS3_REGULATION_KEY = b"ds3#jn/8_7(rsY9pg55GFN7VFL#+3n/)"
DCX_MAGIC = b"DCX\x00"
DCX_FORMAT = b"DFLT"
# The eight characters the installed Regulation 1.35 archive stores at offset
# 0x18 of its BND4 header. The editor shows 1.35 to a reader and keeps the
# stored text here, so a mismatched build is reported as the file spells it.
REGULATION_VERSION = "01350000"
# The value the regulation stores at PARAM offset 0x08 is not the paramdef
# version the pinned XML files declare: those declare 201 for every DS3 table.
# Each table stores its own value instead, and these are the values measured in
# Game/Data0.bdt of Regulation 1.35. The check stays strict, because a different
# value means the row layout this editor patches was not audited.
REGULATION_HEADER_VERSIONS = {
    "EquipParamWeapon": 3,
    "EquipParamProtector": 4,
    "EquipParamAccessory": 1,
    "Magic": 3,
    "SpEffectParam": 4,
    "NpcParam": 9,
}
TARGET_TABLES = (
    "EquipParamWeapon",
    "EquipParamProtector",
    "EquipParamAccessory",
    "Magic",
    "SpEffectParam",
    "NpcParam",
)


class DS3FormatError(ValueError):
    """Input is unsupported or inconsistent with the audited DS3 formats."""


def _reverse_bits(value: int) -> int:
    return int(f"{value:08b}"[::-1], 2)


def dcx_payload(data: bytes) -> bytes:
    """Return the bytes of the DFLT (zlib) block inside a DCX container.

    Only the single-block DFLT shape that DarkSouls3 uses is accepted. The
    compressed length comes from the container header, so the padding a writer
    added after the block is ignored instead of being guessed at.
    """
    if len(data) < 0x4C or data[:4] != DCX_MAGIC:
        raise DS3FormatError("Expected a DCX container")
    if data[0x18:0x1C] != b"DCS\x00" or data[0x24:0x28] != b"DCP\x00":
        raise DS3FormatError("DCX container has no DCS/DCP section")
    if data[0x28:0x2C] != DCX_FORMAT:
        raise DS3FormatError(f"Unsupported DCX compression {data[0x28:0x2C]!r}")
    if data[0x44:0x48] != b"DCA\x00":
        raise DS3FormatError("DCX container has no DCA block")
    data_offset = struct.unpack_from(">I", data, 0x14)[0]
    compressed_size = struct.unpack_from(">I", data, 0x20)[0]
    if data_offset != 0x4C:
        raise DS3FormatError(f"Unexpected DCX block offset 0x{data_offset:X}")
    if compressed_size < 2 or data_offset + compressed_size > len(data):
        raise DS3FormatError("DCX block length is outside the container")
    try:
        return zlib.decompress(data[data_offset:data_offset + compressed_size])
    except zlib.error as error:
        raise DS3FormatError("DCX block is not a valid zlib stream") from error


def dcx_container(plain: bytes) -> bytes:
    """Wrap payload bytes in the DarkSouls3 DCX shape (DFLT, level 9)."""
    compressed = zlib.compress(plain, 9)
    if compressed[:2] != b"\x78\xda":
        raise DS3FormatError("The zlib block did not use the expected 0x78DA header")
    header = bytearray(0x4C)
    header[0x00:0x04] = DCX_MAGIC
    struct.pack_into(">I", header, 0x04, 0x10000)
    struct.pack_into(">I", header, 0x08, 0x18)
    struct.pack_into(">I", header, 0x0C, 0x24)
    struct.pack_into(">I", header, 0x10, 0x44)
    struct.pack_into(">I", header, 0x14, 0x4C)
    header[0x18:0x1C] = b"DCS\x00"
    struct.pack_into(">I", header, 0x1C, len(plain))
    struct.pack_into(">I", header, 0x20, len(compressed))
    header[0x24:0x28] = b"DCP\x00"
    header[0x28:0x2C] = DCX_FORMAT
    struct.pack_into(">I", header, 0x2C, 0x20)
    header[0x30] = 9
    struct.pack_into(">I", header, 0x40, 0x00010100)
    header[0x44:0x48] = b"DCA\x00"
    struct.pack_into(">I", header, 0x48, 8)
    return bytes(header) + compressed


def _strip_writer_padding(padded: bytes) -> bytes:
    """Remove PKCS#7 padding when it is present and valid.

    The installed game build pads with zero bytes, and SoulsFormats pads with
    PKCS#7. Removing PKCS#7 here keeps repeated safe exports from accumulating
    padding. Zero padding is left alone: a BND4 reader ignores trailing bytes,
    and DCX payloads never reach this function.
    """
    if padded and 1 <= padded[-1] <= 16 and padded.endswith(bytes([padded[-1]]) * padded[-1]):
        return padded[:-padded[-1]]
    return padded


def decrypt_regulation(data: bytes) -> tuple[bytes, bool]:
    """Return BND4 bytes and whether the input was encrypted.

    Raw BND4 is accepted for tooling. Everything else is IV || AES-256-CBC
    ciphertext, and the plaintext is either a DCX container that holds the BND4
    or the BND4 itself.
    """
    if data.startswith(b"BND4"):
        return data, False
    if len(data) < 32 or (len(data) - 16) % 16:
        raise DS3FormatError("DS3 regulation is neither BND4 nor IV + AES-CBC ciphertext")
    iv, ciphertext = data[:16], data[16:]
    decryptor = Cipher(algorithms.AES(DS3_REGULATION_KEY), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    plain = dcx_payload(padded) if padded.startswith(DCX_MAGIC) else _strip_writer_padding(padded)
    if not plain.startswith(b"BND4"):
        raise DS3FormatError("DS3 regulation decrypted, but the payload is not BND4")
    return plain, True


def encrypt_regulation(plain: bytes, iv: bytes | None = None) -> bytes:
    """Return the installed game's shape: IV || AES-CBC of a DCX-wrapped BND4."""
    if not plain.startswith(b"BND4"):
        raise DS3FormatError("Only audited BND4 payloads can be encrypted as DS3 regulation data")
    iv = os.urandom(16) if iv is None else iv
    if len(iv) != 16:
        raise DS3FormatError("AES-CBC IV must be 16 bytes")
    padder = PKCS7(128).padder()
    padded = padder.update(dcx_container(plain)) + padder.finalize()
    encryptor = Cipher(algorithms.AES(DS3_REGULATION_KEY), modes.CBC(iv)).encryptor()
    return iv + encryptor.update(padded) + encryptor.finalize()


@dataclass(frozen=True)
class BinderEntry:
    index: int
    name: str
    file_id: int | None
    data_offset: int
    size: int
    uncompressed_size: int | None
    compressed: bool


class BND4View:
    """Strict locator for uncompressed BND4 members; does not reserialize."""

    FORMAT_IDS = 0x02
    FORMAT_NAMES1 = 0x04
    FORMAT_NAMES2 = 0x08
    FORMAT_LONG_OFFSETS = 0x10
    FORMAT_COMPRESSION = 0x20

    def __init__(self, data: bytes):
        if len(data) < 0x40 or data[:4] != b"BND4":
            raise DS3FormatError("Expected a BND4 archive")
        self.data = data
        self.big_endian = bool(data[9])
        self.bit_big_endian = not bool(data[10])
        self.endian = ">" if self.big_endian else "<"
        self.file_count = self._unpack("i", 0x0C)
        header_size = self._unpack("q", 0x10)
        if header_size != 0x40:
            raise DS3FormatError(f"Unsupported BND4 header size 0x{header_size:X}")
        self.file_header_size = self._unpack("q", 0x20)
        self.unicode = bool(data[0x30])
        raw_format = data[0x31]
        reverse = self.bit_big_endian or ((raw_format & 1) and not (raw_format & 0x80))
        self.format = raw_format if reverse else _reverse_bits(raw_format)
        expected = 0x10
        expected += 8 if self.format & self.FORMAT_LONG_OFFSETS else 4
        expected += 8 if self.format & self.FORMAT_COMPRESSION else 0
        expected += 4 if self.format & self.FORMAT_IDS else 0
        expected += 4 if self.format & (self.FORMAT_NAMES1 | self.FORMAT_NAMES2) else 0
        expected += 8 if self.format == self.FORMAT_NAMES1 else 0
        if self.file_header_size != expected:
            raise DS3FormatError(
                f"BND4 file header is 0x{self.file_header_size:X}; audited format expects 0x{expected:X}"
            )
        if self.file_count < 0 or 0x40 + self.file_count * self.file_header_size > len(data):
            raise DS3FormatError("BND4 file table is outside the archive")
        self.entries = self._read_entries()

    def _unpack(self, code: str, offset: int):
        return struct.unpack_from(self.endian + code, self.data, offset)[0]

    def _read_string(self, offset: int) -> str:
        if not 0 <= offset < len(self.data):
            raise DS3FormatError("BND4 filename offset is outside the archive")
        if self.unicode:
            end = offset
            while end + 1 < len(self.data) and self.data[end:end+2] != b"\0\0":
                end += 2
            if end + 1 >= len(self.data):
                raise DS3FormatError("Unterminated UTF-16 BND4 filename")
            return self.data[offset:end].decode("utf-16-be" if self.big_endian else "utf-16-le", errors="strict")
        end = self.data.find(b"\0", offset)
        if end < 0:
            raise DS3FormatError("Unterminated BND4 filename")
        return self.data[offset:end].decode("shift_jis", errors="replace")

    def _read_entries(self) -> list[BinderEntry]:
        result = []
        for index in range(self.file_count):
            pos = 0x40 + index * self.file_header_size
            raw_flags = self.data[pos]
            flags = raw_flags if self.bit_big_endian else _reverse_bits(raw_flags)
            compressed = bool(flags & 1)
            pos += 8
            size = self._unpack("q", pos); pos += 8
            uncompressed_size = None
            if self.format & self.FORMAT_COMPRESSION:
                uncompressed_size = self._unpack("q", pos); pos += 8
            if self.format & self.FORMAT_LONG_OFFSETS:
                data_offset = self._unpack("q", pos); pos += 8
            else:
                data_offset = self._unpack("I", pos); pos += 4
            file_id = None
            if self.format & self.FORMAT_IDS:
                file_id = self._unpack("i", pos); pos += 4
            name = ""
            if self.format & (self.FORMAT_NAMES1 | self.FORMAT_NAMES2):
                name_offset = self._unpack("I", pos); pos += 4
                name = self._read_string(name_offset)
            if size < 0 or data_offset < 0 or data_offset + size > len(self.data):
                raise DS3FormatError(f"BND4 member {index} points outside the archive")
            result.append(BinderEntry(index, name, file_id, data_offset, size, uncompressed_size, compressed))
        return result

    def find_param(self, stem: str) -> BinderEntry:
        target = stem.casefold() + ".param"
        matches = [entry for entry in self.entries if entry.name.replace("\\", "/").split("/")[-1].casefold() == target]
        if len(matches) != 1:
            raise DS3FormatError(f"Expected one {stem}.param in regulation archive; found {len(matches)}")
        entry = matches[0]
        if entry.compressed:
            raise DS3FormatError(
                f"{stem}.param is compressed inside BND4; this byte-preserving editor intentionally refuses archive reconstruction"
            )
        return entry

    @property
    def version_string(self) -> str:
        """The build string the archive header carries, for example 01350000.

        The installed Regulation 1.35 file stores the eight characters
        "01350000" at this offset, so the value is reported exactly as stored.
        """
        return self.data[0x18:0x20].split(b"\x00", 1)[0].decode("ascii", errors="replace")

    def member_bytes(self, entry: BinderEntry) -> bytes:
        return self.data[entry.data_offset:entry.data_offset + entry.size]

    def patch_member(self, entry: BinderEntry, replacement: bytes) -> bytes:
        if entry.compressed:
            raise DS3FormatError("Compressed BND4 members cannot be patched in place")
        if len(replacement) != entry.size:
            raise DS3FormatError("In-place BND4 patch changed member size")
        result = bytearray(self.data)
        result[entry.data_offset:entry.data_offset + entry.size] = replacement
        return bytes(result)


    def grow_member(self, entry: BinderEntry, replacement: bytes) -> bytes:
        """Grow one uncompressed member, retaining other members and alignment."""
        if entry.compressed or len(replacement) < entry.size:
            raise DS3FormatError("Only uncompressed member growth is supported")
        end = entry.data_offset + entry.size
        directory_end = 0x40 + self.file_count * self.file_header_size
        first_data = min(item.data_offset for item in self.entries)
        if directory_end > first_data or any(self._unpack('q', pos) > first_data for pos in (0x28, 0x38)):
            raise DS3FormatError("BND4 metadata must precede member data before resizing")
        for other in self.entries:
            if other.index != entry.index and other.data_offset < end and other.data_offset + other.size > entry.data_offset:
                raise DS3FormatError("Overlapping BND4 members cannot be resized")
        growth = (len(replacement) - entry.size + 15) // 16 * 16
        padding = entry.size + growth - len(replacement)
        result = bytearray(self.data[:entry.data_offset] + replacement + bytes(padding) + self.data[end:])
        offset_field = 16 + (8 if self.format & self.FORMAT_COMPRESSION else 0)
        offset_code = 'q' if self.format & self.FORMAT_LONG_OFFSETS else 'I'
        for item in self.entries:
            pos = 0x40 + item.index * self.file_header_size
            if item.index == entry.index:
                struct.pack_into(self.endian+'q', result, pos+8, len(replacement))
                if self.format & self.FORMAT_COMPRESSION:
                    struct.pack_into(self.endian+'q', result, pos+16, len(replacement))
            elif item.data_offset >= end:
                struct.pack_into(self.endian+offset_code, result, pos+offset_field, item.data_offset+growth)
        return bytes(result)


@dataclass(frozen=True)
class ParamRow:
    row_id: int
    name: str | None
    data_offset: int


class ParamView:
    """PARAM row locator with real row IDs/names and fixed-width row data."""
    def __init__(self, data: bytes):
        if len(data) < 0x30:
            raise DS3FormatError("PARAM is too small")
        self.data = data
        marker = data[0x2C]
        if marker not in (0, 0xFF):
            raise DS3FormatError("PARAM endian marker is invalid")
        self.big_endian = marker == 0xFF
        self.endian = ">" if self.big_endian else "<"
        self.format2d = data[0x2D]
        self.format2e = data[0x2E]
        self.paramdef_format_version = data[0x2F]
        self.strings_offset = self._unpack("I", 0)
        # Offset 0x08 holds a per-table value of the installed regulation. It is
        # not the pinned paramdef version: every pinned DS3 XML declares 201,
        # and the installed Regulation 1.35 file stores 1 to 9 depending on the
        # table. See REGULATION_HEADER_VERSIONS for the measured values.
        self.header_version = self._unpack("h", 8)
        self.row_count = self._unpack("H", 10)
        if self.format2d & 0x80:
            type_offset = self._unpack("q", 16)
            self.param_type = self._ascii_z(type_offset)
            header_end = 48
        else:
            self.param_type = data[12:44].split(b"\0", 1)[0].decode("ascii", errors="strict")
            header_end = 48
        if (self.format2d & 1 and self.format2d & 2) or (self.format2d & 4):
            header_end = 64
        self.long_offsets = bool(self.format2d & 4)
        row_header_size = 24 if self.long_offsets else 12
        if header_end + row_header_size * self.row_count > len(data):
            raise DS3FormatError("PARAM row headers are outside the file")
        self.rows = []
        for i in range(self.row_count):
            pos = header_end + i * row_header_size
            row_id = self._unpack("i", pos)
            if self.long_offsets:
                data_offset = self._unpack("q", pos + 8)
                name_offset = self._unpack("q", pos + 16)
            else:
                data_offset = self._unpack("I", pos + 4)
                name_offset = self._unpack("I", pos + 8)
            if not 0 <= data_offset < len(data):
                raise DS3FormatError(f"PARAM row {row_id} data offset is outside the file")
            name = self._row_name(name_offset) if name_offset else None
            self.rows.append(ParamRow(row_id, name, data_offset))
        offsets = sorted({r.data_offset for r in self.rows})
        sizes = [b-a for a,b in zip(offsets, offsets[1:]) if b > a]
        self.detected_row_size = min(sizes) if sizes else None

    def _unpack(self, code: str, offset: int):
        return struct.unpack_from(self.endian + code, self.data, offset)[0]

    def _ascii_z(self, offset: int) -> str:
        if not 0 <= offset < len(self.data):
            raise DS3FormatError("PARAM type offset is outside the file")
        end = self.data.find(b"\0", offset)
        if end < 0:
            raise DS3FormatError("PARAM type is unterminated")
        return self.data[offset:end].decode("ascii", errors="strict")

    def _row_name(self, offset: int) -> str:
        if not 0 <= offset < len(self.data):
            raise DS3FormatError("PARAM row name is outside the file")
        if self.format2e & 1:
            end = offset
            while end + 1 < len(self.data) and self.data[end:end+2] != b"\0\0": end += 2
            return self.data[offset:end].decode("utf-16-be" if self.big_endian else "utf-16-le", errors="replace")
        end = self.data.find(b"\0", offset)
        return self.data[offset:(len(self.data) if end < 0 else end)].decode("shift_jis", errors="replace")

    def row(self, row_id: int) -> ParamRow:
        row_id = integer_value(row_id, "PARAM row ID", DS3FormatError)
        matches = [row for row in self.rows if row.row_id == row_id]
        if len(matches) != 1:
            raise DS3FormatError(f"Expected one row ID {row_id}; found {len(matches)}")
        return matches[0]

    def copy_row(self, source_id: int, new_id: int, name: str, row_size: int) -> bytes:
        """Extend the directory and data region, preserving existing payloads."""
        if type(new_id) is not int or not -(2**31) <= new_id < 2**31:
            raise DS3FormatError("A PARAM row ID must be a signed 32-bit integer")
        if any(row.row_id == new_id for row in self.rows):
            raise DS3FormatError("That PARAM row ID already exists")
        if self.row_count == 65535:
            raise DS3FormatError("PARAM already has the maximum number of rows")
        if not isinstance(name, str) or '\0' in name or len(name) > 1024:
            raise DS3FormatError("Invalid PARAM row name")
        source = self.row(source_id)
        extended = bool(self.format2d & 4 or self.format2d & 3 == 3)
        header_end = 64 if extended else 48
        stride = 24 if self.long_offsets else 12
        directory_end = header_end + self.row_count * stride
        strings = self.strings_offset
        if row_size <= 0 or not directory_end <= strings <= len(self.data):
            raise DS3FormatError("PARAM data/string boundaries are inconsistent")
        if any(not directory_end <= row.data_offset or row.data_offset + row_size > strings for row in self.rows):
            raise DS3FormatError("PARAM row overlaps its directory or strings")
        encoding = ('utf-16-be' if self.big_endian else 'utf-16-le') if self.format2e & 1 else 'shift_jis'
        try:
            encoded_name = name.encode(encoding) + (b'\0\0' if self.format2e & 1 else b'\0')
        except UnicodeEncodeError as error:
            raise DS3FormatError("Row name cannot be represented in this PARAM encoding") from error
        payload = self.data[source.data_offset:source.data_offset + row_size]
        result = bytearray(self.data[:directory_end] + bytes(stride)
                           + self.data[directory_end:strings] + payload + self.data[strings:])
        name_offset = len(result)
        result.extend(encoded_name)
        def relocated(offset):
            return offset + (stride if offset >= directory_end else 0) + (row_size if offset >= strings else 0)
        struct.pack_into(self.endian + 'H', result, 10, self.row_count + 1)
        struct.pack_into(self.endian + 'I', result, 0, strings + stride + row_size)
        data_code, data_position = ('q', 48) if self.long_offsets else ('I', 48) if extended else ('H', 4)
        data_start = self._unpack(data_code, data_position)
        struct.pack_into(self.endian + data_code, result, data_position, relocated(data_start))
        if self.format2d & 0x80:
            struct.pack_into(self.endian + 'q', result, 16, relocated(self._unpack('q', 16)))
        code = 'q' if self.long_offsets else 'I'
        for index in range(self.row_count):
            pos = header_end + index * stride + (8 if self.long_offsets else 4)
            for offset_position in (pos, pos + (8 if self.long_offsets else 4)):
                offset = self._unpack(code, offset_position)
                if offset:
                    struct.pack_into(self.endian + code, result, offset_position, relocated(offset))
        struct.pack_into(self.endian + 'i', result, directory_end, new_id)
        pos = directory_end + (8 if self.long_offsets else 4)
        struct.pack_into(self.endian + code, result, pos, strings + stride)
        struct.pack_into(self.endian + code, result, pos + (8 if self.long_offsets else 4), name_offset)
        return bytes(result)

_TYPE_SIZE = {"s8":1,"u8":1,"dummy8":1,"s16":2,"u16":2,"s32":4,"u32":4,"b32":4,"f32":4,"angle32":4,"f64":8}
_INT_LIMITS = {
    "s8":(-128,127), "u8":(0,255), "s16":(-32768,32767), "u16":(0,65535),
    "s32":(-2147483648,2147483647), "u32":(0,4294967295), "b32":(-2147483648,2147483647),
}
_FLOAT_LIMITS = {
    "f32": (-3.4028234663852886e38, 3.4028234663852886e38),
    "angle32": (-3.4028234663852886e38, 3.4028234663852886e38),
    "f64": (-1.7976931348623157e308, 1.7976931348623157e308),
}


@dataclass(frozen=True)
class FieldSpec:
    key: str
    dtype: str
    offset: int
    array_length: int = 1
    bit_offset: int | None = None
    bit_size: int | None = None
    label: str = ""
    description: str = ""
    group: str = "Other"
    is_bool: bool = False
    enum: str | None = None
    reference: str | None = None
    padding: bool = False

    @property
    def editable(self):
        return (not self.padding and self.array_length == 1
                and not re.match(r"^(?:unk(?:nown)?)(?:\d|[ _]|$)", self.key, re.IGNORECASE))

    @property
    def minimum(self):
        if self.bit_size is not None:
            if self.dtype.startswith("s"):
                return -(1 << (self.bit_size - 1))
            return 0
        return _INT_LIMITS.get(self.dtype, _FLOAT_LIMITS.get(self.dtype, (None, None)))[0]

    @property
    def maximum(self):
        if self.bit_size is not None:
            if self.dtype.startswith("s"):
                return (1 << (self.bit_size - 1)) - 1
            return (1 << self.bit_size) - 1
        return _INT_LIMITS.get(self.dtype, _FLOAT_LIMITS.get(self.dtype, (None, None)))[1]


@dataclass(frozen=True)
class ParamSchema:
    table: str
    param_type: str
    data_version: int
    row_size: int
    description: str
    fields: tuple[FieldSpec, ...]
    enums: dict[str, dict[str, str]]
    row_names: dict[int, str]

    def field(self, key: str) -> FieldSpec:
        for field in self.fields:
            if field.key == key:
                return field
        raise DS3FormatError(f"Unknown field {self.table}.{key}")


_DEF_RE = re.compile(r"^(?P<type>\w+)\s+(?P<name>[^=\s]+)(?:\s*=.*)?$")
_NAME_RE = re.compile(r"^(?P<name>[^\[:]+)(?:\[(?P<array>\d+)\])?(?::(?P<bits>\d+))?$")


def load_schema(root: Path, table: str) -> ParamSchema:
    if table not in TARGET_TABLES:
        raise DS3FormatError(f"Unsupported DS3 table: {table}")
    def_root = ET.parse(root / "defs" / f"{table}.xml").getroot()
    param_type = (def_root.findtext("ParamType") or "").strip()
    data_version = int((def_root.findtext("Version") or "0").strip())
    meta_root = ET.parse(root / "meta" / f"{table}.xml").getroot()
    meta_field = meta_root.find("Field")
    meta_nodes = {node.tag: node.attrib for node in ([] if meta_field is None else list(meta_field))}
    layout = json.loads((root / "layouts" / f"{table}.json").read_text("utf-8-sig"))
    groups = {}
    for group in layout.get("Groups", []):
        names = group.get("Names", [])
        english = next(
            (entry.get("Name") for entry in names
             if isinstance(entry, dict) and entry.get("Language") == "English"),
            None,
        )
        name = str(english or group.get("Name") or group.get("Key") or "Other")
        if name.upper() == "TODO":
            name = str(group.get("Key") or "Other")
        for key in group.get("Fields", []):
            groups[str(key)] = name
    ann_path = root / "annotations" / f"{param_type}.json"
    if not ann_path.is_file():
        raise DS3FormatError(f"Missing pinned annotation metadata for {table}: {ann_path.name}")
    annotations = json.loads(ann_path.read_text("utf-8-sig"))
    ann_fields = {str(item.get("Field")): item for item in annotations.get("Fields", [])}
    description = str(annotations.get("Description") or table)
    enum_cache: dict[str, dict[str, str]] = {}
    row_names_path = root / "row_names" / f"{table}.json"
    if not row_names_path.is_file():
        raise DS3FormatError(f"Missing pinned row-name metadata for {table}: {row_names_path.name}")
    row_names: dict[int, str] = {}
    raw_names = json.loads(row_names_path.read_text("utf-8-sig"))
    for entry in raw_names.get("Entries", []):
        if not isinstance(entry, dict) or "ID" not in entry:
            continue
        names = [str(value).strip() for value in entry.get("Entries", []) if str(value).strip()]
        if names:
            row_names[int(entry["ID"])] = names[0]
    if not row_names:
        raise DS3FormatError(f"Pinned row-name metadata for {table} has no usable entries")

    fields=[]; offset=0; bit_limit=None; bit_offset=0; bit_storage_offset=0
    for node in def_root.findall(".//Fields/Field"):
        definition = (node.get("Def") or "").strip()
        m=_DEF_RE.match(definition)
        if not m: raise DS3FormatError(f"Unsupported PARAMDEF field declaration: {definition}")
        dtype=m.group("type"); raw_name=m.group("name")
        nm=_NAME_RE.match(raw_name)
        if dtype not in _TYPE_SIZE or not nm:
            raise DS3FormatError(f"Unsupported PARAMDEF field type/name: {definition}")
        key=nm.group("name"); array_len=int(nm.group("array") or "1"); bits=nm.group("bits"); bit_size=int(bits) if bits else None
        storage_bits=_TYPE_SIZE[dtype]*8
        if bit_size is None:
            bit_limit=None; bit_offset=0
            field_offset=offset
            offset += _TYPE_SIZE[dtype] * array_len
        else:
            if array_len != 1:
                raise DS3FormatError(f"Bitfield arrays are unsupported: {definition}")
            if bit_size <= 0 or bit_size > storage_bits:
                raise DS3FormatError(f"Invalid bitfield width: {definition}")
            # PARAM packs adjacent bitfields by storage width; signedness/type
            # affects interpretation, not whether a new storage word begins.
            if bit_limit != storage_bits or bit_offset + bit_size > storage_bits:
                bit_limit=storage_bits; bit_offset=0; bit_storage_offset=offset
                offset += _TYPE_SIZE[dtype]
            field_offset=bit_storage_offset
        attrs=meta_nodes.get(key, {})
        ann=ann_fields.get(key, {})
        enum_name=attrs.get("Enum")
        if enum_name and enum_name not in enum_cache:
            enum_path=root / "enums" / f"{enum_name}.json"
            if not enum_path.is_file():
                raise DS3FormatError(f"Missing pinned enum metadata for {table}.{key}: {enum_name}")
            raw=json.loads(enum_path.read_text("utf-8-sig"))
            if isinstance(raw, dict):
                values=raw.get("Values", raw.get("values"))
                if isinstance(values, dict):
                    enum_cache[enum_name]={str(k):str(v) for k,v in values.items()}
                elif isinstance(values, list):
                    enum_cache[enum_name]={str(i.get("Value")):str(i.get("Name")) for i in values if isinstance(i,dict)}
                elif isinstance(raw.get("Options"), list):
                    options={}
                    for item in raw["Options"]:
                        if not isinstance(item,dict) or "Key" not in item:
                            continue
                        english=next((n.get("Text") for n in item.get("Names",[]) if isinstance(n,dict) and n.get("Language")=="English"),None)
                        options[str(item["Key"])]=str(english or item["Key"])
                    enum_cache[enum_name]=options
            if not enum_cache.get(enum_name):
                raise DS3FormatError(f"Pinned enum metadata {enum_name} has no usable options")
        fields.append(FieldSpec(
            key=key,dtype=dtype,offset=field_offset,array_length=array_len,
            bit_offset=(bit_offset if bit_size is not None else None),bit_size=bit_size,
            label=str(ann.get("Name") or key),description=str(ann.get("Description") or ""),
            group=groups.get(key,"Other"),is_bool="IsBool" in attrs,
            enum=enum_name,
            reference=attrs.get("Refs"),padding=(dtype=="dummy8" or "Padding" in attrs or key.lower().startswith("pad")),
        ))
        if bit_size is not None: bit_offset += bit_size
    return ParamSchema(
        table, param_type, data_version, offset, description,
        tuple(fields), enum_cache, row_names,
    )


def _read_int(data: bytes, field: FieldSpec, endian: str):
    signed = field.dtype.startswith("s") or field.dtype == "b32"
    size = _TYPE_SIZE[field.dtype]
    value = int.from_bytes(data[field.offset:field.offset+size], "big" if endian == ">" else "little", signed=signed)
    if field.bit_size is not None:
        raw = int.from_bytes(data[field.offset:field.offset+size], "big" if endian == ">" else "little", signed=False)
        mask=(1<<field.bit_size)-1
        value=(raw >> field.bit_offset) & mask
        if field.dtype.startswith("s") and value & (1<<(field.bit_size-1)):
            value -= 1<<field.bit_size
    return value


def read_field(row_bytes: bytes, field: FieldSpec, endian: str):
    size=_TYPE_SIZE[field.dtype]
    if field.offset + size * (field.array_length if field.bit_size is None else 1) > len(row_bytes):
        raise DS3FormatError(f"{field.key} exceeds PARAM row size")
    if field.padding:
        return None
    if field.dtype in _INT_LIMITS or field.bit_size is not None:
        return _read_int(row_bytes, field, endian)
    if field.dtype in ("f32","angle32"):
        return struct.unpack_from(endian+"f",row_bytes,field.offset)[0]
    if field.dtype=="f64": return struct.unpack_from(endian+"d",row_bytes,field.offset)[0]
    raise DS3FormatError(f"Field {field.key} is not safely editable")


def _field_integer(field: FieldSpec, value) -> int:
    if isinstance(value, bool):
        if not field.is_bool:
            raise DS3FormatError(f"{field.key} requires an integer")
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise DS3FormatError(f"{field.key} requires an integer")
    elif not isinstance(value, int) and not (isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip())):
        raise DS3FormatError(f"{field.key} requires an integer")
    return int(value)


def write_field(row_bytes: bytes, field: FieldSpec, value, endian: str) -> bytes:
    if not field.editable:
        raise DS3FormatError(f"Field {field.key} is preserved but not editable")
    result=bytearray(row_bytes); size=_TYPE_SIZE[field.dtype]; byteorder="big" if endian==">" else "little"
    if field.bit_size is not None:
        value = _field_integer(field, value)
        if field.is_bool:
            if value not in (0,1): raise DS3FormatError(f"{field.key} is boolean")
        if not field.minimum <= value <= field.maximum:
            raise DS3FormatError(f"{field.key} must be between {field.minimum} and {field.maximum}")
        raw=int.from_bytes(result[field.offset:field.offset+size],byteorder,signed=False)
        encoded=value & ((1<<field.bit_size)-1); mask=((1<<field.bit_size)-1)<<field.bit_offset
        raw=(raw & ~mask) | (encoded<<field.bit_offset)
        result[field.offset:field.offset+size]=raw.to_bytes(size,byteorder,signed=False)
        return bytes(result)
    if field.dtype in _INT_LIMITS:
        value = _field_integer(field, value)
        if field.is_bool and value not in (0,1): raise DS3FormatError(f"{field.key} is boolean")
        if not field.minimum <= value <= field.maximum:
            raise DS3FormatError(f"{field.key} must be between {field.minimum} and {field.maximum}")
        result[field.offset:field.offset+size]=value.to_bytes(size,byteorder,signed=field.dtype.startswith("s") or field.dtype=="b32")
    elif field.dtype in ("f32","angle32","f64"):
        if isinstance(value, bool): raise DS3FormatError(f"{field.key} requires a number")
        try: value=float(value)
        except (TypeError,ValueError,OverflowError): raise DS3FormatError(f"{field.key} requires a number")
        if not math.isfinite(value): raise DS3FormatError(f"{field.key} must be finite")
        if not field.minimum <= value <= field.maximum:
            raise DS3FormatError(f"{field.key} must be between {field.minimum} and {field.maximum}")
        struct.pack_into(endian+("d" if field.dtype=="f64" else "f"),result,field.offset,value)
    else:
        raise DS3FormatError(f"Field {field.key} is not safely editable")
    return bytes(result)


class RegulationDocument:
    def __init__(self, source: bytes, metadata_root: Path):
        plain,self.was_encrypted=decrypt_regulation(source)
        self.binder=BND4View(plain)
        self.regulation_version=self.binder.version_string
        self.metadata_root=metadata_root
        self.schemas={name:load_schema(metadata_root,name) for name in TARGET_TABLES}
        self.params={}
        self.entries={}
        for table,schema in self.schemas.items():
            entry=self.binder.find_param(table)
            param=ParamView(self.binder.member_bytes(entry))
            if param.param_type != schema.param_type:
                raise DS3FormatError(f"{table} PARAM type {param.param_type!r} does not match metadata {schema.param_type!r}")
            expected_version=REGULATION_HEADER_VERSIONS[table]
            if param.header_version != expected_version:
                raise DS3FormatError(
                    f"{table} header value {param.header_version} does not match the audited "
                    f"Regulation {REGULATION_VERSION} value {expected_version} "
                    f"(this archive reports version {self.regulation_version or 'unknown'!r})"
                )
            if param.rows and param.detected_row_size is not None and param.detected_row_size != schema.row_size:
                raise DS3FormatError(f"{table} row size {param.detected_row_size} does not match audited metadata {schema.row_size}")
            self.entries[table]=entry; self.params[table]=param
        self._plain=plain
        self._original_plain=plain
        self._dirty=set()
        self._created_originals={}
        self._created_ids=set()

    def identify_created_rows(self, source: bytes):
        """Identify rows supplied by this project beyond its source regulation."""
        plain, _ = decrypt_regulation(source)
        baseline = BND4View(plain)
        created = set()
        for table,param in self.params.items():
            original = ParamView(baseline.member_bytes(baseline.find_param(table)))
            ids = {row.row_id for row in original.rows}
            created.update((table,row.row_id) for row in param.rows if row.row_id not in ids)
        self._created_ids = created | set(self._created_originals)

    def _display_name(self, table: str, row: ParamRow) -> str:
        schema = self.schemas[table]
        return row.name or schema.row_names.get(row.row_id) or f"Row {row.row_id}"

    def list_rows(self, table: str):
        param=self.params[table]
        return [{"id":r.row_id,"name":self._display_name(table,r),"created":(table,r.row_id) in self._created_ids} for r in param.rows]

    def create_row(self, table: str, source_id: int, new_id: int, name: str):
        schema = self.schemas[table]
        param = self.params[table]
        member = param.copy_row(source_id, new_id, name, schema.row_size)
        plain = self.binder.grow_member(self.entries[table], member)
        binder = BND4View(plain)
        # Validate all relocated members before publishing the draft.
        entries = {key:binder.find_param(key) for key in self.params}
        params = {key:ParamView(binder.member_bytes(entry)) for key,entry in entries.items()}
        created = params[table].row(new_id)
        self._created_originals[table,new_id] = member[created.data_offset:created.data_offset+schema.row_size]
        self._created_ids.add((table,new_id))
        self._plain,self.binder,self.entries,self.params = plain,binder,entries,params
        self._dirty.add((table,new_id,'__created__'))
        return self.read_row(table,new_id)

    def read_row(self, table: str, row_id: int):
        schema=self.schemas[table]; param=self.params[table]; row=param.row(row_id)
        member=self.binder.member_bytes(self.entries[table])
        row_bytes=member[row.data_offset:row.data_offset+schema.row_size]
        fields=[]
        for field in schema.fields:
            if field.padding or field.array_length != 1: continue
            value=read_field(row_bytes,field,param.endian)
            fields.append({
                "key":field.key,"label":field.label,"description":field.description,"group":field.group,
                "value":value,"type":"bool" if field.is_bool else "enum" if field.enum and schema.enums.get(field.enum) else "number",
                "minimum":field.minimum,"maximum":field.maximum,"enum":schema.enums.get(field.enum,{}),"enumName":field.enum,
                "reference":field.reference,"dtype":field.dtype,
                "editable":field.editable,
            })
        return {
            "id": row.row_id,
            "name": self._display_name(table, row),
            "fields": fields,
            "description": schema.description,
        }

    def edit(self, table: str, row_id: int, field_key: str, value):
        row_id = integer_value(row_id, "PARAM row ID", DS3FormatError)
        schema=self.schemas[table]; field=schema.field(field_key); param=self.params[table]; row=param.row(row_id)
        if field.enum and schema.enums.get(field.enum):
            if str(value) not in schema.enums[field.enum]:
                raise DS3FormatError(f"{field.key} must be one of the audited {field.enum} enum values")
        entry=self.entries[table]; member=bytearray(self.binder.member_bytes(entry))
        row_bytes=bytes(member[row.data_offset:row.data_offset+schema.row_size])
        patched=write_field(row_bytes,field,value,param.endian)
        member[row.data_offset:row.data_offset+schema.row_size]=patched
        new_plain=self.binder.patch_member(entry,bytes(member))
        self._plain=new_plain; self.binder=BND4View(new_plain)
        self.entries[table]=self.binder.find_param(table)
        self.params[table]=ParamView(self.binder.member_bytes(self.entries[table]))
        original_row_bytes = self._created_originals.get((table,row_id))
        if original_row_bytes is None:
            original_binder = BND4View(self._original_plain)
            original_member = original_binder.member_bytes(original_binder.find_param(table))
            original_row = ParamView(original_member).row(row_id)
            original_row_bytes = original_member[original_row.data_offset:original_row.data_offset+schema.row_size]
        original_value = read_field(original_row_bytes,field,param.endian)
        dirty_key=(table,row_id,field_key)
        current_value=read_field(patched,field,param.endian)
        if current_value == original_value:
            self._dirty.discard(dirty_key)
        else:
            self._dirty.add(dirty_key)
        return self.read_row(table,row_id)

    @property
    def dirty_count(self): return len(self._dirty)

    def plaintext(self): return self._plain

    def export(self, *, iv: bytes | None=None): return encrypt_regulation(self._plain,iv=iv)
