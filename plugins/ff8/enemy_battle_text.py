"""Safe local battle-dialogue editing for FF8 enemy DAT files.

The format comes from FF8 Ultimate Editor revision 343d97e9, specifically
``AIData.SECTION_BATTLE_SCRIPT_*`` and
``MonsterAnalyser.analyze_battle_script_section``/``prepare_ai``.  The final
two subsections of the battle-script section are a four-byte-aligned table of
u16 offsets and a four-byte-aligned series of null-terminated FF8 strings.

This module deliberately edits existing lines only.  Enemy AI refers to these
lines with one-byte indexes, so adding, removing, or reordering lines needs a
separate reference-aware operation.  A same-size edit changes only the chosen
string bytes.  A size-changing edit preserves the complete AI prefix and every
later DAT section byte-for-byte, and shifts later top-level section pointers by
the exact aligned delta.
"""

from __future__ import annotations

from .kernel_text import decode, encode


MAX_ENCODED_LINE_SIZE = 100  # Includes the null terminator in upstream Ifrit.
MAX_LINES = 256              # Battle-text operands are one byte.


def _section(raw: bytes) -> tuple[int, int]:
    """Return the battle-script section range from the DAT section table."""
    if len(raw) < 16:
        raise ValueError("Enemy DAT header is too short for battle text")
    section_count = int.from_bytes(raw[0:4], "little") + 1
    section_number = 2 if section_count == 3 else 8
    if section_count <= section_number:
        raise ValueError("Enemy DAT has no battle-script section")
    table_index = section_number - 1
    start = int.from_bytes(raw[4 + table_index * 4:8 + table_index * 4], "little")
    end = int.from_bytes(raw[8 + table_index * 4:12 + table_index * 4], "little")
    header_end = 4 + section_count * 4
    if start < header_end or end < start or end > len(raw):
        raise ValueError("Enemy DAT battle-script section is invalid")
    return start, end


def _layout(raw: bytes) -> dict:
    section_start, section_end = _section(raw)
    if section_start == section_end:
        return {
            "available": False,
            "section_start": section_start,
            "section_end": section_end,
            "entries": [],
        }

    section = raw[section_start:section_end]
    if len(section) < 16:
        raise ValueError("Enemy DAT battle-script section is too short")
    subsection_count = int.from_bytes(section[0:4], "little")
    ai_offset = int.from_bytes(section[4:8], "little")
    offset_start = int.from_bytes(section[8:12], "little")
    text_start = int.from_bytes(section[12:16], "little")
    if subsection_count != 3 or ai_offset != 16 or ai_offset + 20 > offset_start:
        raise ValueError("Enemy DAT battle-script header is unsupported")
    if offset_start > text_start or text_start > len(section):
        raise ValueError("Enemy DAT battle-text subsection offsets are invalid")
    if offset_start % 4 or text_start % 4 or (text_start - offset_start) % 4:
        raise ValueError("Enemy DAT battle-text subsections are not four-byte aligned")

    table = section[offset_start:text_start]
    words = [int.from_bytes(table[index:index + 2], "little")
             for index in range(0, len(table), 2)]
    offsets: list[int] = []
    if words:
        if words[0] != 0:
            raise ValueError("Enemy DAT first battle-text offset is not zero")
        offsets.append(0)
        for index, value in enumerate(words[1:], 1):
            # Ifrit pads an odd number of u16 entries with one zero word.
            if value == 0:
                if any(words[index:]):
                    raise ValueError("Enemy DAT battle-text offset padding is invalid")
                break
            if value <= offsets[-1]:
                raise ValueError("Enemy DAT battle-text offsets are not increasing")
            offsets.append(value)
    if len(offsets) > MAX_LINES:
        raise ValueError("Enemy DAT has more than 256 battle-text lines")

    text_data = section[text_start:]
    entries = []
    for index, relative in enumerate(offsets):
        limit = offsets[index + 1] if index + 1 < len(offsets) else len(text_data)
        if relative >= len(text_data) or limit <= relative or limit > len(text_data):
            raise ValueError("Enemy DAT battle-text offset is outside its subsection")
        terminator = text_data.find(b"\0", relative, min(limit, relative + MAX_ENCODED_LINE_SIZE))
        if terminator < 0:
            raise ValueError(f"Enemy battle-text line {index} has no terminator within 100 bytes")
        if index + 1 < len(offsets) and terminator + 1 != limit:
            raise ValueError(f"Enemy battle-text line {index} has unsupported inter-line data")
        payload = bytes(text_data[relative:terminator + 1])
        entries.append({
            "id": index,
            "offset": relative,
            "absolute_offset": section_start + text_start + relative,
            "payload": payload,
            "text": decode(payload[:-1]),
        })

    if entries:
        padding = text_data[entries[-1]["offset"] + len(entries[-1]["payload"]):]
        if any(padding):
            raise ValueError("Enemy DAT battle-text padding contains unsupported data")
        if len(padding) > 3:
            raise ValueError("Enemy DAT battle-text padding is too large")
    elif any(text_data):
        raise ValueError("Enemy DAT has battle-text data without an offset table")

    return {
        "available": True,
        "section_start": section_start,
        "section_end": section_end,
        "section": section,
        "offset_start": offset_start,
        "text_start": text_start,
        "entries": entries,
    }


