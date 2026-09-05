"""FF8 refine/crafting tables stored in menu/mngrp.bin.

The section locations, group boundaries, and eight-byte entry schema come from
FF8 Ultimate Editor revision 343d97e.  The five m00x tables pair fixed-size
binary recipe sections with fixed-size message sections.  Rebuilding text also
rebuilds every linked u16 text offset; unrelated bytes stay unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

from .kernel_text import decode, encode


@dataclass(frozen=True)
class Group:
    key: str
    name: str
    description: str
    count: int


@dataclass(frozen=True)
class Table:
    key: str
    name: str
    binary_offset: int
    binary_size: int
    message_offset: int
    message_size: int
    input_type: str
    output_type: str
    groups: tuple[Group, ...]

    @property
    def count(self) -> int:
        return sum(group.count for group in self.groups)


TABLES = (
    Table("m000", "Magic Refine", 0x21F000, 0x800, 0x221800, 0x1800, "item", "magic", (
        Group("t_mag_rf", "T Mag-RF", "Item to Thunder/Wind Magic", 7),
        Group("i_mag_rf", "I Mag-RF", "Item to Ice/Water Magic", 7),
        Group("f_mag_rf", "F Mag-RF", "Item to Fire/Flare Magic", 10),
        Group("l_mag_rf", "L Mag-RF", "Item to Life Magic", 21),
        Group("time_mag_rf", "Time Mag-RF", "Item to Time Magic", 14),
        Group("st_mag_rf", "ST Mag-RF", "Item to Status Magic", 17),
        Group("supt_mag_rf", "Supt Mag-RF", "Item to Support Magic", 20),
        Group("forbid_mag_rf", "Forbid Mag-RF", "Item to Forbidden Magic", 6),
    )),
    Table("m001", "Tool/Medicine Refine", 0x21F800, 0x800, 0x223000, 0x2000, "item", "item", (
        Group("recov_med_rf", "Recov Med-RF", "Item to Recovery Items", 9),
        Group("st_med_rf", "ST Med-RF", "Item to Status Removal Items", 12),
        Group("amo_rf", "Ammo-RF", "Item to Ammo", 16),
        Group("forbid_med_rf", "Forbid Med-RF", "Item to Forbidden Medicine", 20),
        Group("gfrecov_med_rf", "GFRecov Med-RF", "Item to GF Recovery Items", 12),
        Group("gfabl_med_rf", "GFAbl Med-RF", "Item to GF Ability Medicine", 42),
        Group("tool_rf", "Tool-RF", "Item to Tools", 32),
    )),
    Table("m002", "Magic Upgrade", 0x220000, 0x800, 0x225000, 0x800, "magic", "magic", (
        Group("mid_mag_rf", "Mid Mag-RF", "Low-level to mid-level Magic", 4),
        Group("high_mag_rf", "High Mag-RF", "Mid-level to high-level Magic", 6),
    )),
    Table("m003", "Med LV Up", 0x220800, 0x800, 0x225800, 0x800, "item", "item", (
        Group("med_lv_up", "Med LV Up", "Upgrade recovery items", 12),
    )),
    Table("m004", "Card Mod", 0x221000, 0x800, 0x226000, 0x1800, "card", "item", (
        Group("card_mod", "Card Mod", "Card to Items", 110),
    )),
)
BY_KEY = {table.key: table for table in TABLES}
ENTRY_SIZE = 8


def _bounds(data: bytes, table: Table) -> None:
    if table.binary_offset + table.binary_size > len(data) \
            or table.message_offset + table.message_size > len(data):
        raise ValueError(f"mngrp.bin is too short for refine table {table.key}")


def _table_rows(data: bytes, table: Table) -> list[dict]:
    _bounds(data, table)
    binary = data[table.binary_offset:table.binary_offset + table.binary_size]
    message = data[table.message_offset:table.message_offset + table.message_size]
    if any(binary[table.count * ENTRY_SIZE:]):
        raise ValueError(f"Refine table {table.key} has unsupported trailing data")
    offsets = [int.from_bytes(binary[index * ENTRY_SIZE:index * ENTRY_SIZE + 2], "little")
               for index in range(table.count)]
    if offsets != sorted(offsets) or len(offsets) != len(set(offsets)) \
            or offsets[0] != 0 or any(offset >= table.message_size for offset in offsets):
        raise ValueError(f"Refine table {table.key} has unsafe text offsets")
    rows = []
    group_index = 0
    group_start = 0
    for slot, offset in enumerate(offsets):
        while slot >= group_start + table.groups[group_index].count:
            group_start += table.groups[group_index].count
            group_index += 1
        following = offsets[slot + 1] if slot + 1 < len(offsets) else table.message_size
        terminator = message.find(b"\0", offset, following)
        if terminator < 0 or any(message[terminator + 1:following]):
            raise ValueError(f"Refine table {table.key} text {slot} is not bounded safely")
        position = slot * ENTRY_SIZE
        raw = binary[position:position + ENTRY_SIZE]
        group = table.groups[group_index]
        rows.append({
            "id": slot, "table": table.key, "group": group.key,
            "groupName": group.name, "groupDescription": group.description,
            "inputType": table.input_type, "outputType": table.output_type,
            "text": decode(message[offset:terminator]),
            "rawText": message[offset:terminator].hex(),
            "textOffset": offset, "outputQuantity": raw[2],
            "unknown": int.from_bytes(raw[3:5], "little"),
            "inputId": raw[5], "inputQuantity": raw[6], "outputId": raw[7],
        })
    return rows


def read(data: bytes) -> dict:
    return {"tables": [{"id": table.key, "name": table.name,
                         "inputType": table.input_type, "outputType": table.output_type,
                         "rows": _table_rows(data, table)} for table in TABLES]}


def apply_edits(data: bytes, edits: list[dict]) -> tuple[bytes, int]:
    grouped: dict[str, dict[int, dict]] = {}
    seen = set()
    allowed = {"text", "outputQuantity", "inputId", "inputQuantity", "outputId"}
    for edit in edits:
        table_key, slot = str(edit["table"]), int(edit["id"])
        key = (table_key, slot)
        if table_key not in BY_KEY or not 0 <= slot < BY_KEY[table_key].count or key in seen:
            raise ValueError(f"Invalid or duplicate refine recipe: {key}")
        unknown = set(edit) - {"table", "id"} - allowed
        if unknown:
            raise ValueError(f"Unsupported refine recipe fields: {sorted(unknown)}")
        seen.add(key)
        grouped.setdefault(table_key, {})[slot] = edit

    result = bytearray(data)
    changed = 0
    for table_key, replacements in grouped.items():
        table = BY_KEY[table_key]
        rows = _table_rows(data, table)
        values = []
        text_changed = False
        for row in rows:
            edit = replacements.get(row["id"], {})
            merged = {**row, **edit}
            for field in ("outputQuantity", "inputId", "inputQuantity", "outputId"):
                value = int(merged[field])
                if not 0 <= value <= 255:
                    raise ValueError(f"Refine {field} must be 0 to 255")
                merged[field] = value
            merged["text"] = str(merged["text"])
            if any(merged[field] != row[field] for field in allowed):
                changed += 1
            text_changed |= merged["text"] != row["text"]
            values.append(merged)

        binary = bytearray(data[table.binary_offset:table.binary_offset + table.binary_size])
        message = bytearray()
        for slot, row in enumerate(values):
            original = rows[slot]
            encoded = (encode(row["text"]) if row["text"] != original["text"]
                       else bytes.fromhex(original["rawText"]))
            if len(message) > 0xFFFF:
                raise ValueError(f"Refine table {table.key} text offset exceeds u16")
            position = slot * ENTRY_SIZE
            if text_changed:
                binary[position:position + 2] = len(message).to_bytes(2, "little")
            binary[position + 2] = row["outputQuantity"]
            binary[position + 5] = row["inputId"]
            binary[position + 6] = row["inputQuantity"]
            binary[position + 7] = row["outputId"]
            message.extend(encoded)
            message.append(0)
        if len(message) > table.message_size:
            raise ValueError(
                f"Refine table {table.key} text exceeds its fixed {table.message_size}-byte section")
        message.extend(b"\0" * (table.message_size - len(message)))
        result[table.binary_offset:table.binary_offset + table.binary_size] = binary
        if text_changed:
            result[table.message_offset:table.message_offset + table.message_size] = message
        else:
            # Offsets are unchanged when text is unchanged, so preserve the
            # complete message section rather than normalizing its zero tail.
            original_offsets = [row["textOffset"] for row in rows]
            rebuilt_offsets = [int.from_bytes(binary[i * ENTRY_SIZE:i * ENTRY_SIZE + 2], "little")
                               for i in range(table.count)]
            if rebuilt_offsets != original_offsets:
                raise ValueError("Refine text offsets changed without a text edit")
    return bytes(result), changed
