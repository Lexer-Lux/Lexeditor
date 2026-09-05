"""Lossless editor for FF8's new-game ``init.out`` state.

The layout follows FF8 Ultimate Editor's Quezacotl manager at revision
343d97e9e15023b15b2956b30c1c80cd93969164. Unknown and runtime-only bytes are
never rebuilt. Lexeditor changes only the named fields below and preserves the
rest of the source buffer byte for byte.
"""

from __future__ import annotations

from copy import deepcopy


GF_COUNT = 16
GF_SIZE = 68
CHARACTER_COUNT = 8
CHARACTER_SIZE = 152
CHARACTER_OFFSET = GF_COUNT * GF_SIZE
CONFIG_OFFSET = CHARACTER_OFFSET + CHARACTER_COUNT * CHARACTER_SIZE + 400
MISC_OFFSET = CONFIG_OFFSET + 20
ITEMS_OFFSET = MISC_OFFSET + 80
ITEM_COUNT = 198
FULL_SIZE = ITEMS_OFFSET + ITEM_COUNT * 2

CHARACTER_NAMES = ["Squall", "Zell", "Irvine", "Quistis", "Rinoa", "Selphie", "Seifer", "Edea"]
PARTY_NAMES = CHARACTER_NAMES + ["Laguna", "Kiros", "Ward"]


def _enum(name: str, entries: list[dict]) -> dict:
    return {"type": "enum", "name": name, "entries": entries}


def _flags(name: str, entries: list[dict]) -> dict:
    return {"type": "flags", "name": name, "entries": entries}


def _field(name: str, label: str, offset: int, size: int = 1, *, minimum: int = 0,
           maximum: int | None = None, control: str | None = None,
           lookup: dict | None = None, help_text: str = "") -> dict:
    return {
        "field": name, "label": label, "offset": offset, "size": size,
        "minimum": minimum, "maximum": maximum if maximum is not None else (1 << (size * 8)) - 1,
        **({"control": control} if control else {}),
        **({"lookup": lookup} if lookup else {}),
        **({"help": help_text} if help_text else {}),
    }


GENERAL_FIELDS = [
    _field("party_1", "Party member 1", MISC_OFFSET, lookup=_enum("character", [])),
    _field("party_2", "Party member 2", MISC_OFFSET + 1, lookup=_enum("character", [])),
    _field("party_3", "Party member 3", MISC_OFFSET + 2, lookup=_enum("character", [])),
    _field("unlocked_weapons", "Unlocked weapon recipes", MISC_OFFSET + 4, 4,
           help_text="A bitfield of weapon recipes already built or known at the start of a new game."),
    _field("weapon_laguna", "Laguna weapon", MISC_OFFSET + 20, lookup=_enum("weapon", [])),
    _field("weapon_kiros", "Kiros weapon", MISC_OFFSET + 21, lookup=_enum("weapon", [])),
    _field("weapon_ward", "Ward weapon", MISC_OFFSET + 22, lookup=_enum("weapon", [])),
    _field("gil", "Starting Gil", MISC_OFFSET + 24, 4),
    _field("gil_laguna", "Starting Laguna Gil", MISC_OFFSET + 28, 4),
    _field("limit_quistis", "Quistis limits", MISC_OFFSET + 32, 2),
    _field("limit_zell", "Zell limits", MISC_OFFSET + 34, 2),
    _field("limit_irvine", "Irvine limits", MISC_OFFSET + 36),
    _field("limit_selphie", "Selphie limits", MISC_OFFSET + 37),
    _field("limit_angelo_completed", "Angelo completed", MISC_OFFSET + 38),
    _field("limit_angelo_known", "Angelo known", MISC_OFFSET + 39),
]

CONFIG_NAMES = [
    "battle_speed", "battle_message_speed", "field_message_speed", "volume", "flags", "scan", "camera",
    "map_seal", "key_l2", "key_r2", "key_l1", "key_r1", "key_triangle", "key_circle", "key_cross",
    "key_square", "key_select", "key_unknown_1", "key_unknown_2", "key_start",
]
CONFIG_LABELS = [
    "Battle speed", "Battle message speed", "Field message speed", "Volume", "Config flags", "Scan mode",
    "Camera mode", "Locked menu commands", "L2 action", "R2 action", "L1 action", "R1 action",
    "Triangle action", "Circle action", "Cross action", "Square action", "Select action", "Unknown action 1",
    "Unknown action 2", "Start action",
]
CONFIG_FLAG_ENTRIES = [
    {"name": "Battle vibration trigger", "mask": 0x01}, {"name": "Unknown bit 1", "mask": 0x02},
    {"name": "Unknown bit 2", "mask": 0x04}, {"name": "Unknown bit 3", "mask": 0x08},
    {"name": "Vibration hardware present", "mask": 0x10}, {"name": "Use custom controls", "mask": 0x20},
    {"name": "No controller detected", "mask": 0x40}, {"name": "Controls modified", "mask": 0x80},
]
MAP_SEAL_ENTRIES = [
    {"name": name, "mask": 1 << index} for index, name in enumerate(
        ["Item", "Magic", "GF", "Draw", "Command ability", "Limit break", "Resurrection", "Save"])
]
CONFIG_FIELDS = [
    _field(name, label, CONFIG_OFFSET + index,
           lookup=_flags("config_flags", CONFIG_FLAG_ENTRIES) if name == "flags" else
                  _flags("map_seal", MAP_SEAL_ENTRIES) if name == "map_seal" else None)
    for index, (name, label) in enumerate(zip(CONFIG_NAMES, CONFIG_LABELS))
]