def read(raw: bytes) -> dict:
    """Decode existing local battle-dialogue lines into an editor document."""
    layout = _layout(raw)
    return {
        "available": layout["available"],
        "sectionOffset": layout["section_start"],
        "sectionSize": layout["section_end"] - layout["section_start"],
        "lines": [
            {
                "id": entry["id"],
                "text": entry["text"],
                "encodedSize": len(entry["payload"]),
                "maximumEncodedSize": MAX_ENCODED_LINE_SIZE,
            }
            for entry in layout["entries"]
        ],
    }


def _encoded_lines(layout: dict, texts: list[str]) -> list[bytes]:
    entries = layout["entries"]
    if len(texts) != len(entries):
        raise ValueError("Enemy battle-text rebuild must preserve the line count and order")
    result = []
    for index, (entry, text) in enumerate(zip(entries, texts)):
        if not isinstance(text, str):
            raise ValueError(f"Enemy battle-text line {index} must be text")
        # Reuse the original bytes for an unchanged display value.  This keeps
        # source compression choices and raw escape sequences byte-identical.
        payload = (entry["payload"] if text == entry["text"]
                   else _encode_preserving(entry["payload"], entry["text"], text))
        if len(payload) > MAX_ENCODED_LINE_SIZE:
            raise ValueError(
                f"Enemy battle-text line {index} is {len(payload)} encoded bytes; the limit is 100")
        result.append(payload)
    return result


def _encoded_units(data: bytes) -> list[tuple[bytes, str]]:
    """Split encoded text into units whose decoded strings concatenate exactly."""
    units = []
    index = 0
    while index < len(data):
        width = 2 if data[index] in (0x03, 0x05, 0x0A, 0x0E) \
            and index + 1 < len(data) else 1
        raw = data[index:index + width]
        units.append((raw, decode(raw)))
        index += width
    return units


def _encode_preserving(payload: bytes, old_text: str, new_text: str) -> bytes:
    """Keep unchanged encoded units instead of recompressing the full line."""
    units = _encoded_units(payload[:-1])
    if "".join(text for _, text in units) != old_text:
        raise ValueError("Enemy battle-text source bytes do not match their decoded value")

    common_prefix = 0
    prefix_limit = min(len(old_text), len(new_text))
    while common_prefix < prefix_limit \
            and old_text[common_prefix] == new_text[common_prefix]:
        common_prefix += 1
    common_suffix = 0
    suffix_limit = min(len(old_text) - common_prefix, len(new_text) - common_prefix)
    while common_suffix < suffix_limit \
            and old_text[-1 - common_suffix] == new_text[-1 - common_suffix]:
        common_suffix += 1

    prefix_units = 0
    prefix_chars = 0
    for raw, text in units:
        if prefix_chars + len(text) > common_prefix:
            break
        prefix_chars += len(text)
        prefix_units += 1

    suffix_units = len(units)
    suffix_chars = 0
    for unit_index in range(len(units) - 1, prefix_units - 1, -1):
        text = units[unit_index][1]
        if suffix_chars + len(text) > common_suffix:
            break
        suffix_chars += len(text)
        suffix_units = unit_index

    middle_end = len(new_text) - suffix_chars if suffix_chars else len(new_text)
    middle = encode(new_text[prefix_chars:middle_end])
    return (b"".join(raw for raw, _ in units[:prefix_units]) + middle
            + b"".join(raw for raw, _ in units[suffix_units:]) + b"\0")


