"""FF8 2013 executable text exposed through FFNx Direct Mode.

The fixed English offsets come from FF8 Ultimate Editor's ``exe.json`` and
``SectionExeFile`` reader.  The replacement format and runtime filenames come
from FFNx's ``exe_data.cpp``.  This module only reads ``FF8_EN.exe``; saves are
complete ``.msd`` files for FFNx.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from .kernel_text import decode, encode


SUPPORTED_EXE_SHA256 = (
    "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
)
MAX_MSD_SIZE = 0x7FFFFFFF  # FFNx passes the file size through a signed int.


@dataclass(frozen=True)
class Source:
    id: str
    label: str
    section_id: int
    section: str
    role: str
    filename: str
    exe_offset: int
    count: int
    layout: str


SOURCES = (
    Source("exe_card_names", "Card names", 60, "Card names", "Name",
           "card_names.msd", 0x875074, 110, "count-u16"),
    Source("exe_draw_point", "Draw-point text", 61, "Draw-point text", "Text",
           "draw_point.msd", 0x7921E4, 9, "msd"),
    Source("exe_card_texts", "Card text", 62, "Card text", "Text",
           "card_texts.msd", 0x874B58, 29, "count-plus-u32"),
)
BY_ID = {source.id: source for source in SOURCES}


def _validate_executable(data: bytes) -> None:
    digest = sha256(data).hexdigest()
    if digest != SUPPORTED_EXE_SHA256:
        raise ValueError(
            "Executable text requires the supported FF8 2013 Steam English "
            f"FF8_EN.exe ({SUPPORTED_EXE_SHA256}); found {digest}"
        )


def _bounded_end(data: bytes, offsets: list[int], start: int) -> int:
    """Return the byte after the last terminated string in an offset block."""
    if not offsets or offsets != sorted(offsets) or len(set(offsets)) != len(offsets):
        raise ValueError("Executable text offsets are not strictly increasing")
    if offsets[0] < start:
        raise ValueError("Executable text begins inside its offset table")
    end = data.find(b"\0", offsets[-1])
    if end < 0:
        raise ValueError("The final executable text entry has no terminator")
    return end + 1


def _read_entries(data: bytes, offsets: list[int], expected_count: int) -> list[str]:
    if len(offsets) != expected_count:
        raise ValueError(f"Expected {expected_count} executable text offsets")
    end = _bounded_end(data, offsets, expected_count * 4)
    values = []
    for index, offset in enumerate(offsets):
        limit = offsets[index + 1] if index + 1 < len(offsets) else end
        if not 0 <= offset < limit <= len(data):
            raise ValueError("An executable text offset is outside its data")
        terminator = data.find(b"\0", offset, limit)
        if terminator < 0:
            raise ValueError(f"Executable text {index} has no bounded terminator")
        values.append(decode(data[offset:terminator]))
    return values


def read_msd(path: Path, source: Source) -> list[str]:
    data = path.read_bytes()
    table_size = source.count * 4
    if len(data) <= table_size:
        raise ValueError(f"{source.filename} is too short")
    offsets = [int.from_bytes(data[index:index + 4], "little")
               for index in range(0, table_size, 4)]
    if offsets[0] != table_size:
        raise ValueError(
            f"{source.filename} does not contain exactly {source.count} offsets"
        )
    if _bounded_end(data, offsets, table_size) != len(data):
        raise ValueError(f"{source.filename} has unowned trailing data")
    return _read_entries(data, offsets, source.count)


def build_msd(values: list[str], source: Source) -> bytes:
    if len(values) != source.count:
        raise ValueError(f"{source.label} requires exactly {source.count} entries")
    encoded = []
    for index, value in enumerate(values):
        try:
            raw = encode(str(value)) + b"\0"
        except ValueError as error:
            raise ValueError(f"{source.label} entry {index}: {error}") from error
        encoded.append(raw)
    table_size = source.count * 4
    total = table_size + sum(map(len, encoded))
    if total > MAX_MSD_SIZE or total > 0xFFFFFFFF:
        raise ValueError(f"{source.filename} exceeds FFNx's supported size")
    offset = table_size
    output = bytearray()
    for raw in encoded:
        output.extend(offset.to_bytes(4, "little"))
        offset += len(raw)
    output.extend(b"".join(encoded))
    return bytes(output)


def apply_edits(data: bytes, source: Source, replacements: dict[int, str]) -> tuple[bytes, int]:
    """Rebuild one MSD while preserving every unedited encoded string byte."""
    table_size = source.count * 4
    if len(data) <= table_size:
        raise ValueError(f"{source.filename} is too short")
    offsets = [int.from_bytes(data[index:index + 4], "little")
               for index in range(0, table_size, 4)]
    values = _read_entries(data, offsets, source.count)
    if any(not 0 <= record_id < source.count for record_id in replacements):
        raise ValueError(f"A {source.label} edit has an invalid record ID")
    raw_entries = []
    changed = 0
    for index, offset in enumerate(offsets):
        limit = offsets[index + 1] if index + 1 < source.count else len(data)
        terminator = data.find(b"\0", offset, limit)
        original = data[offset:terminator + 1]
        replacement = replacements.get(index)
        if replacement is None or replacement == values[index]:
            raw_entries.append(original)
            continue
        try:
            raw_entries.append(encode(replacement) + b"\0")
        except ValueError as error:
            raise ValueError(f"{source.label} entry {index}: {error}") from error
        changed += 1
    total = table_size + sum(map(len, raw_entries))
    if total > MAX_MSD_SIZE or total > 0xFFFFFFFF:
        raise ValueError(f"{source.filename} exceeds FFNx's supported size")
    position = table_size
    output = bytearray()
    for raw in raw_entries:
        output.extend(position.to_bytes(4, "little"))
        position += len(raw)
    output.extend(b"".join(raw_entries))
    return bytes(output), changed


def _extract_msd(exe: bytes, source: Source) -> bytes:
    start = source.exe_offset
    if source.layout == "count-u16":
        count = int.from_bytes(exe[start:start + 2], "little")
        if count != source.count:
            raise ValueError(f"FF8_EN.exe has {count}, not {source.count}, card names")
        old_table_size = (count + 1) * 2
        positions = [int.from_bytes(exe[start + 2 + index * 2:start + 4 + index * 2], "little")
                     for index in range(count)]
        new_table_size = count * 4
        offsets = [position - old_table_size + new_table_size for position in positions]
        raw_start = start + old_table_size
        absolute = [start + position for position in positions]
        raw_end = _bounded_end(exe, absolute, raw_start)
        payload = exe[raw_start:raw_end]
    elif source.layout == "msd":
        table_size = source.count * 4
        offsets = [int.from_bytes(exe[start + index:start + index + 4], "little")
                   for index in range(0, table_size, 4)]
        absolute = [start + offset for offset in offsets]
        raw_end = _bounded_end(exe, absolute, start + table_size)
        payload = exe[start + table_size:raw_end]
    elif source.layout == "count-plus-u32":
        stored_count = int.from_bytes(exe[start:start + 2], "little")
        table_start = start + 2
        first_offset = int.from_bytes(exe[table_start:table_start + 4], "little")
        count = first_offset // 4
        if stored_count != 57 or count != source.count:
            raise ValueError("FF8_EN.exe has an unexpected card-text table")
        # The executable stores 57 u16 slots.  FFNx takes every other slot and
        # widens it to the 29 u32 offsets used by the Direct Mode MSD.
        offsets = [int.from_bytes(exe[table_start + index * 4:table_start + index * 4 + 2], "little")
                   for index in range(count)]
        # FFNx deliberately copies from data + first_offset, two bytes before
        # the end of the sparse executable table.  Preserve that contract.
        raw_start = start + first_offset
        absolute = [start + offset for offset in offsets]
        raw_end = _bounded_end(exe, absolute, raw_start)
        payload = exe[raw_start:raw_end]
    else:
        raise ValueError(f"Unknown executable text layout: {source.layout}")

    table_size = source.count * 4
    if offsets[0] != table_size:
        raise ValueError(f"{source.label} does not convert to an FFNx MSD table")
    output = bytearray().join(offset.to_bytes(4, "little") for offset in offsets)
    output.extend(payload)
    # Parsing the result proves every entry is bounded before it reaches the UI.
    _read_entries(bytes(output), offsets, source.count)
    return bytes(output)


def extract(path: Path, source: Source) -> list[str]:
    exe = path.read_bytes()
    _validate_executable(exe)
    msd = _extract_msd(exe, source)
    table_size = source.count * 4
    offsets = [int.from_bytes(msd[index:index + 4], "little")
               for index in range(0, table_size, 4)]
    return _read_entries(msd, offsets, source.count)


def extracted_msd(path: Path, source: Source) -> bytes:
    exe = path.read_bytes()
    _validate_executable(exe)
    return _extract_msd(exe, source)
