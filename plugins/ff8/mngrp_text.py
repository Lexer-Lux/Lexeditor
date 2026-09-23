"""Fixed-size FF8 ``mngrp.bin`` string-section editor.

The supported section ids, offsets, sizes, and names come from FF8 Ultimate
Editor's ``mngrp_bin_data.json``. Its ``SectionString`` reader proves the
layout: u16 slot count, u16 offsets from the section start, then null-terminated
FF8 text. Only ``mngrp_string`` sections are exposed here. Other menu data,
images, text-box maps, and scripts stay opaque.
"""

from __future__ import annotations

from dataclasses import dataclass

from .kernel_text import decode, encode


@dataclass(frozen=True)
class Section:
    id: int
    offset: int
    size: int
    name: str


SECTIONS = [
    Section(38, 0x1A8000, 0x3000, "Book text"),
    Section(39, 0x1AB000, 0x0800, "Battle tutorial"),
    Section(40, 0x1AB800, 0x1000, "Card rules + Icon"),
    Section(41, 0x1AC800, 0x1000, "Chocobo tutorial"),
    Section(42, 0x1AD800, 0x0800, "Test seed general"),
    *[Section(section_id, 0x1AE000 + (section_id - 43) * 0x800, 0x0800,
              f"Test seed {section_id - 42}") for section_id in range(43, 74)],
    Section(81, 0x1D6000, 0x1000, "Junction tutorial"),
    Section(82, 0x1D7000, 0x0800, "Magic junction tutorial"),
    Section(83, 0x1D7800, 0x0800, "Elemental junction tutorial"),
    Section(84, 0x1D8000, 0x0800, "Status junction tutorial"),
    Section(85, 0x1D8800, 0x0800, "GF tutorial"),
    Section(86, 0x1D9000, 0x0800, "Squall limit break tutorial"),
    Section(87, 0x1D9800, 0x0800, "Zell limit break tutorial"),
    Section(88, 0x1DA000, 0x0800, "Rinoa limit break tutorial"),
    Section(116, 0x227800, 0x0800, "Character switch tutorial"),
]
BY_ID = {section.id: section for section in SECTIONS}


def _entries(data: bytes, section: Section) -> list[dict]:
    end = section.offset + section.size
    if end > len(data):
        raise ValueError(f"mngrp.bin is too short for section {section.id}")
    raw = data[section.offset:end]
    count = int.from_bytes(raw[:2], "little")
    header_size = 2 + count * 2
    if count == 0 or header_size > section.size:
        raise ValueError(f"mngrp.bin section {section.id} has an invalid offset table")
    offsets = [int.from_bytes(raw[2 + slot * 2:4 + slot * 2], "little")
               for slot in range(count)]
    active = [offset for offset in offsets if offset]
    if (active != sorted(active) or len(active) != len(set(active))
            or any(offset < header_size or offset >= section.size for offset in active)):
        raise ValueError(f"mngrp.bin section {section.id} has unsafe text offsets")
    rows = []
    has_literal_prefix = section.name.startswith("Test seed")
    for slot, offset in enumerate(offsets):
        if offset == 0:
            continue
        following = next((value for value in offsets[slot + 1:] if value), section.size)
        text_start = offset + (1 if has_literal_prefix else 0)
        terminator = raw.find(b"\0", text_start, following)
        if terminator < 0 or any(raw[terminator + 1:following]):
            raise ValueError(f"mngrp.bin section {section.id} string {slot} is not bounded safely")
        rows.append({"slot": slot, "offset": offset,
                     "prefix": raw[offset:text_start],
                     "raw": raw[text_start:terminator],
                     "value": decode(raw[text_start:terminator])})
    if active:
        last = rows[-1]
        terminator = raw.find(b"\0", last["offset"] + len(last["prefix"]))
        if terminator < 0 or any(raw[terminator + 1:]):
            raise ValueError(f"mngrp.bin section {section.id} has unowned trailing data")
    return rows


def rows(data: bytes) -> dict:
    result = []
    section_rows = []
    for section in SECTIONS:
        entries = _entries(data, section)
        for entry in entries:
            result.append({
                "id": f"mngrp:{section.id}:{entry['slot']}",
                "source": "mngrp", "sourceLabel": "Menu text",
                "sectionId": section.id, "section": section.name,
                "recordId": entry["slot"], "slot": 0, "role": "Text",
                "name": f"{section.name} #{entry['slot']}",
                "value": entry["value"],
            })
        section_rows.append({"id": section.id, "source": "mngrp",
                             "name": section.name, "entries": len(entries)})
    return {"rows": result, "sections": section_rows}


def apply_edits(data: bytes, edits: list[dict]) -> tuple[bytes, int]:
    grouped: dict[int, dict[int, str]] = {}
    seen: set[tuple[int, int]] = set()
    for edit in edits:
        if str(edit.get("source", "mngrp")) != "mngrp":
            raise ValueError("A menu-text edit has the wrong source")
        section_id, slot = int(edit["sectionId"]), int(edit["recordId"])
        key = (section_id, slot)
        if key in seen or section_id not in BY_ID:
            raise ValueError("Invalid or duplicate mngrp.bin text edit")
        seen.add(key)
        grouped.setdefault(section_id, {})[slot] = str(edit.get("value", ""))

    output = bytearray(data)
    changed = 0
    for section_id, replacements in grouped.items():
        section = BY_ID[section_id]
        original_entries = _entries(data, section)
        by_slot = {entry["slot"]: entry for entry in original_entries}
        if any(slot not in by_slot for slot in replacements):
            raise ValueError("mngrp.bin text edit targets an unused or unknown slot")
        changed_here = {
            slot: value for slot, value in replacements.items()
            if value != by_slot[slot]["value"]
        }
        if not changed_here:
            continue
        raw = data[section.offset:section.offset + section.size]
        count = int.from_bytes(raw[:2], "little")
        old_offsets = [int.from_bytes(raw[2 + slot * 2:4 + slot * 2], "little")
                       for slot in range(count)]
        rebuilt = bytearray(raw[:2] + b"\0" * (count * 2))
        for slot, old_offset in enumerate(old_offsets):
            if old_offset == 0:
                continue
            if len(rebuilt) > 0xFFFF:
                raise ValueError(f"mngrp.bin section {section_id} exceeds its u16 offset range")
            rebuilt[2 + slot * 2:4 + slot * 2] = len(rebuilt).to_bytes(2, "little")
            rebuilt.extend(by_slot[slot]["prefix"])
            rebuilt.extend(encode(changed_here.get(slot, by_slot[slot]["value"])))
            rebuilt.append(0)
        if len(rebuilt) > section.size:
            raise ValueError(
                f"mngrp.bin section {section_id} text exceeds its fixed {section.size}-byte size")
        rebuilt.extend(b"\0" * (section.size - len(rebuilt)))
        output[section.offset:section.offset + section.size] = rebuilt
        changed += len(changed_here)
    return bytes(output), changed
