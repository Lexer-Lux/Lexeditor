"""FINAL FANTASY VII REMAKE text-resource reader/writer.

This implements the FF7R (not Rebirth) `GameContents/Text/*/*_TxtRes`
`.uasset`/`.uexp` shape documented by MatyaModding's MIT-licensed
`ff7r-text-tool`. Unlike DataObjects, text entries are variable length, so the
`.uexp` is rebuilt and the export serial-size field in the paired `.uasset` is
updated. All other `.uasset` bytes are preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import struct
from typing import Any


UNREAL_SIGNATURE = b"\xC1\x83\x2A\x9E"
LANGUAGES = frozenset({"BR", "CN", "DE", "ES", "FR", "IT", "JP", "KR", "MX", "TW", "US"})
MAX_STRING_BYTES = 32 * 1024 * 1024
MAX_ENTRIES = 65535
MAX_SUBENTRIES = 15
MAX_NAMES = 2047
TEXT_NAME_COUNT_OFFSET = 41
TEXT_NAME_MAP_OFFSET = 193
TEXT_SERIAL_SIZE_FROM_END = 92


class TextFormatError(ValueError):
    pass


class Reader:
    def __init__(self, data: bytes | bytearray, label: str):
        self.data = data
        self.label = label
        self.pos = 0

    def seek(self, offset: int, whence: int = 0) -> None:
        if whence == 0:
            target = offset
        elif whence == 1:
            target = self.pos + offset
        elif whence == 2:
            target = len(self.data) + offset
        else:
            raise ValueError("invalid whence")
        if target < 0 or target > len(self.data):
            raise TextFormatError(f"{self.label}: offset {target} is outside the file")
        self.pos = target

    def read(self, size: int) -> bytes:
        if size < 0 or self.pos + size > len(self.data):
            raise TextFormatError(f"{self.label}: unexpected end of file at 0x{self.pos:X}")
        result = bytes(self.data[self.pos:self.pos + size])
        self.pos += size
        return result

    def int32(self) -> int:
        try:
            value = struct.unpack_from("<i", self.data, self.pos)[0]
        except struct.error as error:
            raise TextFormatError(f"{self.label}: unexpected end of file at 0x{self.pos:X}") from error
        self.pos += 4
        return value

    def uint32(self) -> int:
        try:
            value = struct.unpack_from("<I", self.data, self.pos)[0]
        except struct.error as error:
            raise TextFormatError(f"{self.label}: unexpected end of file at 0x{self.pos:X}") from error
        self.pos += 4
        return value

    def fstring(self) -> str:
        length = self.int32()
        if length == 0:
            return ""
        if length > 0:
            if length > MAX_STRING_BYTES:
                raise TextFormatError(f"{self.label}: implausibly large string ({length} bytes)")
            raw = self.read(length)
            if not raw.endswith(b"\0"):
                raise TextFormatError(f"{self.label}: ASCII FString lacks a terminator")
            try:
                return raw[:-1].decode("utf-8")
            except UnicodeDecodeError as error:
                raise TextFormatError(f"{self.label}: invalid UTF-8 text") from error
        code_units = -length
        byte_length = code_units * 2
        if byte_length > MAX_STRING_BYTES:
            raise TextFormatError(f"{self.label}: implausibly large UTF-16 string ({byte_length} bytes)")
        raw = self.read(byte_length)
        if not raw.endswith(b"\0\0"):
            raise TextFormatError(f"{self.label}: UTF-16 FString lacks a terminator")
        try:
            return raw[:-2].decode("utf-16-le")
        except UnicodeDecodeError as error:
            raise TextFormatError(f"{self.label}: invalid UTF-16 text") from error


def _fstring(value: str) -> bytes:
    if not isinstance(value, str):
        raise TypeError("FF7R text values must be strings")
    if "\0" in value:
        raise ValueError("FF7R text values cannot contain NUL characters")
    try:
        raw = value.encode("ascii")
    except UnicodeEncodeError:
        raw = value.encode("utf-16-le")
        units = len(raw) // 2 + 1
        return struct.pack("<i", -units) + raw + b"\0\0"
    return struct.pack("<i", len(raw) + 1) + raw + b"\0"


def sha256_bytes(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_text_uasset_names(data: bytes, label: str = "uasset") -> tuple[str, ...]:
    """Read the FF7R text-resource name map while preserving the package raw."""
    if len(data) < TEXT_NAME_MAP_OFFSET or data[:4] != UNREAL_SIGNATURE:
        raise TextFormatError(f"{label}: not an FF7R text-resource Unreal package")
    if TEXT_NAME_COUNT_OFFSET + 4 > len(data):
        raise TextFormatError(f"{label}: truncated name-count field")
    count = struct.unpack_from("<I", data, TEXT_NAME_COUNT_OFFSET)[0]
    if count > MAX_NAMES:
        raise TextFormatError(f"{label}: unreasonable name count {count}")
    reader = Reader(data, label)
    reader.seek(TEXT_NAME_MAP_OFFSET)
    names: list[str] = []
    for _ in range(count):
        names.append(reader.fstring())
        reader.read(4)  # Unreal name hash
    return tuple(names)


@dataclass
class TextSubEntry:
    id: str
    text: str
    name_index: int


@dataclass
class TextEntry:
    id: str
    text: str
    subentries: list[TextSubEntry]


class TextResourcePackage:
    def __init__(self, uasset_path: Path, uexp_path: Path, *, asset: str = ""):
        self.uasset_path = Path(uasset_path)
        self.uexp_path = Path(uexp_path)
        self.asset = asset or self.uasset_path.with_suffix("").as_posix()
        self.uasset_bytes = bytearray(self.uasset_path.read_bytes())
        self.uexp_bytes = bytearray(self.uexp_path.read_bytes())
        self.names = parse_text_uasset_names(bytes(self.uasset_bytes), self.uasset_path.name)
        self.head, self.language, self.entries = self._parse_uexp(bytes(self.uexp_bytes))
        self.source_uasset_sha256 = sha256_bytes(self.uasset_bytes)
        self.source_uexp_sha256 = sha256_bytes(self.uexp_bytes)

    @classmethod
    def from_bytes(cls, uasset: bytes, uexp: bytes, *, asset: str = "fixture") -> "TextResourcePackage":
        obj = cls.__new__(cls)
        obj.uasset_path = Path(f"{asset}.uasset")
        obj.uexp_path = Path(f"{asset}.uexp")
        obj.asset = asset
        obj.uasset_bytes = bytearray(uasset)
        obj.uexp_bytes = bytearray(uexp)
        obj.names = parse_text_uasset_names(bytes(obj.uasset_bytes), obj.uasset_path.name)
        obj.head, obj.language, obj.entries = obj._parse_uexp(bytes(obj.uexp_bytes))
        obj.source_uasset_sha256 = sha256_bytes(obj.uasset_bytes)
        obj.source_uexp_sha256 = sha256_bytes(obj.uexp_bytes)
        return obj

    def _parse_uexp(self, data: bytes) -> tuple[bytes, str, list[TextEntry]]:
        reader = Reader(data, self.uexp_path.name)
        head = reader.read(2)
        language = reader.fstring()
        if language not in LANGUAGES:
            raise TextFormatError(f"{reader.label}: unknown language {language!r}")
        if reader.int32() != 0:
            raise TextFormatError(f"{reader.label}: expected null marker before text count")
        count = reader.uint32()
        if count > MAX_ENTRIES:
            raise TextFormatError(f"{reader.label}: unreasonable text-entry count {count}")
        entries: list[TextEntry] = []
        for _ in range(count):
            entry_id = reader.fstring()
            text = reader.fstring()
            sub_count = reader.uint32()
            if sub_count > MAX_SUBENTRIES:
                raise TextFormatError(f"{reader.label}: unreasonable sub-entry count {sub_count} for {entry_id}")
            subs: list[TextSubEntry] = []
            seen: set[int] = set()
            for _sub in range(sub_count):
                name_index = reader.uint32()
                if name_index >= len(self.names):
                    raise TextFormatError(f"{reader.label}: sub-entry name index {name_index} is outside the name map")
                if name_index in seen:
                    raise TextFormatError(f"{reader.label}: duplicate sub-entry id for {entry_id}")
                seen.add(name_index)
                if reader.int32() != 0:
                    raise TextFormatError(f"{reader.label}: expected null marker in sub-entry")
                subs.append(TextSubEntry(self.names[name_index], reader.fstring(), name_index))
            entries.append(TextEntry(entry_id, text, subs))
        if reader.read(4) != UNREAL_SIGNATURE:
            raise TextFormatError(f"{reader.label}: missing trailing Unreal signature")
        if reader.pos != len(data):
            raise TextFormatError(f"{reader.label}: unexpected trailing bytes ({len(data) - reader.pos})")
        return head, language, entries

    def api_payload(self, *, source_uasset_sha256: str | None = None,
                    source_uexp_sha256: str | None = None,
                    using_project: bool = False) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "language": self.language,
            "sourceUassetSha256": source_uasset_sha256 or self.source_uasset_sha256,
            "sourceUexpSha256": source_uexp_sha256 or self.source_uexp_sha256,
            "activeUassetSha256": sha256_bytes(self.uasset_bytes),
            "activeUexpSha256": sha256_bytes(self.uexp_bytes),
            "usingProject": using_project,
            "records": [
                {
                    "id": index,
                    "key": entry.id,
                    "text": entry.text,
                    "subentries": [{"id": sub.id, "text": sub.text} for sub in entry.subentries],
                }
                for index, entry in enumerate(self.entries)
            ],
        }

    def text_map(self) -> dict[str, str]:
        return {entry.id: entry.text for entry in self.entries if entry.id}

    def apply_edits(self, edits: list[dict[str, Any]]) -> None:
        for edit in edits:
            if not isinstance(edit, dict):
                raise TypeError("Each text edit must be an object")
            index = int(edit.get("entry", -1))
            if index < 0 or index >= len(self.entries):
                raise IndexError(f"Text entry index out of range: {index}")
            value = edit.get("text")
            if not isinstance(value, str):
                raise TypeError("Text edit requires a string 'text' value")
            if "\0" in value:
                raise ValueError("Text values cannot contain NUL characters")
            entry = self.entries[index]
            sub_id = edit.get("subId")
            if sub_id in (None, ""):
                entry.text = value
                continue
            matches = [sub for sub in entry.subentries if sub.id == sub_id]
            if len(matches) != 1:
                raise KeyError(f"Unknown text sub-entry {sub_id!r} for {entry.id}")
            matches[0].text = value
        self._rebuild()

    def _rebuild(self) -> None:
        output = bytearray(self.head)
        output += _fstring(self.language)
        output += struct.pack("<iI", 0, len(self.entries))
        for entry in self.entries:
            output += _fstring(entry.id)
            output += _fstring(entry.text)
            output += struct.pack("<I", len(entry.subentries))
            for sub in entry.subentries:
                output += struct.pack("<Ii", sub.name_index, 0)
                output += _fstring(sub.text)
        output += UNREAL_SIGNATURE
        self.uexp_bytes = output
        if len(self.uasset_bytes) < TEXT_SERIAL_SIZE_FROM_END:
            raise TextFormatError(f"{self.uasset_path.name}: too small to contain FF7R text export size")
        # Matya's writer updates the FF7R text export serial size 92 bytes from
        # the end of the .uasset. The trailing 4-byte package signature in the
        # .uexp is outside that export's serialized payload.
        struct.pack_into("<i", self.uasset_bytes,
                         len(self.uasset_bytes) - TEXT_SERIAL_SIZE_FROM_END,
                         len(self.uexp_bytes) - len(UNREAL_SIGNATURE))

    def write_pair(self, uasset_target: Path, uexp_target: Path) -> tuple[Path, Path]:
        uasset_target = Path(uasset_target)
        uexp_target = Path(uexp_target)
        uasset_target.parent.mkdir(parents=True, exist_ok=True)
        uexp_target.parent.mkdir(parents=True, exist_ok=True)
        for target, data in ((uasset_target, bytes(self.uasset_bytes)),
                             (uexp_target, bytes(self.uexp_bytes))):
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(target)
            if target.read_bytes() != data:
                raise OSError(f"FF7R text-resource readback mismatch: {target}")
        return uasset_target, uexp_target
