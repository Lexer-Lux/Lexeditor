"""Safe readers and writers for the first FF8 gameplay-data integration."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile

from . import paths, runtime_layout
from . import encounters as encounter_format
from . import enemy_ai as enemy_ai_format
from . import enemy_battle_text as enemy_battle_text_format
from . import enemy_tables as enemy_table_format
from . import executable_text
from . import init_data as init_format
from . import kernel_text
from . import menu_items as menu_item_format
from . import mngrp_text
from . import refine_tables
from . import scan_text
from .game_icons import item_icon_id, ability_identity


SCHEMA_ROOT = Path(__file__).resolve().parent / "schema"
SHOP_NAMES = [
    "Timber Pet Shop", "Balamb Shop", "Dollet Shop", "Timber Shop", "Deling City Shop",
    "Winhill Shop", "FH Shop", "Trabia Shop - Unused", "Esthar Shop (Cloud's Shop)",
    "Balamb Shop (Laguna) - Unused", "Dollet Shop (Laguna) - Unused",
    "Timber Shop (Laguna) - Unused", "Deling City Shop (Laguna) - Unused",
    "Winhill Shop (Laguna)", "FH Shop (Laguna) - Unused", "Trabia Shop (Laguna) - Unused",
    "Man from Garden", "Esthar Pet Shop", "Esthar Book Store", "Esthar Shop!!!",
]
FILE_LOCATIONS = {
    "kernel.bin": (Path("kernel.bin"), Path("main/kernel.bin")),
    "init.out": (Path("init.out"), Path("main/init.out")),
    "price.bin": (Path("menu/price.bin"), Path("menu/price.bin")),
    "shop.bin": (Path("menu/shop.bin"), Path("menu/shop.bin")),
    "mwepon.bin": (Path("menu/mwepon.bin"), Path("menu/mwepon.bin")),
    "mitem.bin": (Path("menu/mitem.bin"), Path("menu/mitem.bin")),
    "mngrp.bin": (Path("menu/mngrp.bin"), Path("menu/mngrp.bin")),
    "scene.out": (Path("battle/scene.out"), Path("battle/scene.out")),
}


def _json(name: str):
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


ITEMS = _json("item.json")["items"]
ITEM_NAMES = {row["id"]: row["name"] for row in ITEMS}
WEAPONS = _json("weapon.json")["weapons"]
MAGIC = _json("magic.json")["magic"]
GFORCES = _json("gforce.json")["gforce"]
MONSTERS = _json("monster.json")["monster"]
SECTIONS = {row["id"]: row for row in _json("kernel_bin_data.json")["sections"]}
SECTION_FIELDS = {int(key): value for key, value in _json("kernel_section_fields.json").items()}
LOOKUPS = _json("kernel_lookups.json")
CHARACTERS = [
    {"id": int(row["value"]), "name": row["name"]}
    for row in LOOKUPS["weapon_character"]["entries"]
]
INIT_ABILITIES = [
    {"id": int(row.get("value", row.get("id", 0))), "name": row["name"]}
    for row in LOOKUPS["junctionable_ability"]["entries"]
    if int(row.get("value", row.get("id", 0))) != 0
]


def item_choices() -> list[dict]:
    """Return item identities with their installed-game menu-type icons."""
    return [{**row, "iconId": item_icon_id(row["id"])} for row in ITEMS]

# FF8 Ultimate Editor: FF8GameData.monsterdata.AIData.SECTION_INFO_STAT_*.
# These fields all live in the fixed section-7 information block. Keeping the
# definitions here small avoids rebuilding any model, texture, animation, or AI
# section when Lexeditor changes gameplay data.
ENEMY_FIELDS = [
    *[
        {"name": f"{stat}_{suffix.casefold()}", "label": f"{stat.upper()} curve {suffix}",
         "group": "Stat curves", "offset": offset + index, "size": 1, "byteorder": "big",
         "minimum": 0, "maximum": 255,
         "help": "One of the four coefficients used by FF8 to scale this stat with enemy level."}
        for stat, offset in (("hp", 0x18), ("str", 0x1C), ("vit", 0x20),
                             ("mag", 0x24), ("spr", 0x28), ("spd", 0x2C), ("eva", 0x30))
        for index, suffix in enumerate("ABCD")
    ],
    {"name": "medium_level", "label": "Medium level starts", "group": "Levels", "offset": 0xF4,
     "size": 1, "byteorder": "big", "minimum": 0, "maximum": 100,
     "help": "The first enemy level that uses the medium ability, Draw, Mug, and drop tables."},
    {"name": "high_level", "label": "High level starts", "group": "Levels", "offset": 0xF5,
     "size": 1, "byteorder": "big", "minimum": 0, "maximum": 100,
     "help": "The first enemy level that uses the high ability, Draw, Mug, and drop tables."},
    {"name": "zombie", "label": "Zombie", "group": "Properties", "offset": 0xF7,
     "size": 1, "byteorder": "little", "mask": 0x01, "control": "boolean",
     "help": "The enemy has the intrinsic Zombie property."},
    {"name": "flying", "label": "Flying", "group": "Properties", "offset": 0xF7,
     "size": 1, "byteorder": "little", "mask": 0x02, "control": "boolean",
     "help": "The enemy has intrinsic Float. Battle status handling preserves the Float flag, so effects cannot remove it; attacks that reject Float targets react to the same status elsewhere."},
    {"name": "hidden_hp", "label": "Hide HP", "group": "Properties", "offset": 0xF7,
     "size": 1, "byteorder": "little", "mask": 0x10, "control": "boolean",
     "help": "Scan does not show the enemy's HP."},
    {"name": "auto_reflect", "label": "Auto-Reflect", "group": "Properties", "offset": 0xF7,
     "size": 1, "byteorder": "little", "mask": 0x20, "control": "boolean",
     "help": "The enemy starts battle with permanent Reflect."},
    {"name": "auto_shell", "label": "Auto-Shell", "group": "Properties", "offset": 0xF7,
     "size": 1, "byteorder": "little", "mask": 0x40, "control": "boolean",
     "help": "The enemy starts battle with permanent Shell."},
    {"name": "auto_protect", "label": "Auto-Protect", "group": "Properties", "offset": 0xF7,
     "size": 1, "byteorder": "little", "mask": 0x80, "control": "boolean",
     "help": "The enemy starts battle with permanent Protect."},
    {"name": "surprise_immunity", "label": "Surprise immunity", "group": "Properties", "offset": 0xFE,
     "size": 1, "byteorder": "little", "mask": 0x04, "control": "boolean",
     "help": "The party cannot begin this encounter with a surprise attack against this enemy."},
    {"name": "diablos_misses", "label": "Diablos misses", "group": "Properties", "offset": 0xFE,
     "size": 1, "byteorder": "little", "mask": 0x40, "control": "boolean",
     "help": "Diablos cannot damage this enemy."},
    {"name": "always_card", "label": "Always yields a card", "group": "Properties", "offset": 0xFE,
     "size": 1, "byteorder": "little", "mask": 0x80, "control": "boolean",
     "help": "Card conversion always succeeds when the enemy can become a card."},
    {"name": "extra_xp", "label": "Extra XP", "group": "Rewards", "offset": 0x100,
     "size": 2, "byteorder": "little", "minimum": 0, "maximum": 65535,
     "help": "The fixed XP amount added to the enemy's level-based XP reward."},
    {"name": "xp", "label": "XP", "group": "Rewards", "offset": 0x102,
     "size": 2, "byteorder": "little", "minimum": 0, "maximum": 65535,
     "help": "The coefficient used by the enemy's level-based XP reward."},
    {"name": "mug_rate", "label": "Mug rate", "group": "Rewards", "offset": 0x14C,
     "size": 1, "byteorder": "big", "minimum": 0, "maximum": 100, "control": "percent",
     "help": "The base chance that Mug succeeds."},
    {"name": "drop_rate", "label": "Drop rate", "group": "Rewards", "offset": 0x14D,
     "size": 1, "byteorder": "big", "minimum": 0, "maximum": 100, "control": "percent",
     "help": "The base chance that the enemy leaves an item after battle."},
    {"name": "ap", "label": "AP", "group": "Rewards", "offset": 0x14F,
     "size": 1, "byteorder": "big", "minimum": 0, "maximum": 255,
     "help": "The Ability Points awarded after battle."},
]
ENEMY_FIELD_MAP = {field["name"]: field for field in ENEMY_FIELDS}


def reference_roots() -> list[dict]:
    roots = []
    parent = paths.PROJECT_ROOT / "references"
    if not parent.is_dir():
        return roots
    for child in sorted((item for item in parent.iterdir() if item.is_dir()), key=lambda item: item.name.casefold()):
        roots.append({"id": child.name, "name": child.name, "path": str(child)})
    return roots


def _managed_root(dataset: str) -> Path | None:
    if not dataset.startswith("mod:"):
        return None
    return runtime_layout.root_for_mod(
        paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])


def source_path(name: str, dataset: str = "current") -> Path:
    direct_relative, baseline_relative = FILE_LOCATIONS[name]
    if dataset == "vanilla":
        return paths.BASELINE_ROOT / baseline_relative
    if dataset.startswith("reference:"):
        reference_id = dataset.partition(":")[2]
        reference = next((row for row in reference_roots() if row["id"] == reference_id), None)
        if reference is None:
            raise ValueError(f"Unknown reference dataset: {reference_id}")
        root = Path(reference["path"])
        candidates = (root / "direct" / direct_relative, root / direct_relative)
        target = next((candidate for candidate in candidates if candidate.is_file()), None)
        if target is None:
            raise ValueError(f"{name} is absent from reference {reference_id}")
        return target
    managed = _managed_root(dataset)
    if managed is not None:
        candidates = (managed / "direct" / direct_relative, managed / direct_relative)
        return next((candidate for candidate in candidates if candidate.is_file()),
                    paths.BASELINE_ROOT / baseline_relative)
    if dataset != "current":
        raise ValueError(f"Unknown dataset: {dataset}")
    override = paths.DIRECT_ROOT / direct_relative
    return override if override.is_file() else paths.BASELINE_ROOT / baseline_relative


def output_path(name: str) -> Path:
    return paths.DIRECT_ROOT / FILE_LOCATIONS[name][0]


def source_label(name: str) -> str:
    return "Project override" if output_path(name).is_file() else "Extracted baseline"


def _atomic_write(destination: Path, data: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(destination, destination.with_name(f"{destination.name}.{stamp}.bak"))
    handle, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, destination)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def item_rows(dataset: str = "current") -> dict:
    raw = source_path("price.bin", dataset).read_bytes()
    if len(raw) % 4:
        raise ValueError("price.bin has a partial item record")
    rows = []
    for item_id in range(len(raw) // 4):
        offset = item_id * 4
        buy = int.from_bytes(raw[offset:offset + 2], "little") * 10
        multiplier = raw[offset + 2]
        rows.append({
            "id": item_id,
            "name": ITEM_NAMES.get(item_id, f"Item {item_id}"),
            "iconId": item_icon_id(item_id),
            "buyPrice": buy,
            "sellMultiplier": multiplier,
            "sellPrice": round((buy / 20) * multiplier),
        })
    return {"rows": rows, "source": source_label("price.bin")}


def save_items(edits: list[dict]) -> dict:
    raw = bytearray(source_path("price.bin").read_bytes())
    changed = 0
    seen: set[int] = set()
    for edit in edits:
        item_id = int(edit["id"])
        if item_id in seen or not 0 <= item_id < len(raw) // 4:
            raise ValueError(f"Invalid or duplicate item id: {item_id}")
        seen.add(item_id)
        buy = int(edit["buyPrice"])
        multiplier = int(edit["sellMultiplier"])
        if buy < 0 or buy > 655350 or buy % 10:
            raise ValueError("Buy price must be 0 to 655350 in steps of 10")
        if not 0 <= multiplier <= 255:
            raise ValueError("Sell multiplier must be 0 to 255")
        offset = item_id * 4
        raw[offset:offset + 2] = (buy // 10).to_bytes(2, "little")
        raw[offset + 2] = multiplier
        changed += 1
    _atomic_write(output_path("price.bin"), bytes(raw))
    return {"saved": changed, "file": str(output_path("price.bin"))}


def menu_item_rows(dataset: str = "current") -> dict:
    payload = menu_item_format.read_rows(source_path("mitem.bin", dataset).read_bytes(), ITEM_NAMES, SCHEMA_ROOT)
    payload["parameterChoices"] = {
        "gf_target": [*GFORCES, {"id": 255, "name": "All GFs"}],
        "gf_ability": [
            {"id": int(row["value"]), "name": row["name"]}
            for row in LOOKUPS["junctionable_ability"]["entries"]],
        "quistis_limit": [
            {"id": int(row["bit"]), "name": row["name"]}
            for row in _json("limit_break.json")["quistis_blue_magic"]],
    }
    payload["source"] = source_label("mitem.bin")
    return payload


def save_menu_items(edits: list[dict]) -> dict:
    data, changed = menu_item_format.apply_edits(
        source_path("mitem.bin").read_bytes(), edits, SCHEMA_ROOT)
    destination = output_path("mitem.bin")
    _atomic_write(destination, data)
    return {"saved": changed, "file": str(destination)}


def shop_rows(dataset: str = "current") -> dict:
    raw = source_path("shop.bin", dataset).read_bytes()
    if len(raw) < 20 * 16 * 2:
        raise ValueError("shop.bin is too short")
    rows = []
    for shop_id, name in enumerate(SHOP_NAMES):
        slots = []
        for slot in range(16):
            offset = (shop_id * 16 + slot) * 2
            item_id, rarity = raw[offset], raw[offset + 1]
            slots.append({
                "slot": slot,
                "itemId": item_id,
                "itemName": ITEM_NAMES.get(item_id, f"Item {item_id}"),
                "rare": rarity == 0,
            })
        rows.append({"id": shop_id, "name": name, "slots": slots})
    return {"rows": rows, "items": item_choices(), "source": source_label("shop.bin")}


def save_shops(edits: list[dict]) -> dict:
    raw = bytearray(source_path("shop.bin").read_bytes())
    changed = 0
    seen: set[tuple[int, int]] = set()
    for edit in edits:
        shop_id, slot = int(edit["shopId"]), int(edit["slot"])
        item_id = int(edit["itemId"])
        key = (shop_id, slot)
        if key in seen or not 0 <= shop_id < 20 or not 0 <= slot < 16:
            raise ValueError("Invalid or duplicate shop slot")
        if item_id not in ITEM_NAMES:
            raise ValueError(f"Unknown item id: {item_id}")
        seen.add(key)
        offset = (shop_id * 16 + slot) * 2
        raw[offset] = item_id
        raw[offset + 1] = 0 if bool(edit["rare"]) else 255
        changed += 1
    _atomic_write(output_path("shop.bin"), bytes(raw))
    return {"saved": changed, "file": str(output_path("shop.bin"))}


def weapon_rows(dataset: str = "current") -> dict:
    raw = source_path("mwepon.bin", dataset).read_bytes()
    if len(raw) % 12:
        raise ValueError("mwepon.bin has a partial weapon record")
    kernel = kernel_rows(5, dataset)["rows"]
    rows = []
    for weapon_id in range(len(raw) // 12):
        offset = weapon_id * 12
        ingredients = [
            {"slot": slot, "itemId": raw[offset + 4 + slot * 2],
             "quantity": raw[offset + 5 + slot * 2]}
            for slot in range(4)
        ]
        rows.append({
            "id": weapon_id,
            "name": WEAPONS[weapon_id]["name"] if weapon_id < len(WEAPONS) else f"Weapon {weapon_id}",
            "upgradePrice": raw[offset + 3] * 10,
            "ingredients": ingredients,
            "fields": kernel[weapon_id]["fields"] if weapon_id < len(kernel) else [],
        })
    return {"rows": rows, "items": item_choices(), "source": {
        "recipe": source_label("mwepon.bin"), "stats": source_label("kernel.bin")}}


def save_weapons(edits: list[dict]) -> dict:
    raw = bytearray(source_path("mwepon.bin").read_bytes())
    changed = 0
    kernel_edits = []
    for edit in edits:
        weapon_id = int(edit["id"])
        if not 0 <= weapon_id < len(raw) // 12:
            raise ValueError(f"Invalid weapon id: {weapon_id}")
        price = int(edit["upgradePrice"])
        if not 0 <= price <= 2550 or price % 10:
            raise ValueError("Upgrade price must be 0 to 2550 in steps of 10")
        offset = weapon_id * 12
        raw[offset + 3] = price // 10
        ingredients = edit.get("ingredients", [])
        if len(ingredients) != 4:
            raise ValueError("A weapon recipe must have four slots")
        for slot, ingredient in enumerate(ingredients):
            item_id, quantity = int(ingredient["itemId"]), int(ingredient["quantity"])
            if (item_id not in ITEM_NAMES or
                    (item_id == 0 and quantity != 0) or
                    (item_id != 0 and not 1 <= quantity <= 255)):
                raise ValueError("Invalid weapon ingredient")
            raw[offset + 4 + slot * 2] = item_id
            raw[offset + 5 + slot * 2] = quantity
        for field in edit.get("fields", []):
            kernel_edits.append({"id": weapon_id, "field": field["field"], "value": field["value"]})
        changed += 1
    _atomic_write(output_path("mwepon.bin"), bytes(raw))
    if kernel_edits:
        save_kernel(5, kernel_edits)
    return {"saved": changed, "file": str(output_path("mwepon.bin"))}


# Kernel sections 12 to 18 hold the GF ability definitions, one section per
# category, and every record carries its AP-to-learn cost. They had no names,
# so every ability read as "Record N".
#
# The sections hold 20, 19, 19, 20, 5, 9 and 24 records: 116 in total, which is
# exactly the number of junctionable abilities. Their cumulative boundaries are
# 20, 39, 58, 78, 83, 92, 116, and 39, 58, 78, 83 and 92 are the very thresholds
# BuildGFAbilityList uses at 0x004ACDA4 to bucket an ability id into a category
# (0x27, 0x3A, 0x4E, 0x53, 0x5C). The sections are therefore the same list in
# the same order, so a record maps to its ability id by its position.
# Verified two ways: the sections hold 20, 19, 19, 20, 5, 9 and 24 records, so
# they start at 0, 20, 39, 58, 78, 83 and 92; and 39, 58, 78, 83 and 92 are the
# thresholds the game itself uses at 0x004ACDA4 to bucket an ability id into a
# category. The two agree exactly, so a record maps to its ability id by its
# position within its section.
ABILITY_SECTION_BASES = {12: 0, 13: 20, 14: 39, 15: 58, 16: 78, 17: 83, 18: 92}
ABILITY_SECTIONS = tuple(ABILITY_SECTION_BASES)

ABILITY_NAMES = {
    int(row.get("value", row.get("id", 0))): str(row["name"])
    for row in LOOKUPS["junctionable_ability"]["entries"]
}


def _record_name(section_id: int, record_id: int) -> str:
    rows = {2: MAGIC, 3: GFORCES, 5: WEAPONS, 7: CHARACTERS}.get(section_id)
    if rows and record_id < len(rows):
        return rows[record_id]["name"]
    if section_id in ABILITY_SECTIONS:
        identifier = ABILITY_SECTION_BASES[section_id] + record_id
        return ABILITY_NAMES.get(identifier, f"Ability {identifier}")
    if section_id == 8:
        return ITEM_NAMES.get(record_id, f"Item {record_id}")
    return f"Record {record_id}"


def _public_fields(section_id: int) -> list[dict]:
    result = []
    for field in SECTION_FIELDS.get(section_id, {}).get("fields", []):
        name = str(field.get("name", ""))
        label = str(field.get("label") or name.replace("_", " ").title())
        if (field.get("readonly") or name.startswith(("unknown", "padding", "unused")) or
                label.casefold() in {"padding", "unused"}):
            continue
        result.append(field)
    return result


def _display_fields(section_id: int) -> list[dict]:
    """Return editable fields plus named read-only values meant for the UI."""
    writable = {field["name"]: field for field in _public_fields(section_id)}
    result = []
    for field in SECTION_FIELDS.get(section_id, {}).get("fields", []):
        if field["name"] in writable:
            result.append(field)
        elif field.get("display_readonly"):
            result.append(field)
    return result


def _lookup_payload(field: dict) -> dict | None:
    lookup_name = field.get("lookup")
    lookup = LOOKUPS.get(lookup_name) if lookup_name else None
    if not lookup:
        return None
    entries = lookup.get("entries", [])
    if lookup_name == "junctionable_ability":
        entries = [{**entry, **ability_identity(entry.get("value", entry.get("id", -1)))} for entry in entries]
    return {"name": lookup_name, "type": lookup.get("type", "enum"), "entries": entries}


def kernel_rows(section_id: int, dataset: str = "current") -> dict:
    section = SECTIONS.get(section_id)
    if not section or section.get("type") != "data":
        raise ValueError(f"Unsupported kernel section: {section_id}")
    raw = source_path("kernel.bin", dataset).read_bytes()
    section_start = int.from_bytes(raw[section_id * 4:section_id * 4 + 4], "little")
    fields = _display_fields(section_id)
    rows = []
    for record_id in range(section["number_sub_section"]):
        base = section_start + record_id * section["sub_section_size"]
        values = []
        for field in fields:
            offset, size = int(field["offset"]), int(field["size"])
            value = int.from_bytes(raw[base + offset:base + offset + size], "little")
            if value == 0 and field.get("default_if_zero") is not None:
                value = int(field["default_if_zero"])
            if field.get("mask") is not None:
                value &= int(field["mask"])
            values.append({
                "field": field["name"],
                "label": field.get("label") or field["name"].replace("_", " ").title(),
                "group": field.get("group", "General"),
                "help": field.get("help", ""),
                "value": value,
                "minimum": int(field.get("minimum", 0)),
                "maximum": int(field.get("maximum", (1 << (size * 8)) - 1)),
                "mask": field.get("mask"),
                "lookup": _lookup_payload(field),
                "formula": field.get("formula"),
                "control": "boolean" if field.get("bool") else field.get("control"),
                "row": field.get("row"),
                "subgroup": field.get("subgroup"),
                "readonly": bool(field.get("readonly")),
            })
        rows.append({"id": record_id, "name": _record_name(section_id, record_id), "fields": values,
                     **(ability_identity(ABILITY_SECTION_BASES[section_id] + record_id)
                        if section_id in ABILITY_SECTIONS else {})})
    return {"section": section["section_name"], "rows": rows, "source": source_label("kernel.bin")}


def save_kernel(section_id: int, edits: list[dict]) -> dict:
    section = SECTIONS.get(section_id)
    if not section:
        raise ValueError(f"Unsupported kernel section: {section_id}")
    definitions = {field["name"]: field for field in _public_fields(section_id)}
    raw = bytearray(source_path("kernel.bin").read_bytes())
    section_start = int.from_bytes(raw[section_id * 4:section_id * 4 + 4], "little")
    changed = 0
    seen: set[tuple[int, str]] = set()
    for edit in edits:
        record_id, field_name = int(edit["id"]), str(edit["field"])
        definition = definitions.get(field_name)
        key = (record_id, field_name)
        if key in seen or not definition or not 0 <= record_id < section["number_sub_section"]:
            raise ValueError("Invalid or duplicate kernel field edit")
        seen.add(key)
        size, relative = int(definition["size"]), int(definition["offset"])
        value = int(edit["value"])
        minimum = int(definition.get("minimum", 0))
        maximum = int(definition.get("maximum", (1 << (size * 8)) - 1))
        if not minimum <= value <= maximum:
            raise ValueError(f"{field_name} must be {minimum} to {maximum}")
        absolute = section_start + record_id * section["sub_section_size"] + relative
        mask = definition.get("mask")
        if mask is not None:
            current = int.from_bytes(raw[absolute:absolute + size], "little")
            mask = int(mask)
            value = (current & ~mask) | (value & mask)
        raw[absolute:absolute + size] = value.to_bytes(size, "little")
        changed += 1
    _atomic_write(output_path("kernel.bin"), bytes(raw))
    return {"saved": changed, "file": str(output_path("kernel.bin"))}


def kernel_text_rows(dataset: str = "current") -> dict:
    """Return every referenced kernel text value from sections 32 through 56."""
    result = kernel_text.rows(source_path("kernel.bin", dataset).read_bytes(), SECTIONS)
    for row in result["rows"]:
        row["source"] = "kernel"
        row["sourceLabel"] = "Kernel text"
        row["id"] = f"kernel:{row['sectionId']}:{row['recordId']}:{row['slot']}"
    for section in result["sections"]:
        section["source"] = "kernel"
    result["source"] = source_label("kernel.bin")
    return result


def save_kernel_text(edits: list[dict]) -> dict:
    """Rebuild linked u16 offsets and the top-level table after text edits."""
    rebuilt, changed = kernel_text.apply_edits(
        source_path("kernel.bin").read_bytes(), SECTIONS, edits)
    destination = output_path("kernel.bin")
    _atomic_write(destination, rebuilt)
    return {"saved": changed, "file": str(destination)}


def text_rows(dataset: str = "current") -> dict:
    """Return all supported, source-discriminated FF8 text rows."""
    kernel = kernel_text_rows(dataset)
    menu = mngrp_text.rows(source_path("mngrp.bin", dataset).read_bytes())
    executable = executable_text_rows(dataset)
    return {
        "rows": [*kernel["rows"], *menu["rows"], *executable["rows"]],
        "sections": [*kernel["sections"], *menu["sections"], *executable["sections"]],
        "sources": [
            {"id": "kernel", "name": "Kernel text", "file": "main/kernel.bin"},
            {"id": "mngrp", "name": "Menu text", "file": "menu/mngrp.bin"},
            *executable["sources"],
        ],
    }


def save_text(edits: list[dict]) -> dict:
    """Save text to its declared source file; source keys cannot collide."""
    kernel_edits = []
    menu_edits = []
    executable_edits: dict[str, list[dict]] = {}
    for edit in edits:
        source = str(edit.get("source", "kernel"))
        if source == "kernel":
            kernel_edits.append(edit)
        elif source == "mngrp":
            menu_edits.append(edit)
        elif source in executable_text.BY_ID:
            executable_edits.setdefault(source, []).append(edit)
        else:
            raise ValueError(f"Unsupported FF8 text source: {source}")
    pending = []
    if kernel_edits:
        rebuilt, changed = kernel_text.apply_edits(
            source_path("kernel.bin").read_bytes(), SECTIONS, kernel_edits)
        pending.append((output_path("kernel.bin"), rebuilt, changed))
    if menu_edits:
        rebuilt, changed = mngrp_text.apply_edits(
            source_path("mngrp.bin").read_bytes(), menu_edits)
        pending.append((output_path("mngrp.bin"), rebuilt, changed))
    for source_id, source_edits in executable_edits.items():
        source = executable_text.BY_ID[source_id]
        replacements: dict[int, str] = {}
        for edit in source_edits:
            if int(edit.get("sectionId", -1)) != source.section_id or int(edit.get("slot", -1)) != 0:
                raise ValueError(f"A {source.label} edit has the wrong source identity")
            record_id = int(edit["recordId"])
            if record_id in replacements:
                raise ValueError(f"Duplicate {source.label} text edit")
            replacements[record_id] = str(edit.get("value", ""))
        current = _executable_text_msd(source, "current")
        rebuilt, changed = executable_text.apply_edits(current, source, replacements)
        if changed:
            pending.append((paths.DIRECT_ROOT / "ff8" / "en" / "exe" / source.filename,
                            rebuilt, changed))
    for destination, rebuilt, _changed in pending:
        _atomic_write(destination, rebuilt)
    return {"saved": sum(changed for _path, _data, changed in pending),
            "files": [str(path) for path, _data, _changed in pending]}


def _executable_text_override_path(source: executable_text.Source,
                                   dataset: str = "current") -> Path | None:
    relative = Path("ff8") / "en" / "exe" / source.filename
    if dataset == "current":
        target = paths.DIRECT_ROOT / relative
        return target if target.is_file() else None
    if dataset == "vanilla":
        return None
    if dataset.startswith("reference:"):
        reference_id = dataset.partition(":")[2]
        reference = next((row for row in reference_roots() if row["id"] == reference_id), None)
        if reference is None:
            raise ValueError(f"Unknown reference dataset: {reference_id}")
        root = Path(reference["path"])
        candidates = (root / "direct" / relative, root / relative,
                      root / "direct" / "exe" / source.filename,
                      root / "exe" / source.filename)
        return next((candidate for candidate in candidates if candidate.is_file()), None)
    managed = _managed_root(dataset)
    if managed is not None:
        candidates = (managed / "direct" / relative, managed / relative,
                      managed / "direct" / "exe" / source.filename,
                      managed / "exe" / source.filename)
        return next((candidate for candidate in candidates if candidate.is_file()), None)
    raise ValueError(f"Unknown dataset: {dataset}")


def _executable_text_msd(source: executable_text.Source, dataset: str) -> bytes:
    override = _executable_text_override_path(source, dataset)
    if override is not None:
        # Parse before returning so malformed reference or mod files fail closed.
        executable_text.read_msd(override, source)
        return override.read_bytes()
    return executable_text.extracted_msd(paths.GAME_ROOT / "FF8_EN.exe", source)


def executable_text_rows(dataset: str = "current") -> dict:
    rows = []
    sections = []
    sources = []
    for source in executable_text.SOURCES:
        override = _executable_text_override_path(source, dataset)
        if dataset.startswith("reference:") and override is None:
            continue
        if override is not None:
            values = executable_text.read_msd(override, source)
        else:
            values = executable_text.extract(paths.GAME_ROOT / "FF8_EN.exe", source)
        for record_id, value in enumerate(values):
            rows.append({
                "id": f"{source.id}:{record_id}", "source": source.id,
                "sourceLabel": source.label, "sectionId": source.section_id,
                "section": source.section, "recordId": record_id, "slot": 0,
                "role": source.role, "name": f"{source.label} #{record_id}",
                "value": value, "file": f"ff8/en/exe/{source.filename}",
            })
        sections.append({"id": source.section_id, "source": source.id,
                         "name": source.section, "entries": len(values)})
        sources.append({"id": source.id, "name": source.label,
                        "file": f"ff8/en/exe/{source.filename}"})
    return {"rows": rows, "sections": sections, "sources": sources}


def _enemy_source_path(filename: str, dataset: str = "current") -> Path:
    relative = Path("battle") / filename
    if dataset == "vanilla":
        return paths.BASELINE_ROOT / relative
    if dataset.startswith("reference:"):
        reference_id = dataset.partition(":")[2]
        reference = next((row for row in reference_roots() if row["id"] == reference_id), None)
        if reference is None:
            raise ValueError(f"Unknown reference dataset: {reference_id}")
        root = Path(reference["path"])
        candidates = (root / "direct" / relative, root / relative)
        target = next((candidate for candidate in candidates if candidate.is_file()), None)
        if target is None:
            raise ValueError(f"{filename} is absent from reference {reference_id}")
        return target
    managed = _managed_root(dataset)
    if managed is not None:
        candidates = (managed / "direct" / relative, managed / relative)
        return next((candidate for candidate in candidates if candidate.is_file()),
                    paths.BASELINE_ROOT / relative)
    if dataset != "current":
        raise ValueError(f"Unknown dataset: {dataset}")
    override = paths.DIRECT_ROOT / relative
    return override if override.is_file() else paths.BASELINE_ROOT / relative


def _enemy_output_path(filename: str) -> Path:
    return paths.DIRECT_ROOT / "battle" / filename


def _scan_override_path(dataset: str = "current") -> Path | None:
    relative = Path("ff8") / "en" / "exe" / "battle_scans.msd"
    if dataset == "current":
        return paths.DIRECT_ROOT / relative
    if dataset == "vanilla":
        return None
    if dataset.startswith("reference:"):
        reference_id = dataset.partition(":")[2]
        reference = next((row for row in reference_roots() if row["id"] == reference_id), None)
        if reference is None:
            raise ValueError(f"Unknown reference dataset: {reference_id}")
        root = Path(reference["path"])
        candidates = (
            root / "direct" / relative,
            root / relative,
            root / "direct" / "exe" / "battle_scans.msd",
            root / "exe" / "battle_scans.msd",
        )
        return next((candidate for candidate in candidates if candidate.is_file()), None)
    managed = _managed_root(dataset)
    if managed is not None:
        candidates = (
            managed / "direct" / relative, managed / relative,
            managed / "direct" / "exe" / "battle_scans.msd",
            managed / "exe" / "battle_scans.msd",
        )
        return next((candidate for candidate in candidates if candidate.is_file()), None)
    raise ValueError(f"Unknown dataset: {dataset}")


def _scan_descriptions(dataset: str = "current") -> list[str | None]:
    override = _scan_override_path(dataset)
    if override is not None and override.is_file():
        return scan_text.read_msd(override)
    if dataset.startswith("reference:"):
        return [None] * scan_text.SCAN_COUNT
    return scan_text.read_executable(paths.GAME_ROOT / "FF8_EN.exe")


def _enemy_info_start(raw: bytes) -> int:
    if len(raw) < 48:
        raise ValueError("Enemy DAT header is too short")
    section_count = int.from_bytes(raw[0:4], "little") + 1
    info_section = 1 if section_count == 3 else 7
    if section_count <= info_section:
        raise ValueError("Enemy DAT has no information section")
    # The on-disk table omits the synthetic section-0 position which the
    # upstream analyser prepends in memory. Section 7 therefore uses table
    # entries 6 and 7. The no-model enemy uses sections 1 and 2.
    table_index = info_section - 1
    start = int.from_bytes(raw[4 + table_index * 4:8 + table_index * 4], "little")
    end = int.from_bytes(raw[4 + (table_index + 1) * 4:8 + (table_index + 1) * 4], "little")
    if start < 4 + section_count * 4 or end <= start or end > len(raw):
        raise ValueError("Enemy DAT information section is invalid")
    # The final supported byte is AP at +0x14F. Later fields vary between DAT
    # variants, so Lexeditor does not expose them through this fixed contract.
    if end - start < 0x150:
        raise ValueError("Enemy DAT information section is too short")
    return start


def _enemy_field_value(raw: bytes, start: int, definition: dict):
    offset, size = int(definition["offset"]), int(definition["size"])
    stored = int.from_bytes(raw[start + offset:start + offset + size], definition["byteorder"])
    if definition.get("mask") is not None:
        return bool(stored & int(definition["mask"]))
    if definition.get("control") == "percent":
        return round(stored * 100 / 255, 1)
    return stored


def enemy_rows(dataset: str = "current") -> dict:
    rows = []
    descriptions = _scan_descriptions(dataset)
    for monster in MONSTERS:
        monster_id = int(monster.get("com_id", len(rows)))
        filename = f"c0m{monster_id:03d}.dat"
        try:
            target = _enemy_source_path(filename, dataset)
        except ValueError:
            if dataset.startswith(("reference:", "mod:")):
                continue
            raise
        available = target.is_file()
        fields = []
        if available:
            raw = target.read_bytes()
            start = _enemy_info_start(raw)
            fields = [{
                "field": definition["name"],
                "label": definition["label"],
                "group": definition["group"],
                "help": definition["help"],
                "value": _enemy_field_value(raw, start, definition),
                "minimum": definition.get("minimum", 0),
                "maximum": definition.get("maximum", 1),
                "control": definition.get("control", "number"),
            } for definition in ENEMY_FIELDS]
        rows.append({
            "id": monster_id,
            "name": monster.get("name") or f"Enemy {monster_id}",
            "role": monster.get("role", "enemy"),
            "filename": filename,
            "available": available,
            "fields": fields,
            "scanDescription": descriptions[int(monster["entity_id"])],
        })
    return {"rows": rows}


def enemy_table_rows(dataset: str = "current", enemy_id: int | None = None) -> dict:
    rows = []
    monsters = MONSTERS if enemy_id is None else [
        row for row in MONSTERS if int(row.get("com_id", -1)) == enemy_id]
    if enemy_id is not None and not monsters:
        raise ValueError(f"Invalid enemy id: {enemy_id}")
    for monster in monsters:
        monster_id = int(monster["com_id"])
        filename = f"c0m{monster_id:03d}.dat"
        target = _enemy_source_path(filename, dataset)
        if not target.is_file():
            continue
        raw = target.read_bytes()
        rows.append({
            "id": monster_id,
            "name": monster.get("name") or f"Enemy {monster_id}",
            "role": monster.get("role", "enemy"),
            "filename": filename,
            "tables": enemy_table_format.read_tables(raw, _enemy_info_start(raw)),
        })
    return {
        "rows": rows,
        "choices": enemy_table_format.choices(SCHEMA_ROOT, MAGIC, ITEMS),
    }


def enemy_ai_rows(dataset: str = "current", enemy_id: int | None = None) -> dict:
    rows = []
    monsters = MONSTERS if enemy_id is None else [
        row for row in MONSTERS if int(row.get("com_id", -1)) == enemy_id]
    if enemy_id is not None and not monsters:
        raise ValueError(f"Invalid enemy id: {enemy_id}")
    for monster in monsters:
        monster_id = int(monster["com_id"])
        filename = f"c0m{monster_id:03d}.dat"
        target = _enemy_source_path(filename, dataset)
        if not target.is_file():
            continue
        rows.append({"id": monster_id, "name": monster.get("name") or f"Enemy {monster_id}",
                     "filename": filename, **enemy_ai_format.read(target.read_bytes())})
    return {"rows": rows, "opcodes": enemy_ai_format.opcode_catalog()}


def enemy_battle_text_rows(dataset: str = "current", enemy_id: int | None = None) -> dict:
    """Return each enemy's local scripted battle-dialogue lines."""
    rows = []
    monsters = MONSTERS if enemy_id is None else [
        row for row in MONSTERS if int(row.get("com_id", -1)) == enemy_id]
    if enemy_id is not None and not monsters:
        raise ValueError(f"Invalid enemy id: {enemy_id}")
    for monster in monsters:
        monster_id = int(monster["com_id"])
        filename = f"c0m{monster_id:03d}.dat"
        target = _enemy_source_path(filename, dataset)
        if not target.is_file():
            continue
        rows.append({
            "id": monster_id,
            "name": monster.get("name") or f"Enemy {monster_id}",
            "filename": filename,
            **enemy_battle_text_format.read(target.read_bytes()),
        })
    return {"rows": rows}


