"""Read and write the proved Final Fantasy VII KERNEL.BIN record sections.

The container and record layouts follow the public MIT-licensed Elena reader
(Joshua Moon, 2019). The English text map and dictionary expansion follow the
permissively licensed ff7tools implementation (Christian Bauer). Both are
checked against the two locally installed English Steam releases. Lexeditor
writes only documented fields and preserves every unknown byte in each record.
"""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import os
from pathlib import Path
import struct
from typing import Any


TEXT_MAP_EN = tuple(
    " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_"
    "`abcdefghijklmnopqrstuvwxyz{|}~ ÄÅÇÉÑÖÜáàâäãåçéèêëíìîïñóòôöõúù"
    "ûü♥°¢£↔→♪ßα  ´¨≠ÆØ∞±≤≥¥µ∂ΣΠπ⌡ªºΩæø¿¡¬√ƒ≈∆«»… ÀÃÕŒœ"
    "–—“”‘’÷◊ÿŸ⁄ ‹›ﬁﬂ■‧‚„‰ÂÊÁËÈÍÎÏÌÓÔ ÒÚÛÙıˆ˜¯˘˙˚¸˝˛ˇ       "
)

TEXT_COMMANDS = {
    0xEA: "CHARACTER", 0xEB: "ITEM", 0xEC: "NUMBER", 0xED: "TARGET",
    0xEE: "PREVIOUS", 0xEF: "ATTACK", 0xF0: "TARGET2",
}


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    offset: int
    kind: str = "B"
    minimum: int = 0
    maximum: int = 255
    scale: int = 1


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    section: int
    text_name_section: int
    text_description_section: int
    record_size: int
    fields: tuple[Field, ...]


CATEGORIES = {
    category.key: category for category in (
        Category("items", "Items", 5, 20, 12, 28, (
            Field("cameraMovementId", "Camera movement ID", 0x08, "H", maximum=65535),
            Field("targetData", "Target flags", 0x0C),
            Field("attackEffectId", "Attack effect ID", 0x0D),
            Field("damageCalculationId", "Damage calculation ID", 0x0E),
            Field("attackPower", "Attack power", 0x0F),
            Field("conditionSubmenu", "Condition submenu", 0x10),
            Field("statusChange", "Status change", 0x11),
            Field("additionalEffects", "Additional effects", 0x12),
            Field("additionalEffectsModifier", "Effect modifier", 0x13),
            Field("statusFlags", "Status flags", 0x14, "I", maximum=0xFFFFFFFF),
            Field("elementFlags", "Element flags", 0x18, "H", maximum=0xFFFF),
        )),
        Category("weapons", "Weapons", 6, 21, 13, 44, (
            Field("targetData", "Target flags", 0x00),
            Field("damageCalculationId", "Damage calculation ID", 0x02),
            Field("attackStrength", "Attack strength", 0x04),
            Field("status", "Equipment status", 0x05),
            Field("growthRate", "Materia growth rate", 0x06),
            Field("criticalRate", "Critical rate", 0x07),
            Field("accuracyRate", "Accuracy rate", 0x08),
            Field("weaponModelId", "Weapon model ID", 0x09),
            Field("equipableBy", "Equipable-by flags", 0x0E, "H", maximum=0xFFFF),
            Field("attackElements", "Attack element flags", 0x10, "H", maximum=0xFFFF),
        )),
        Category("armor", "Armor", 7, 22, 14, 36, (
            Field("elementDamageModifier", "Element damage modifier", 0x01),
            Field("defense", "Defense", 0x02),
            Field("magicDefense", "Magic defense", 0x03),
            Field("evade", "Evade", 0x04),
            Field("magicEvade", "Magic evade", 0x05),
            Field("status", "Equipment status", 0x06),
            Field("growthRate", "Materia growth rate", 0x11),
            Field("equipableBy", "Equipable-by flags", 0x12, "H", maximum=0xFFFF),
            Field("elementalDefense", "Element defense flags", 0x14, "H", maximum=0xFFFF),
        )),
        Category("accessories", "Accessories", 8, 23, 15, 16, (
            Field("boostedStat1", "Boosted stat 1", 0x00),
            Field("boostedStat2", "Boosted stat 2", 0x01),
            Field("boostedStat1Bonus", "Stat 1 bonus", 0x02),
            Field("boostedStat2Bonus", "Stat 2 bonus", 0x03),
            Field("elementDamageModifier", "Element damage modifier", 0x04),
            Field("specialEffect", "Special effect", 0x05),
            Field("elementalDefense", "Element defense flags", 0x06, "H", maximum=0xFFFF),
            Field("statusDefense", "Status defense flags", 0x08, "I", maximum=0xFFFFFFFF),
            Field("equipableBy", "Equipable-by flags", 0x0C, "H", maximum=0xFFFF),
        )),
        Category("materia", "Materia", 9, 24, 16, 20, (
            Field("level2Ap", "Level 2 AP", 0x00, "H", maximum=6_553_500, scale=100),
            Field("level3Ap", "Level 3 AP", 0x02, "H", maximum=6_553_500, scale=100),
            Field("level4Ap", "Level 4 AP", 0x04, "H", maximum=6_553_500, scale=100),
            Field("level5Ap", "Level 5 AP", 0x06, "H", maximum=6_553_500, scale=100),
            Field("equipEffect", "Equip effect", 0x08),
            Field("statusFlags", "Status flags", 0x09, "3", maximum=0xFFFFFF),
            Field("element", "Element", 0x0C),
            Field("materiaType", "Materia type byte", 0x0D),
            Field("attribute1", "Attribute 1", 0x0E),
            Field("attribute2", "Attribute 2", 0x0F),
            Field("attribute3", "Attribute 3", 0x10),
            Field("attribute4", "Attribute 4", 0x11),
            Field("attribute5", "Attribute 5", 0x12),
            Field("attribute6", "Attribute 6", 0x13),
        )),
    )
}


