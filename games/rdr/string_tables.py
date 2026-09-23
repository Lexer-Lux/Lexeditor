"""Structured reader/writer for RDR1 .strtbl localization tables.

Format evidence:
- Foxxyyy/Magic-RDR exposes RDR string tables and supports string import.
- Foxxyyy/CodeX.Games.RDR1 documents the ordinary STRTBL header, identifier
  table, language block offsets, hashed entries, UTF-16LE text, and glyph/layout
  metadata.

Neither project is copied here.  This module independently implements only the
small subset needed for bounded text replacement while preserving identifiers,
hashes, glyph metrics, language sharing, unknown padding, and block tails.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Iterable


LANGUAGE_NAMES = (
    "English",
    "Spanish",
    "French",
    "German",
    "Italian",
    "Japanese",
    "Chinese (Traditional)",
    "Chinese (Simplified)",
    "Korean",
    "Spanish (Spain)",
    "Spanish (Mexico)",
    "Portuguese",
    "Polish",
    "Russian",
)
MAX_LANGUAGES = 64
MAX_IDENTIFIERS = 1_000_000
MAX_STRING_UNITS = 4_000_000


@dataclass(frozen=True)
class StringEntry:
    prefix: bytes
    hash: int
    text: str
    terminators: int
    encoded_text: bytes
    suffix: bytes


@dataclass(frozen=True)
class LanguageBlock:
    old_offset: int
    entries: tuple[StringEntry, ...]
    trailing: bytes


@dataclass(frozen=True)
class StringTable:
    original: bytes
    positions: tuple[int, ...]
    version: int
    identifiers: tuple[str, ...]
    prefix: bytes
    blocks: dict[int, LanguageBlock]


def _u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError("String table contains a truncated 32-bit value")
    return struct.unpack_from("<I", data, offset)[0]


def _i32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError("String table contains a truncated 32-bit value")
    return struct.unpack_from("<i", data, offset)[0]


def joaat(value: str) -> int:
    """RAGE/Jenkins one-at-a-time hash used to link identifiers to entries."""
    result = 0
    try:
        raw = value.lower().encode("latin-1", errors="strict")
    except UnicodeEncodeError as error:
        raise ValueError(f"String-table identifier is not single-byte text: {value!r}") from error
    for byte in raw:
        result = (result + byte) & 0xFFFFFFFF
        result = (result + (result << 10)) & 0xFFFFFFFF
        result ^= result >> 6
    result = (result + (result << 3)) & 0xFFFFFFFF
    result ^= result >> 11
    result = (result + (result << 15)) & 0xFFFFFFFF
    return result & 0xFFFFFFFF


def parse(data: bytes) -> StringTable:
    if len(data) < 12:
        raise ValueError("String table is too short")
    language_count = _i32(data, 0)
    if language_count <= 0 or language_count > MAX_LANGUAGES:
        raise ValueError(f"Unsupported string-table language count: {language_count}")

    cursor = 4
    positions = tuple(_u32(data, cursor + index * 4) for index in range(language_count))
    cursor += language_count * 4
    version = _u32(data, cursor)
    cursor += 4
    identifier_count = _i32(data, cursor)
    cursor += 4
    if identifier_count < 0 or identifier_count > MAX_IDENTIFIERS:
        raise ValueError(f"Unsupported string-table identifier count: {identifier_count}")

    language_starts = [offset for offset in positions if 0 < offset <= len(data)]
    prefix_end = min(language_starts) if language_starts else len(data)
    identifiers: list[str] = []
    for _index in range(identifier_count):
        if cursor + 4 > prefix_end:
            raise ValueError("String-table identifier header overlaps language data")
        declared_length = _u32(data, cursor)
        cursor += 4
        terminator = data.find(b"\x00", cursor, prefix_end)
        if terminator < 0:
            raise ValueError("String-table identifier is missing its terminator")
        raw = data[cursor:terminator]
        # The public writers store a character count, then a NUL-terminated
        # single-byte identifier.  Keep the entire prefix byte-for-byte, but
        # reject structural drift rather than guessing a different encoding.
        if declared_length != len(raw):
            raise ValueError(
                f"String-table identifier length mismatch: {declared_length} != {len(raw)}"
            )
        identifiers.append(raw.decode("latin-1"))
        cursor = terminator + 1
    if cursor > prefix_end:
        raise ValueError("String-table identifier data overlaps a language block")

    unique_offsets = sorted({offset for offset in positions if 0 < offset < len(data)})
    blocks: dict[int, LanguageBlock] = {}
    for block_index, start in enumerate(unique_offsets):
        end = unique_offsets[block_index + 1] if block_index + 1 < len(unique_offsets) else len(data)
        if start + 4 > end:
            raise ValueError("String-table language block is truncated")
        entry_count = _u32(data, start)
        cursor = start + 4
        entries: list[StringEntry] = []
        for entry_index in range(entry_count):
            if cursor + 14 > end:
                raise ValueError(
                    f"String-table entry {entry_index} header exceeds its language block"
                )
            prefix = data[cursor:cursor + 10]
            entry_hash = _u32(prefix, 0)
            cursor += 10
            unit_count = _i32(data, cursor)
            cursor += 4
            if unit_count < 0 or unit_count > MAX_STRING_UNITS:
                raise ValueError(
                    f"Unsupported UTF-16 unit count in string-table entry {entry_index}: "
                    f"{unit_count}"
                )
            byte_count = unit_count * 2
            if cursor + byte_count + 10 > end:
                raise ValueError(
                    f"String-table entry {entry_index} text exceeds its language block"
                )
            encoded_text = data[cursor:cursor + byte_count]
            cursor += byte_count
            try:
                decoded = encoded_text.decode("utf-16le")
            except UnicodeDecodeError as error:
                raise ValueError(
                    f"String-table entry {entry_index} is not valid UTF-16LE"
                ) from error
            terminators = len(decoded) - len(decoded.rstrip("\x00"))
            text = decoded[:-terminators] if terminators else decoded
            suffix = data[cursor:cursor + 10]
            cursor += 10
            entries.append(StringEntry(
                prefix=prefix,
                hash=entry_hash,
                text=text,
                terminators=terminators,
                encoded_text=encoded_text,
                suffix=suffix,
            ))
        blocks[start] = LanguageBlock(
            old_offset=start,
            entries=tuple(entries),
            trailing=data[cursor:end],
        )

    for offset in positions:
        if offset not in {0, len(data)} and offset not in blocks:
            raise ValueError(f"String-table language offset is invalid: 0x{offset:X}")

    return StringTable(
        original=data,
        positions=positions,
        version=version,
        identifiers=tuple(identifiers),
        prefix=data[:prefix_end],
        blocks=blocks,
    )


def _identifier_lookup(table: StringTable) -> dict[int, tuple[str, ...]]:
    by_hash: dict[int, list[str]] = {}
    for identifier in table.identifiers:
        by_hash.setdefault(joaat(identifier), []).append(identifier)
    return {key: tuple(values) for key, values in by_hash.items()}


def _language_name(index: int) -> str:
    return LANGUAGE_NAMES[index] if index < len(LANGUAGE_NAMES) else f"Language {index + 1}"


def rows(table: StringTable) -> list[dict]:
    """Return one row per physical language-block entry.

    Duplicate language slots (the documented Spain/Mexico sharing case) are
    represented once with all slot indexes attached, so editing the shared
    block cannot misleadingly look like two independent changes.
    """
    identifiers = _identifier_lookup(table)
    result: list[dict] = []
    for block_offset in sorted(table.blocks):
        block = table.blocks[block_offset]
        language_indexes = tuple(
            index for index, offset in enumerate(table.positions) if offset == block_offset
        )
        language_label = " / ".join(_language_name(index) for index in language_indexes)
        primary_language = language_indexes[0]
        for entry_index, entry in enumerate(block.entries):
            candidates = identifiers.get(entry.hash, ())
            identifier = candidates[0] if len(candidates) == 1 else ""
            result.append({
                "languageIndex": primary_language,
                "languageIndexes": list(language_indexes),
                "language": language_label,
                "entryIndex": entry_index,
                "hash": f"0x{entry.hash:08X}",
                "hashValue": entry.hash,
                "identifier": identifier,
                "identifierCandidates": list(candidates),
                "text": entry.text,
                "sharedLanguageBlock": len(language_indexes) > 1,
            })
    return result


def serialize(table: StringTable, changes: dict[tuple[int, int], str]) -> bytes:
    if not changes:
        return table.original

    output = bytearray(table.prefix)
    old_to_new: dict[int, int] = {}
    for old_offset in sorted(table.blocks):
        old_to_new[old_offset] = len(output)
        block = table.blocks[old_offset]
        language_indexes = tuple(
            index for index, offset in enumerate(table.positions) if offset == old_offset
        )
        output.extend(struct.pack("<I", len(block.entries)))
        for entry_index, entry in enumerate(block.entries):
            output.extend(entry.prefix)
            replacement = None
            for language_index in language_indexes:
                key = (language_index, entry_index)
                if key not in changes:
                    continue
                candidate = changes[key]
                if replacement is not None and candidate != replacement:
                    raise ValueError(
                        "Conflicting edits target language slots that share one string block"
                    )
                replacement = candidate
            if replacement is None:
                encoded = entry.encoded_text
            else:
                if "\x00" in replacement:
                    raise ValueError("String-table text cannot contain NUL characters")
                encoded = (
                    replacement + ("\x00" * entry.terminators)
                ).encode("utf-16le")
                if len(encoded) // 2 > MAX_STRING_UNITS:
                    raise ValueError("String-table text is too large")
            output.extend(struct.pack("<i", len(encoded) // 2))
            output.extend(encoded)
            output.extend(entry.suffix)
        output.extend(block.trailing)

    final_end = len(output)
    for index, old_offset in enumerate(table.positions):
        if old_offset == 0:
            new_offset = 0
        elif old_offset == len(table.original):
            new_offset = final_end
        elif old_offset in old_to_new:
            new_offset = old_to_new[old_offset]
        else:
            raise ValueError(f"Cannot relocate string-table language offset: 0x{old_offset:X}")
        struct.pack_into("<I", output, 4 + index * 4, new_offset)
    return bytes(output)


def apply_text_edits(data: bytes, edits: Iterable[dict]) -> tuple[bytes, int]:
    table = parse(data)
    requested: dict[tuple[int, int], str] = {}
    changed = 0
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("String-table edits must be objects")
        language_index = edit.get("languageIndex")
        entry_index = edit.get("entryIndex")
        if isinstance(language_index, bool) or not isinstance(language_index, int):
            raise ValueError("String-table language index must be an integer")
        if isinstance(entry_index, bool) or not isinstance(entry_index, int):
            raise ValueError("String-table entry index must be an integer")
        if language_index < 0 or language_index >= len(table.positions):
            raise ValueError("String-table language index is out of range")
        block = table.blocks.get(table.positions[language_index])
        if block is None or entry_index < 0 or entry_index >= len(block.entries):
            raise ValueError("String-table entry index is out of range")
        entry = block.entries[entry_index]

        expected_hash = str(edit.get("expectedHash", "")).strip().casefold()
        if expected_hash != f"0x{entry.hash:08x}":
            raise ValueError("String-table entry identity changed; reload before saving")
        expected_text = edit.get("expectedText")
        if not isinstance(expected_text, str) or expected_text != entry.text:
            raise ValueError("String-table entry text changed; reload before saving")
        value = edit.get("value")
        if not isinstance(value, str):
            raise ValueError("String-table replacement text must be a string")
        key = (language_index, entry_index)
        if key in requested and requested[key] != value:
            raise ValueError("String-table entry is edited more than once")
        requested[key] = value
        if value != entry.text:
            changed += 1

    return serialize(table, requested), changed