def save_enemy_battle_text(edits: list[dict]) -> dict:
    """Save existing local dialogue lines through selected-mod DAT overrides."""
    grouped: dict[int, list[dict]] = {}
    valid_ids = {int(row["com_id"]) for row in MONSTERS}
    for edit in edits:
        monster_id = int(edit["id"])
        if monster_id not in valid_ids:
            raise ValueError(f"Invalid enemy id: {monster_id}")
        grouped.setdefault(monster_id, []).append({
            "id": edit.get("line"),
            "text": edit.get("text"),
        })
    changed = 0
    files = []
    for monster_id in sorted(grouped):
        filename = f"c0m{monster_id:03d}.dat"
        source = _enemy_source_path(filename)
        rebuilt, count = enemy_battle_text_format.apply_edits(
            source.read_bytes(), grouped[monster_id])
        destination = _enemy_output_path(filename)
        _atomic_write(destination, rebuilt)
        changed += count
        files.append(str(destination))
    return {"saved": changed, "file": files[0] if files else "", "files": files}


def save_enemy_ai(edits: list[dict], documents: list[dict] | None = None) -> dict:
    grouped: dict[int, list[dict]] = {}
    valid_ids = {int(row["com_id"]) for row in MONSTERS}
    document_map: dict[int, list[dict]] = {}
    for document in documents or []:
        monster_id = int(document["id"])
        if monster_id not in valid_ids or monster_id in document_map:
            raise ValueError(f"Invalid or duplicate enemy AI document: {monster_id}")
        has_scripts = "scripts" in document
        has_sources = "sources" in document
        if has_scripts == has_sources:
            raise ValueError("Enemy AI document must contain scripts or sources, but not both")
        document_map[monster_id] = (
            enemy_ai_format.compile_sources(document["sources"])
            if has_sources else list(document["scripts"]))
    for edit in edits:
        monster_id = int(edit["id"])
        if monster_id not in valid_ids or monster_id in document_map:
            raise ValueError(f"Invalid enemy id: {monster_id}")
        grouped.setdefault(monster_id, []).append(edit)
    changed = 0
    files = []
    for monster_id in sorted(set(grouped) | set(document_map)):
        monster_edits = grouped.get(monster_id, [])
        filename = f"c0m{monster_id:03d}.dat"
        source = _enemy_source_path(filename)
        if monster_id in document_map:
            rebuilt, count = enemy_ai_format.rebuild_scripts(
                source.read_bytes(), document_map[monster_id])
        else:
            rebuilt, count = enemy_ai_format.apply_edits(source.read_bytes(), monster_edits)
        destination = _enemy_output_path(filename)
        _atomic_write(destination, rebuilt)
        changed += count
        files.append(str(destination))
    return {"saved": changed, "file": files[0] if files else "", "files": files}