def rebuild(raw: bytes, texts: list[str]) -> tuple[bytes, int]:
    """Rebuild existing lines, preserving every unrelated byte."""
    layout = _layout(raw)
    if not layout["available"]:
        if texts:
            raise ValueError("Enemy DAT has no battle text to edit")
        return raw, 0
    payloads = _encoded_lines(layout, texts)
    entries = layout["entries"]
    changed = sum(payload != entry["payload"]
                  for payload, entry in zip(payloads, entries))
    if not changed:
        return raw, 0

    # Preserve exact positions when all encoded sizes are unchanged.  This is
    # the strongest form of mutation isolation: only edited payload bytes move.
    if all(len(payload) == len(entry["payload"])
           for payload, entry in zip(payloads, entries)):
        result = bytearray(raw)
        for payload, entry in zip(payloads, entries):
            if payload != entry["payload"]:
                start = entry["absolute_offset"]
                result[start:start + len(payload)] = payload
        verified = read(bytes(result))
        if [line["text"] for line in verified["lines"]] != texts:
            raise ValueError("Rebuilt enemy battle text did not decode to the requested values")
        return bytes(result), changed

    offsets = bytearray()
    text_data = bytearray()
    cursor = 0
    for payload in payloads:
        if cursor > 0xFFFF:
            raise ValueError("Enemy battle-text data exceeds the u16 offset range")
        offsets.extend(cursor.to_bytes(2, "little"))
        text_data.extend(payload)
        cursor += len(payload)
    while len(offsets) % 4:
        offsets.append(0)
    while len(text_data) % 4:
        text_data.append(0)

    section = bytearray(layout["section"][:layout["offset_start"]])
    new_text_start = layout["offset_start"] + len(offsets)
    section[12:16] = new_text_start.to_bytes(4, "little")
    section.extend(offsets)
    section.extend(text_data)
    if len(section) % 4:
        raise ValueError("Rebuilt enemy battle-script section is not four-byte aligned")

    old_end = layout["section_end"]
    delta = len(section) - len(layout["section"])
    result = bytearray(raw[:layout["section_start"]])
    result.extend(section)
    result.extend(raw[old_end:])
    section_count = int.from_bytes(raw[0:4], "little") + 1
    for index in range(section_count):
        position = 4 + index * 4
        old_offset = int.from_bytes(raw[position:position + 4], "little")
        if old_offset >= old_end:
            shifted = old_offset + delta
            if shifted < 0 or shifted > 0xFFFFFFFF:
                raise ValueError("A shifted enemy DAT section offset is outside the u32 range")
            result[position:position + 4] = shifted.to_bytes(4, "little")

    verified = read(bytes(result))
    if [line["text"] for line in verified["lines"]] != texts:
        raise ValueError("Rebuilt enemy battle text did not decode to the requested values")
    return bytes(result), changed


def apply_edits(raw: bytes, edits: list[dict]) -> tuple[bytes, int]:
    """Apply ``{id, text}`` replacements to existing local dialogue lines."""
    document = read(raw)
    texts = [line["text"] for line in document["lines"]]
    seen = set()
    for edit in edits:
        try:
            line_id = edit["id"]
            text = edit["text"]
        except (KeyError, TypeError) as error:
            raise ValueError("Enemy battle-text edits require an integer id and text") from error
        if isinstance(line_id, bool) or not isinstance(line_id, int):
            raise ValueError("Enemy battle-text edits require an integer id and text")
        if line_id in seen:
            raise ValueError(f"Duplicate enemy battle-text edit for line {line_id}")
        if not 0 <= line_id < len(texts):
            raise ValueError(f"Enemy battle-text line does not exist: {line_id}")
        seen.add(line_id)
        texts[line_id] = text
    return rebuild(raw, texts)