def _read_field(data: bytes | bytearray, field: Field) -> int:
    if field.kind == "3":
        value = int.from_bytes(data[field.offset:field.offset + 3], "little")
    else:
        value = struct.unpack_from("<" + field.kind, data, field.offset)[0]
    return value * field.scale


def _write_field(data: bytearray, field: Field, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field.label} must be an integer")
    if value < field.minimum or value > field.maximum:
        raise ValueError(f"{field.label} must be between {field.minimum} and {field.maximum}")
    if value % field.scale:
        raise ValueError(f"{field.label} must be a multiple of {field.scale}")
    stored = value // field.scale
    if field.kind == "3":
        data[field.offset:field.offset + 3] = stored.to_bytes(3, "little")
    else:
        struct.pack_into("<" + field.kind, data, field.offset, stored)


def _decode_text(raw: bytes) -> str:
    result: list[str] = []
    index = 0
    while index < len(raw):
        value = raw[index]
        if value == 0xFF:
            break
        if value == 0xF8:
            result.append("{ALERT}")
            index += 2
            continue
        if value == 0xE6:
            result.append("{THIRTEEN}")
            index += 1
            continue
        if value in TEXT_COMMANDS:
            arguments = raw[index + 1:index + 3]
            suffix = " ".join(f"{byte:02X}" for byte in arguments)
            result.append("{" + TEXT_COMMANDS[value] + (" " + suffix if suffix else "") + "}")
            index += 3
            continue
        if value == 0xF8 and index + 1 < len(raw):
            result.append(f"{{COLOR {raw[index + 1]:02X}}}")
            index += 2
            continue
        result.append(TEXT_MAP_EN[value] if value < 0xE7 and value < len(TEXT_MAP_EN) else "")
        index += 1
    return "".join(result).strip()