def compile_enemy_ai_sources(sources: list[object]) -> dict:
    """Validate source and return the equivalent structural scripts."""
    scripts = enemy_ai_format.compile_sources(sources)
    return {"scripts": scripts, "sources": [script["source"] for script in scripts]}


def refine_rows(dataset: str = "current") -> dict:
    payload = refine_tables.read(source_path("mngrp.bin", dataset).read_bytes())
    choices = {
        "item": item_choices(),
        "magic": [{"id": int(row["id"]), "name": row["name"]} for row in MAGIC],
        "card": enemy_table_format.choices(SCHEMA_ROOT, MAGIC, ITEMS)["cards"],
    }
    payload["choices"] = choices
    payload["rows"] = []
    for table in payload["tables"]:
        for row in table["rows"]:
            row["inputName"] = next((entry["name"] for entry in choices[row["inputType"]]
                                     if int(entry["id"]) == int(row["inputId"])),
                                    f"{row['inputType']} {row['inputId']}")
            row["outputName"] = next((entry["name"] for entry in choices[row["outputType"]]
                                      if int(entry["id"]) == int(row["outputId"])),
                                     f"{row['outputType']} {row['outputId']}")
            row["name"] = f"{row['inputName']} -> {row['outputName']}"
            payload["rows"].append(row)
    return payload