def _gf_fields(base: int) -> list[dict]:
    return [
        _field("exp", "Experience", base + 12, 4),
        _field("available", "Available", base + 17, control="boolean"),
        _field("current_hp", "Current HP", base + 18, 2),
        _field("kills", "Kills", base + 60, 2),
        _field("kos", "KOs", base + 62, 2),
        _field("learning_ability", "Learning ability", base + 64, maximum=127,
               help_text="The GF ability slot currently receiving AP."),
    ]


def _character_fields(base: int, weapons: list[dict], abilities: list[dict], gfs: list[dict], magic: list[dict]) -> list[dict]:
    ability_lookup = _enum("junctionable_ability", [{"id": 0, "name": "None"}, *abilities])
    gf_flags = _flags("gfs", [{"name": row["name"], "mask": 1 << int(row["id"])} for row in gfs])
    status_flags = _flags("status_1", [
        {"name": name, "mask": 1 << index} for index, name in enumerate(
            ["Death", "Poison", "Petrify", "Darkness", "Silence", "Berserk", "Zombie"])
    ])
    fields = [
        _field("current_hp", "Current HP", base, 2), _field("hp_bonus", "HP bonus", base + 2, 2),
        _field("exp", "Experience", base + 4, 4), _field("model_id", "Model ID", base + 8),
        _field("weapon_id", "Weapon", base + 9, lookup=_enum("weapon", weapons)),
        *[_field(name, label, base + offset) for name, label, offset in (
            ("str", "STR", 10), ("vit", "VIT", 11), ("mag", "MAG", 12), ("spr", "SPR", 13),
            ("spd", "SPD", 14), ("luck", "LUCK", 15))],
        *[_field(f"active_ability_{slot + 1}", f"Command ability {slot + 1}", base + 80 + slot,
                 lookup=ability_lookup) for slot in range(4)],
        *[_field(f"passive_ability_{slot + 1}", f"Passive ability {slot + 1}", base + 84 + slot,
                 lookup=ability_lookup) for slot in range(4)],
        _field("junctioned_gfs", "Junctioned GFs", base + 88, 2, lookup=gf_flags),
        _field("alternate_model", "Alternate model", base + 91, control="boolean"),
    ]
    junction_names = ["hp", "str", "vit", "mag", "spr", "spd", "eva", "hit", "luck", "element_attack",
                      "status_attack", "element_defense_1", "element_defense_2", "element_defense_3",
                      "element_defense_4", "status_defense_1", "status_defense_2", "status_defense_3",
                      "status_defense_4"]
    magic_lookup = _enum("magic", [{"id": 0, "name": "None"}, *magic])
    fields.extend(_field(f"junction_{name}", f"Junction {name.replace('_', ' ').title()}", base + 92 + index,
                         lookup=magic_lookup) for index, name in enumerate(junction_names))
    fields.extend(_field(f"gf_compatibility_{index + 1}", f"{gf['name']} compatibility", base + 112 + index * 2,
                         2, minimum=1000, maximum=6000) for index, gf in enumerate(gfs))
    fields.extend([
        _field("kills", "Kills", base + 144, 2), _field("kos", "KOs", base + 146, 2),
        _field("exists", "Exists", base + 148, control="boolean"),
        _field("status", "Starting status", base + 150, 2, lookup=status_flags),
    ])
    return fields


def _read_int(data: bytes | bytearray, offset: int, size: int) -> int:
    chunk = data[offset:offset + size]
    return int.from_bytes(chunk.ljust(size, b"\0"), "little")


def _read_fields(data: bytes, definitions: list[dict]) -> list[dict]:
    return [{key: deepcopy(value) for key, value in definition.items() if key != "offset"} |
            {"value": bool(_read_int(data, definition["offset"], definition["size"]))
                      if definition.get("control") == "boolean" else
                      _read_int(data, definition["offset"], definition["size"])}
            for definition in definitions]