def _text_section(data: bytes) -> list[str]:
    if len(data) < 2:
        return []
    first_address = struct.unpack_from("<H", data, 0)[0]
    if first_address < 2 or first_address > len(data) or first_address % 2:
        raise ValueError("Invalid FF7 text pointer table")
    addresses = struct.unpack_from("<" + "H" * (first_address // 2), data, 0)
    def extract(start: int, limit: int, depth: int = 0) -> tuple[bytes, bool]:
        if depth > 32:
            raise ValueError("FF7 text dictionary recursion is too deep")
        output = bytearray()
        index = start
        while index < limit:
            value = data[index]
            index += 1
            if value == 0xF9:
                if index >= limit:
                    raise ValueError("FF7 text dictionary reference is truncated")
                argument = data[index]
                index += 1
                length = (argument >> 6) * 2 + 4
                reference = index - (argument & 0x3F) - 3
                if reference < 0 or reference >= index:
                    raise ValueError("FF7 text dictionary reference is invalid")
                expanded, ended = extract(reference, min(reference + length, len(data)), depth + 1)
                output.extend(expanded)
                if ended:
                    return bytes(output), True
            elif value in TEXT_COMMANDS:
                if index + 1 >= limit:
                    raise ValueError("FF7 text variable is truncated")
                output.append(value)
                output.extend(data[index:index + 2])
                index += 2
            elif value == 0xF8:
                if index >= limit:
                    raise ValueError("FF7 text color command is truncated")
                output.extend((value, data[index]))
                index += 1
            else:
                output.append(value)
                if value == 0xFF:
                    return bytes(output), True
        return bytes(output), False

    result = []
    for address in addresses:
        if address >= len(data):
            raise ValueError("FF7 text pointer leaves its section")
        raw, ended = extract(address, len(data))
        if not ended:
            raise ValueError("FF7 text string has no terminator")
        result.append(_decode_text(raw))
    return result


class Kernel:
    """A lossless KERNEL.BIN container with bounded field updates."""

    def __init__(self, path: Path):
        self.path = path
        self.original = path.read_bytes()
        self.sections: list[bytearray] = []
        self.file_types: list[int] = []
        offset = 0
        for section_index in range(27):
            if offset + 6 > len(self.original):
                raise ValueError(f"KERNEL.BIN ends before section {section_index + 1}")
            compressed_size, expected_size, file_type = struct.unpack_from("<HHH", self.original, offset)
            end = offset + 6 + compressed_size
            if end > len(self.original):
                raise ValueError(f"KERNEL.BIN section {section_index + 1} is truncated")
            raw = gzip.decompress(self.original[offset + 6:end])
            if len(raw) != expected_size:
                raise ValueError(f"KERNEL.BIN section {section_index + 1} has the wrong size")
            self.sections.append(bytearray(raw))
            self.file_types.append(file_type)
            offset = end
        self.trailer = self.original[offset:]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.original).hexdigest().upper()

    def records(self, category_key: str) -> list[dict[str, Any]]:
        category = CATEGORIES[category_key]
        section = self.sections[category.section - 1]
        if len(section) % category.record_size:
            raise ValueError(f"{category.label} section does not contain whole records")
        names = _text_section(self.sections[category.text_name_section - 1])
        descriptions = _text_section(self.sections[category.text_description_section - 1])
        count = len(section) // category.record_size
        if len(names) < count or len(descriptions) < count:
            raise ValueError(f"{category.label} text count does not match its records")
        result = []
        for record_index in range(count):
            start = record_index * category.record_size
            record = section[start:start + category.record_size]
            values = {field.key: _read_field(record, field) for field in category.fields}
            result.append({
                "id": record_index, "name": names[record_index] or f"{category.label} {record_index}",
                "description": descriptions[record_index], "values": values,
            })
        return result

    def apply(self, category_key: str, records: list[dict[str, Any]]) -> None:
        category = CATEGORIES[category_key]
        section = self.sections[category.section - 1]
        expected_count = len(section) // category.record_size
        if len(records) != expected_count:
            raise ValueError(f"{category.label} must contain exactly {expected_count} records")
        fields = {field.key: field for field in category.fields}
        seen: set[int] = set()
        for record in records:
            record_index = record.get("id")
            if isinstance(record_index, bool) or not isinstance(record_index, int):
                raise ValueError(f"{category.label} record ID must be an integer")
            if record_index < 0 or record_index >= expected_count or record_index in seen:
                raise ValueError(f"Invalid or duplicate {category.label} record ID {record_index}")
            seen.add(record_index)
            values = record.get("values")
            if not isinstance(values, dict) or set(values) != set(fields):
                raise ValueError(f"{category.label} record {record_index} has an invalid field set")
            start = record_index * category.record_size
            current = bytearray(section[start:start + category.record_size])
            for key, field in fields.items():
                _write_field(current, field, values[key])
            section[start:start + category.record_size] = current

    def to_bytes(self) -> bytes:
        output = bytearray()
        for raw, file_type in zip(self.sections, self.file_types):
            compressed = gzip.compress(bytes(raw), compresslevel=9, mtime=0)
            if len(compressed) > 0xFFFF or len(raw) > 0xFFFF:
                raise ValueError("A KERNEL.BIN section exceeds the 16-bit container limit")
            output.extend(struct.pack("<HHH", len(compressed), len(raw), file_type))
            output.extend(compressed)
        output.extend(self.trailer)
        return bytes(output)

    def save(self, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".tmp")
        temp.write_bytes(self.to_bytes())
        os.replace(temp, target)


def resolve_kernel(game_root: Path) -> tuple[Path, Path]:
    """Return the installed source and its product-relative output path."""
    candidates = (
        Path("ff7/workingdir/data/lang-en/kernel/kernel.bin"),
        Path("data/lang-en/kernel/KERNEL.BIN"),
    )
    found = [(game_root / relative, relative) for relative in candidates if (game_root / relative).is_file()]
    if len(found) != 1:
        raise FileNotFoundError(f"Expected one supported English KERNEL.BIN under {game_root}")
    return found[0]


def category_metadata() -> list[dict[str, Any]]:
    return [{
        "id": category.key,
        "label": category.label,
        "fields": [{
            "key": field.key, "label": field.label, "dataType": "int",
            "minimum": field.minimum, "maximum": field.maximum, "step": field.scale,
        } for field in category.fields],
    } for category in CATEGORIES.values()]