def save_refine_tables(edits: list[dict]) -> dict:
    rebuilt, changed = refine_tables.apply_edits(
        source_path("mngrp.bin").read_bytes(), edits)
    destination = output_path("mngrp.bin")
    _atomic_write(destination, rebuilt)
    return {"saved": changed, "file": str(destination)}


def save_enemy_tables(edits: list[dict]) -> dict:
    grouped: dict[int, list[dict]] = {}
    valid_ids = {int(row["com_id"]) for row in MONSTERS}
    for edit in edits:
        monster_id = int(edit["id"])
        if monster_id not in valid_ids:
            raise ValueError(f"Invalid enemy id: {monster_id}")
        grouped.setdefault(monster_id, []).append(edit)
    changed = 0
    files = []
    for monster_id, monster_edits in grouped.items():
        filename = f"c0m{monster_id:03d}.dat"
        raw = bytearray(_enemy_source_path(filename).read_bytes())
        changed += enemy_table_format.apply_edits(
            raw, _enemy_info_start(raw), monster_edits, SCHEMA_ROOT,
            {int(row["id"]) for row in MAGIC}, set(ITEM_NAMES))
        destination = _enemy_output_path(filename)
        _atomic_write(destination, bytes(raw))
        files.append(str(destination))
    return {"saved": changed, "file": files[0] if files else "", "files": files}