def read(data: bytes, *, items: list[dict], weapons: list[dict], magic: list[dict],
         gfs: list[dict], abilities: list[dict]) -> dict:
    party_entries = [{"id": index, "name": name} for index, name in enumerate(PARTY_NAMES)] + [{"id": 255, "name": "Empty"}]
    general_defs = deepcopy(GENERAL_FIELDS)
    for definition in general_defs[:3]:
        definition["lookup"]["entries"] = party_entries
    for definition in general_defs[4:7]:
        definition["lookup"]["entries"] = weapons
    character_rows = []
    for character_id, name in enumerate(CHARACTER_NAMES):
        base = CHARACTER_OFFSET + character_id * CHARACTER_SIZE
        magics = [{"slot": slot, "magicId": _read_int(data, base + 16 + slot * 2, 1),
                   "quantity": _read_int(data, base + 17 + slot * 2, 1)} for slot in range(32)]
        character_rows.append({"id": character_id, "name": name,
                               "fields": _read_fields(data, _character_fields(base, weapons, abilities, gfs, magic)),
                               "magics": magics})
    return {
        "general": {"fields": _read_fields(data, general_defs)},
        "config": {"fields": _read_fields(data, CONFIG_FIELDS)},
        "gfs": {"rows": [{"id": gf_id, "name": gfs[gf_id]["name"],
                            "fields": _read_fields(data, _gf_fields(gf_id * GF_SIZE))}
                           for gf_id in range(GF_COUNT)]},
        "characters": {"rows": character_rows},
        "inventory": {"rows": [{"slot": slot, "itemId": _read_int(data, ITEMS_OFFSET + slot * 2, 1),
                                  "quantity": _read_int(data, ITEMS_OFFSET + slot * 2 + 1, 1)}
                                 for slot in range(ITEM_COUNT)]},
        "choices": {"items": items, "magic": [{"id": 0, "name": "None"}, *magic]},
    }


def _definition_map(*, weapons: list[dict], magic: list[dict], gfs: list[dict], abilities: list[dict]) -> dict[tuple[str, int, str], dict]:
    definitions: dict[tuple[str, int, str], dict] = {}
    for definition in GENERAL_FIELDS:
        definitions[("general", 0, definition["field"])] = definition
    for definition in CONFIG_FIELDS:
        definitions[("config", 0, definition["field"])] = definition
    for gf_id in range(GF_COUNT):
        for definition in _gf_fields(gf_id * GF_SIZE):
            definitions[("gf", gf_id, definition["field"])] = definition
    for character_id in range(CHARACTER_COUNT):
        base = CHARACTER_OFFSET + character_id * CHARACTER_SIZE
        for definition in _character_fields(base, weapons, abilities, gfs, magic):
            definitions[("character", character_id, definition["field"])] = definition
    return definitions


def apply(data: bytes, edits: list[dict], *, item_ids: set[int], weapon_ids: set[int], magic_ids: set[int],
          weapons: list[dict], magic: list[dict], gfs: list[dict], abilities: list[dict]) -> tuple[bytes, int]:
    result = bytearray(data)
    if len(result) < FULL_SIZE:
        result.extend(b"\0" * (FULL_SIZE - len(result)))
    definitions = _definition_map(weapons=weapons, magic=magic, gfs=gfs, abilities=abilities)
    seen: set[tuple] = set()
    changed = 0
    for edit in edits:
        kind = str(edit.get("kind", ""))
        row_id = int(edit.get("id", 0))
        if kind == "inventory":
            slot = int(edit["slot"])
            key = (kind, slot)
            if key in seen or not 0 <= slot < ITEM_COUNT:
                raise ValueError(f"Invalid or duplicate starting inventory slot: {slot}")
            seen.add(key)
            item_id, quantity = int(edit["itemId"]), int(edit["quantity"])
            if item_id not in item_ids or not 0 <= quantity <= 100:
                raise ValueError("Starting inventory needs a valid item and a quantity from 0 to 100")
            if item_id == 0:
                quantity = 0
            offset = ITEMS_OFFSET + slot * 2
            result[offset:offset + 2] = bytes((item_id, quantity))
            changed += 1
            continue
        if kind == "magic":
            slot = int(edit["slot"])
            key = (kind, row_id, slot)
            if key in seen or not 0 <= row_id < CHARACTER_COUNT or not 0 <= slot < 32:
                raise ValueError("Invalid or duplicate starting Magic slot")
            seen.add(key)
            magic_id, quantity = int(edit["magicId"]), int(edit["quantity"])
            if magic_id not in magic_ids | {0} or not 0 <= quantity <= 100:
                raise ValueError("Starting Magic needs a valid spell and a quantity from 0 to 100")
            if magic_id == 0:
                quantity = 0
            offset = CHARACTER_OFFSET + row_id * CHARACTER_SIZE + 16 + slot * 2
            result[offset:offset + 2] = bytes((magic_id, quantity))
            changed += 1
            continue
        field_name = str(edit.get("field", ""))
        definition = definitions.get((kind, row_id, field_name))
        key = (kind, row_id, field_name)
        if definition is None or key in seen:
            raise ValueError(f"Invalid or duplicate init.out field: {kind} {row_id} {field_name}")
        seen.add(key)
        value = 1 if definition.get("control") == "boolean" and bool(edit.get("value")) else int(edit.get("value", 0))
        if not int(definition["minimum"]) <= value <= int(definition["maximum"]):
            raise ValueError(f"{definition['label']} must be {definition['minimum']} to {definition['maximum']}")
        if field_name in {"weapon_id", "weapon_laguna", "weapon_kiros", "weapon_ward"} and value not in weapon_ids:
            raise ValueError(f"Invalid weapon id: {value}")
        offset, size = int(definition["offset"]), int(definition["size"])
        result[offset:offset + size] = value.to_bytes(size, "little")
        changed += 1
    return bytes(result), changed
