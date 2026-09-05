"""Strict FF8 kernel.bin text reader and offset-table rebuilder.

The layout follows FF8 Ultimate Editor's KernelManager: sections 32 through
56 hold text, and each is linked to the leading u16 offsets in a fixed-size
data section.  The encoding follows OpenVIII's FF8 text code page. Unknown
bytes use ``{xNN}``, so an edited string can preserve codes which do not have a
display glyph.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


TEXT_SECTION_FIRST = 32
TEXT_SECTION_LAST = 56
UNUSED_OFFSET = 0xFFFF

_BASIC = (
    " 0123456789%/:!?"
    "…+-=*&「」()·.,~”“"
    "‘#$\"_"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "ÀÁÂÄÇÈÉÊËÌÍÎÏÑÒÓÔÖÙÚÛÜŒ"
    "ßàáâäçèéêëìíîïñòóôöùúûüœ"
)
if len(_BASIC) != 0xA8 - 0x20:
    raise AssertionError("FF8 European code page length is invalid")

_BYTE_TO_TEXT = {0x20 + index: char for index, char in enumerate(_BASIC)}
_BYTE_TO_TEXT.update({
    0xA8: "Ⅷ", 0xA9: "[", 0xAA: "]", 0xAB: "■", 0xAC: "◎",
    0xAD: "♦", 0xAE: "〖", 0xAF: "〗", 0xB0: "□", 0xB1: "★",
    0xB2: "『", 0xB3: "』", 0xB4: "▽", 0xB5: ";", 0xB6: "▼",
    0xB7: "‾", 0xB8: "⨯", 0xB9: "☆", 0xBB: "↓", 0xBC: "°",
    0xBD: "¡", 0xBE: "¿", 0xBF: "─", 0xC0: "«", 0xC1: "»",
    0xC2: "±", 0xC3: "♬", 0xC5: "↑", 0xC9: "™", 0xCA: "<",
    0xCB: ">",
})
_TEXT_TO_BYTE = {text: value for value, text in _BYTE_TO_TEXT.items()}
_TEXT_TO_BYTE.update({"'": _TEXT_TO_BYTE["‘"], "\\": _TEXT_TO_BYTE["/"], "\t": _TEXT_TO_BYTE[" "]})

_COMPRESSED = (
    "in", "e ", "ne", "to", "re", "HP", "l ", "ll",
    "GF", "nt", "il", "o ", "ef", "on", " w", " r",
    "wi", "fi", "EC", "s ", "ar", "FE", " S", "ag",
)

_CHARACTERS = (
    "Squall", "Zell", "Irvine", "Quistis", "Rinoa", "Selphie", "Seifer",
    "Edea", "Laguna", "Kiros", "Ward", "Angelo", "Griever", "Boko",
)
_CHARACTER_CODES = {
    **{name: 0x30 + index for index, name in enumerate(_CHARACTERS[:11])},
    "Angelo": 0x40, "Griever": 0x50, "Boko": 0x60,
}
_ICONS = (
    "L2", "R2", "L1", "R1", "Circle", "Triangle", "X", "Square",
    "Icon08", "Icon09", "Icon0A", "Icon0B", "CrossTop", "CrossRight",
    "CrossDown", "CrossLeft", "Icon10", "Icon11", "Icon12", "Icon13",
    "Icon14", "Icon15", "Icon16", "Icon17", "Select", "Icon19", "Icon1A",
    "START", "Icon1C", "Icon1D", "Icon1E", "Icon1F", "MagicJunctioned",
    "LimitBreakArrow", "JunctionAbility", "CommandAbility", "Icon24",
    "CharacterAbility", "PartyAbility", "GFAbility", "MenuAbility", "Fire",
    "Ice", "Thunder", "Earth", "PoisonType", "Wind", "Water", "Holy",
    "Death", "PoisonStatus", "Petrify", "Darkness", "Silence", "Berserk",
    "Zombie", "Sleep", "Slow", "Stop", "Curse", "Confuse", "Drain",
)
_LOCATIONS = (
    "Galbadia", "Esthar", "Balamb", "Dollet", "Timber", "Trabia", "Centra",
    "Horizon", "East Academy", "Desert Prison", "Trabia Garden", "Lunar Base",
    "Shumi Village", "Deling City", "Balamb Garden", "East Academy Station",
    "Dolet Station", "Desert Prison Station", "Lunar Gate", "Restores", "status",
    "learns", "ability", "Magic", "Refine", "Junctions", "Raises", "command",
    "Magazine", "Ultimecia Castle",
)
_SPECIAL = {0x20: "CurrentSeedTestLevel", 0x22: "NextSeedTestLevel",
            0x23: "CardReceived", 0x26: "SeedRank"}

_RAW_TOKEN = re.compile(r"\{x([0-9A-Fa-f]{2})\}")


def decode(data: bytes) -> str:
    """Decode one string payload without its null terminator."""
    out: list[str] = []
    index = 0
    while index < len(data):
        value = data[index]
        if value == 0x02:
            out.append("\n")
            index += 1
            continue
        if value >= 0xE8:
            out.append(_COMPRESSED[value - 0xE8])
            index += 1
            continue
        if value in (0x03, 0x05, 0x0A, 0x0E) and index + 1 < len(data):
            parameter = data[index + 1]
            if value == 0x03:
                name = next((name for name, code in _CHARACTER_CODES.items()
                             if code == parameter), None)
            elif value == 0x05:
                slot = parameter - 0x20
                name = _ICONS[slot] if 0 <= slot < len(_ICONS) else None
            elif value == 0x0A:
                name = _SPECIAL.get(parameter)
            else:
                slot = parameter - 0x20
                name = _LOCATIONS[slot] if 0 <= slot < len(_LOCATIONS) else None
            if name is not None:
                out.append("{" + name + "}")
            else:
                out.extend((f"{{x{value:02X}}}", f"{{x{parameter:02X}}}"))
            index += 2
            continue
        glyph = _BYTE_TO_TEXT.get(value)
        out.append(glyph if glyph is not None else f"{{x{value:02X}}}")
        index += 1
    return "".join(out)


def encode(text: str, *, compress: bool = True) -> bytes:
    """Encode display text. Reject characters which FF8 cannot represent."""
    output = bytearray()
    index = 0
    named = {
        **{name: bytes((0x03, code)) for name, code in _CHARACTER_CODES.items()},
        **{name: bytes((0x05, 0x20 + slot)) for slot, name in enumerate(_ICONS)},
        **{name: bytes((0x0E, 0x20 + slot)) for slot, name in enumerate(_LOCATIONS)},
        **{name: bytes((0x0A, code)) for code, name in _SPECIAL.items()},
    }
    while index < len(text):
        if text[index] == "\n":
            output.append(0x02)
            index += 1
            continue
        if text[index] == "{":
            end = text.find("}", index + 1)
            if end < 0:
                raise ValueError("FF8 text has an opening brace without a closing brace")
            token = text[index + 1:end]
            raw = _RAW_TOKEN.fullmatch(text[index:end + 1])
            if raw:
                value = int(raw.group(1), 16)
                if value == 0:
                    raise ValueError("{x00} is the string terminator and cannot appear inside FF8 text")
                output.append(value)
            elif token in named:
                output.extend(named[token])
            else:
                raise ValueError(f"Unknown FF8 text token: {{{token}}}")
            index = end + 1
            continue
        pair = text[index:index + 2]
        if compress and len(pair) == 2 and pair in _COMPRESSED:
            output.append(0xE8 + _COMPRESSED.index(pair))
            index += 2
            continue
        value = _TEXT_TO_BYTE.get(text[index])
        if value is None:
            raise ValueError(f"Character {text[index]!r} is not available in the FF8 font")
        output.append(value)
        index += 1
    return bytes(output)


@dataclass(frozen=True)
class _Slot:
    record_id: int
    slot: int
    offset_position: int
    text_offset: int


def _split_sections(data: bytes, section_count: int) -> tuple[list[bytes], list[int]]:
    if len(data) < (section_count + 1) * 4:
        raise ValueError("kernel.bin is shorter than its section header")
    stored_count = int.from_bytes(data[:4], "little")
    if stored_count != section_count:
        raise ValueError(f"kernel.bin has {stored_count} sections; expected {section_count}")
    starts = [int.from_bytes(data[index * 4:index * 4 + 4], "little")
              for index in range(1, section_count + 1)]
    if starts[0] < (section_count + 1) * 4 or starts != sorted(starts) or starts[-1] > len(data):
        raise ValueError("kernel.bin has an invalid section-offset table")
    ends = starts[1:] + [len(data)]
    return [data[start:end] for start, end in zip(starts, ends)], starts


def _slots(data_section: bytes, definition: dict) -> list[_Slot]:
    expected_count = int(definition["number_sub_section"])
    size = int(definition["sub_section_size"])
    per_record = int(definition["sub_section_nb_text_offset"])
    if len(data_section) % size:
        raise ValueError(f"Linked kernel section {definition['id']} has an unexpected size")
    count = len(data_section) // size
    if count != expected_count and (not definition.get("growable") or count < expected_count):
        raise ValueError(f"Linked kernel section {definition['id']} has an unexpected size")
    result = []
    for record_id in range(count):
        for slot in range(per_record):
            position = record_id * size + slot * 2
            result.append(_Slot(record_id, slot, position,
                                int.from_bytes(data_section[position:position + 2], "little")))
    return result


def _strings(text_section: bytes, slots: list[_Slot]) -> dict[int, bytes]:
    active = [slot.text_offset for slot in slots if slot.text_offset != UNUSED_OFFSET]
    if len(active) != len(set(active)):
        raise ValueError("Aliased kernel text offsets are not safe to rebuild")
    result: dict[int, bytes] = {}
    covered = 0
    for offset in sorted(active):
        if offset != covered or offset >= len(text_section):
            raise ValueError("Kernel text has a gap, overlap, or invalid offset")
        end = text_section.find(b"\0", offset)
        if end < 0:
            raise ValueError("Kernel text string has no null terminator")
        result[offset] = text_section[offset:end]
        covered = end + 1
    # kernel.bin section starts are four-byte aligned.  The shipped file pads a
    # text section with zeroes after its final terminated string when needed.
    # FF8UE rebuilds the section offsets after text changes; accepting only this
    # bounded alignment padding keeps unknown trailing data from being erased.
    padding = text_section[covered:]
    if len(text_section) % 4 or len(padding) > 3 or any(padding):
        raise ValueError("Kernel text has unreferenced trailing bytes")
    return result


def rows(data: bytes, sections: dict[int, dict]) -> dict:
    payloads, _ = _split_sections(data, len(sections))
    result = []
    section_rows = []
    row_id = 0
    for text_id in range(TEXT_SECTION_FIRST, TEXT_SECTION_LAST + 1):
        text_definition = sections[text_id]
        data_id = int(text_definition["section_id_data_linked"])
        data_definition = sections[data_id]
        slots = _slots(payloads[data_id - 1], data_definition)
        strings = _strings(payloads[text_id - 1], slots)
        active_count = 0
        for entry in slots:
            if entry.text_offset == UNUSED_OFFSET:
                continue
            role = "Name" if entry.slot == 0 else "Description" if entry.slot == 1 else f"Text {entry.slot + 1}"
            result.append({
                "id": row_id,
                "sectionId": text_id,
                "section": text_definition["section_name"].removesuffix(" section"),
                "linkedSectionId": data_id,
                "recordId": entry.record_id,
                "slot": entry.slot,
                "role": role,
                "name": f"{text_definition['section_name'].removesuffix(' section')} #{entry.record_id} {role}",
                "value": decode(strings[entry.text_offset]),
            })
            row_id += 1
            active_count += 1
        section_rows.append({"id": text_id, "name": text_definition["section_name"],
                             "linkedSectionId": data_id, "entries": active_count})
    return {"rows": result, "sections": section_rows}


def apply_edits(data: bytes, sections: dict[int, dict], edits: list[dict]) -> tuple[bytes, int]:
    payloads, _ = _split_sections(data, len(sections))
    grouped: dict[int, dict[tuple[int, int], str]] = {}
    seen: set[tuple[int, int, int]] = set()
    for edit in edits:
        text_id = int(edit["sectionId"])
        record_id = int(edit["recordId"])
        slot = int(edit["slot"])
        key = (text_id, record_id, slot)
        if key in seen or not TEXT_SECTION_FIRST <= text_id <= TEXT_SECTION_LAST:
            raise ValueError("Invalid or duplicate kernel text edit")
        seen.add(key)
        grouped.setdefault(text_id, {})[(record_id, slot)] = str(edit.get("value", ""))

    changed = 0
    for text_id, replacements in grouped.items():
        text_definition = sections[text_id]
        if text_definition.get("type") != "text":
            raise ValueError(f"Kernel section {text_id} is not text")
        data_id = int(text_definition["section_id_data_linked"])
        data_definition = sections[data_id]
        data_section = bytearray(payloads[data_id - 1])
        slots = _slots(data_section, data_definition)
        by_key = {(entry.record_id, entry.slot): entry for entry in slots}
        if any(key not in by_key or by_key[key].text_offset == UNUSED_OFFSET for key in replacements):
            raise ValueError("Kernel text edit targets an unused or unknown offset")
        text_section = payloads[text_id - 1]
        strings = _strings(text_section, slots)
        rebuilt = bytearray()
        for entry in sorted((slot for slot in slots if slot.text_offset != UNUSED_OFFSET),
                            key=lambda slot: slot.text_offset):
            original = strings[entry.text_offset]
            value = replacements.get((entry.record_id, entry.slot))
            # Stat ability names go straight to the native glyph renderer,
            # which does not expand the dialogue's E8..FF pair codes.
            # Re-encode even an unchanged supplied name to repair older output.
            plain_stat_name = text_id == 44 and entry.slot == 0
            if value is not None and (value != decode(original) or plain_stat_name):
                encoded = encode(value, compress=not plain_stat_name)
                changed += encoded != original
            else:
                encoded = original
            if len(rebuilt) > 0xFFFE:
                raise ValueError("Kernel text section exceeds its 16-bit offset range")
            data_section[entry.offset_position:entry.offset_position + 2] = len(rebuilt).to_bytes(2, "little")
            rebuilt.extend(encoded)
            rebuilt.append(0)
        while len(rebuilt) % 4:
            rebuilt.append(0)
        if len(rebuilt) > 0xFFFF:
            raise ValueError("Kernel text section exceeds 65,535 bytes")
        payloads[data_id - 1] = bytes(data_section)
        payloads[text_id - 1] = bytes(rebuilt)

    header_size = (len(sections) + 1) * 4
    starts = []
    cursor = header_size
    for section in payloads:
        starts.append(cursor)
        cursor += len(section)
    header = len(sections).to_bytes(4, "little") + b"".join(
        start.to_bytes(4, "little") for start in starts)
    return header + b"".join(payloads), changed