def encounter_rows(dataset: str = "current") -> dict:
    enemy_names = {int(row["com_id"]): row.get("name", "") for row in MONSTERS}
    payload = encounter_format.read_rows(source_path("scene.out", dataset).read_bytes(), enemy_names)
    payload["enemies"] = [
        {"id": enemy_id, "name": name} for enemy_id, name in sorted(enemy_names.items())]
    payload["source"] = source_label("scene.out")
    return payload


def save_encounters(edits: list[dict]) -> dict:
    enemy_ids = {int(row["com_id"]) for row in MONSTERS}
    data, changed = encounter_format.apply_edits(
        source_path("scene.out").read_bytes(), edits, enemy_ids)
    destination = output_path("scene.out")
    _atomic_write(destination, data)
    return {"saved": changed, "file": str(destination)}


def init_rows(dataset: str = "current") -> dict:
    payload = init_format.read(
        source_path("init.out", dataset).read_bytes(),
        items=item_choices(), weapons=WEAPONS, magic=MAGIC, gfs=GFORCES,
        abilities=INIT_ABILITIES,
    )
    payload["source"] = source_label("init.out")
    return payload


def save_init(edits: list[dict]) -> dict:
    data, changed = init_format.apply(
        source_path("init.out").read_bytes(), edits,
        item_ids=set(ITEM_NAMES), weapon_ids={int(row["id"]) for row in WEAPONS},
        magic_ids={int(row["id"]) for row in MAGIC}, weapons=WEAPONS,
        magic=MAGIC, gfs=GFORCES, abilities=INIT_ABILITIES,
    )
    destination = output_path("init.out")
    _atomic_write(destination, data)
    return {"saved": changed, "file": str(destination)}


def save_enemies(edits: list[dict]) -> dict:
    grouped: dict[int, list[dict]] = {}
    scan_edits: dict[int, str] = {}
    valid_ids = {int(row["com_id"]) for row in MONSTERS}
    for edit in edits:
        monster_id = int(edit["id"])
        if monster_id not in valid_ids:
            raise ValueError(f"Invalid enemy id: {monster_id}")
        if edit.get("field") == "scan_description":
            if monster_id in scan_edits:
                raise ValueError(f"Duplicate Scan description edit for enemy {monster_id}")
            scan_edits[monster_id] = str(edit.get("value", ""))
        else:
            grouped.setdefault(monster_id, []).append(edit)

    changed = 0
    files = []
    for monster_id, monster_edits in grouped.items():
        filename = f"c0m{monster_id:03d}.dat"
        raw = bytearray(_enemy_source_path(filename).read_bytes())
        start = _enemy_info_start(raw)
        seen: set[str] = set()
        for edit in monster_edits:
            field_name = str(edit["field"])
            definition = ENEMY_FIELD_MAP.get(field_name)
            if definition is None or field_name in seen:
                raise ValueError(f"Invalid or duplicate enemy field: {field_name}")
            seen.add(field_name)
            absolute = start + int(definition["offset"])
            size = int(definition["size"])
            if definition.get("mask") is not None:
                current = int.from_bytes(raw[absolute:absolute + size], definition["byteorder"])
                mask = int(definition["mask"])
                stored = (current | mask) if bool(edit["value"]) else (current & ~mask)
            elif definition.get("control") == "percent":
                value = float(edit["value"])
                if not 0 <= value <= 100:
                    raise ValueError(f"{definition['label']} must be 0% to 100%")
                stored = round(value * 255 / 100)
            else:
                value = int(edit["value"])
                minimum, maximum = int(definition["minimum"]), int(definition["maximum"])
                if not minimum <= value <= maximum:
                    raise ValueError(f"{definition['label']} must be {minimum} to {maximum}")
                stored = value
            raw[absolute:absolute + size] = int(stored).to_bytes(size, definition["byteorder"])
            changed += 1
        destination = _enemy_output_path(filename)
        _atomic_write(destination, bytes(raw))
        files.append(str(destination))
    if scan_edits:
        descriptions = _scan_descriptions("current")
        monsters = {int(row["com_id"]): row for row in MONSTERS}
        for monster_id, description in scan_edits.items():
            descriptions[int(monsters[monster_id]["entity_id"])] = description
        destination = paths.DIRECT_ROOT / "ff8" / "en" / "exe" / "battle_scans.msd"
        _atomic_write(destination, scan_text.build_msd([str(value) for value in descriptions]))
        files.append(str(destination))
        changed += len(scan_edits)
    return {"saved": changed, "file": files[0] if files else "", "files": files}


def data_map_rows() -> dict:
    rows = [
        {"filename": "kernel.bin", "controls": "Character, Magic, GF, weapon, battle-item, command and ability gameplay records; linked names and descriptions", "notes": "Numeric fields with proven schemas are editable. All referenced text in sections 32-56 is editable with FF8 encoding and complete linked-offset and section-offset rebuilds. Unnamed numeric fields remain preserved.", "status": "partial"},
        {"filename": "menu/price.bin", "controls": "Item buy prices and sell-price multipliers", "notes": "", "status": "integrated"},
        {"filename": "menu/shop.bin", "controls": "Twenty shop inventories and rare-stock flags", "notes": "", "status": "integrated"},
        {"filename": "menu/mwepon.bin", "controls": "Weapon upgrade prices and four ingredient slots", "notes": "", "status": "integrated"},
        {"filename": "init.out", "controls": "Starting party, inventory, GF, character, junction and config state", "notes": "The Starting Data tab edits only named Quezacotl fields and preserves unknown and runtime-only bytes.", "status": "integrated"},
        {"filename": "menu/mitem.bin", "controls": "Menu item type, use flags and type-specific parameters", "notes": "The Items detail panel exposes every meaningful field in each four-byte record with bounded, schema-driven controls.", "status": "integrated"},
        {"filename": "menu/mngrp.bin", "controls": "Book, card-rule, SeeD-test, battle and character tutorial text; all 377 Magic Refine, Tool/Medicine Refine, Magic Upgrade, Med LV Up and Card Mod recipes", "notes": "The Text tab rebuilds proved mngrp_string sections. The Refine tab edits the five proved m00x recipe tables and their linked display text, rebuilds every u16 text offset within the original fixed sections, and preserves unknown recipe words and all unrelated menu data byte-for-byte. Other menu data, scripts, text-box maps and images remain outside the editor.", "status": "partial"},
        {"filename": "battle/c0m*.dat", "controls": "Enemy stats, properties, action definitions, structural and source-language conditional battle AI, and local scripted battle text", "notes": "The Enemies AI view decodes and rebuilds the five proved Init, Turn, Counter, Death and Pre-hit scripts. Structure supports replace, insert, delete and reorder; Source supports stable labels, exact opcode mnemonics and typed operands. Both compile through the same validated branch-aware writer. The Battle Text view edits the existing local dialogue lines referenced by those scripts. Unknown or malformed tails remain fail-closed.", "status": "partial"},
        {"filename": "battle/scene.out", "controls": "Battle formations, stage, cameras, enemy slots, levels and positions", "notes": "The Encounters tab exposes all 1,024 fixed records and every supported header, slot, mask and position field. Enemy levels use proved Fixed 1-100, Maximum 1-100, and Ultimecia Castle random 1-100 controls; unresolved special level bytes are preserved until the user selects a proved rule.", "status": "integrated"},
        {"filename": "world.fs / world/dat/wmx.obj + wmsetus.obj + rail.obj + texl.obj", "controls": "Rendered in-game world map with clickable 32 by 24 WMX segments, segment group and encounter-region editing, encounter rules and groups, 64 field-to-world positions, all 128 world Draw Point positions, 8 positioned sky and ambient colour records, train stops and XYZ rail keypoints, plus previews, palette selection, export, and validated replacement for all 20 high-resolution world TIM textures", "notes": "The Map view decodes the game's own minimap TIM and aligns it to Deling's 32 by 24 base WMX segment grid. It validates all 835 fixed 0x9000-byte WMX segments and patches only the proved leading group ID, so topology and unknown bytes stay exact. The other subtabs edit proved fixed-size wmset fields, OpenVIII-proved 2,048-byte rail blocks, and Deling/OpenVIII-proved 0x12800 texl slots. Draw Point magic, quantity, and refill data live in FF8_EN.exe and are not misrepresented as wmset fields.", "status": "partial"},
        {"filename": "FF8_EN.exe", "controls": "Localized Scan descriptions, card names, draw-point messages, card UI text, and Triple Triad card properties", "notes": "The supported English text blocks are read from the executable but never written back to it. The Text and Enemies tabs save complete FFNx Direct Mode MSD overrides. Cards edits the existing 110 card names, four ranks, element and selection power. Property edits generate ordered Hext writes to both menu and minigame tables, preserving unknown bytes and other fields. Adding or removing card types requires separate engine and save support. Other executable text and gameplay code remain outside the data editor.", "status": "partial"},
        {"filename": "ff8/en/exe/battle_scans.msd", "controls": "All 160 localized Scan descriptions", "notes": "The Enemies panel writes the FFNx language-specific project override and preserves every unedited entry.", "status": "integrated"},
        {"filename": "ff8/en/exe/card_names.msd", "controls": "All 110 Triple Triad card names", "notes": "The Text tab writes the FFNx-supported Direct Mode file. Source-qualified record IDs keep these names separate from kernel and menu text.", "status": "integrated"},
        {"filename": "ff8/en/exe/draw_point.msd", "controls": "All 9 executable draw-point and disc messages", "notes": "The Text tab writes the FFNx-supported Direct Mode file and rejects malformed offsets or unsupported FF8 characters.", "status": "integrated"},
        {"filename": "ff8/en/exe/card_texts.msd", "controls": "All 29 executable card-menu messages", "notes": "The Text tab writes FFNx's supported 29-entry MSD form while preserving every unedited encoded string.", "status": "integrated"},
        {"filename": "hext/ff8/en_nv/Lexeditor.FLYING_EVA.txt", "controls": "Flying-enemy EVA bonus and ranged/Float exceptions", "notes": "Generated in FFNx's effective FF8 English Nvidia Hext directory.", "status": "integrated"},
        {"filename": "FFNx.toml", "controls": "FFNx display, audio, rendering, mod and runtime settings", "notes": "The Tweaks > FFNx tab edits typed values in place and preserves comments and file order.", "status": "integrated" if (paths.GAME_ROOT / "FFNx.toml").is_file() else "partial"},
        {"filename": "field.fs", "controls": "Field-map index, backgrounds, random encounter formations and rates, dialogue, general scripts, walkmesh, gateways, triggers, and Triple Triad CARDGAME parameters", "notes": "The Maps > Field view indexes all 896 complete nested map archive triplets without extracting unrelated assets. It extracts only the selected map's supported assets on demand. The four MRT formation IDs and canonical four-byte RAT encounter rate are editable for all 889 maps that contain the proved pair; no-op writes are exact and ordered mods merge independent formation slots or the rate unit. All 894 MAP/MIM background pairs render from the installed texture and expose 14 Deling-proved tile fields with packed spare bits and terminators preserved. All 22,392 dialogue lines across 883 map MSD files are editable with strict FF8 encoding, rebuilt u32 offsets, stable line counts, and unchanged encoded-payload preservation. Across 882 JSM maps, all 87,218 methods and 1,439,792 instruction words parse and rebuild identically. The 87,197 methods with contained control flow are editable using only Deling's 376 defined opcode names; method positions and intra-method relative branches rebuild after edits. The 21 methods with branches outside their own method remain visible and locked. All 151,651 triangles in 894 proved ID walkmeshes have a top-down X/Z preview and typed signed X/Y/Z and adjacency controls. Walkmesh saves preserve topology, reserved vertex words, and the optional two-byte tail; ordered mods merge independent proved fields and report same-field conflicts. Literal and savemap-variable values in the seven fixed pushes before opcode 0x13A remain available through the focused Triple Triad controls. All 12 INF gateways and triggers expose their proved line endpoints, destination positions, target field IDs, and door IDs. Saves preserve source variants and unrelated bytes. Models and media remain explicitly unsupported.", "status": "partial"},
    ]
    targets = {
        "kernel.bin": ["characters", "magic", "gfs", "weapons", "items", "abilities", "text"],
        "menu/price.bin": ["items"], "menu/shop.bin": ["shops"],
        "menu/mwepon.bin": ["weapons"], "init.out": ["starting"],
        "menu/mitem.bin": ["items"], "menu/mngrp.bin": ["text", "refine"],
        "battle/c0m*.dat": ["enemies"], "battle/scene.out": ["encounters"],
        "FF8_EN.exe": ["cards", "text", "enemies"],
        "ff8/en/exe/battle_scans.msd": ["enemies"],
        "ff8/en/exe/card_names.msd": ["text"],
        "ff8/en/exe/draw_point.msd": ["text"],
        "ff8/en/exe/card_texts.msd": ["text"],
        "hext/ff8/en_nv/Lexeditor.FLYING_EVA.txt": ["settings"],
        "FFNx.toml": ["settings"], "field.fs": ["fields"],
    }
    for row in rows:
        row["targets"] = targets.get(row["filename"], ["world"] if row["filename"].startswith("world.fs /") else [])
        row["coverage"] = "structured" if row["targets"] else "unavailable"
        row["openable"] = bool(row["targets"])
        if row["filename"] == "init.out":
            row["status"] = "partial"
        if row["filename"] == "FFNx.toml" and not (paths.GAME_ROOT / "FFNx.toml").is_file():
            row.update(status="not-integrated", coverage="unavailable", openable=False)
            row["notes"] = "FFNx.toml is missing; its settings editor becomes available after FFNx creates it."
    return {"rows": rows}
