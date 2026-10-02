"""Reviewed stamina-recovery projection for Dark Souls Remastered.

Only the signed staminaRecoverChangeSpeed cell is writable. The rest of each
368-byte SP_EFFECT_PARAM_ST row, its directory, and the containing archive are
preserved. The table is optional so older/smaller projects remain readable.

Layout reference: Smithbox revision
057b417887cc7d0ddc8001602be3f5339f42c74f,
Smithbox.Release/Output/Assets/PARAM/DS1R/Defs/SpEffect.xml
(blob 30411975bed40f56ea53247a93807c9cc099cfe1).
The first 46 fields are four bytes each: the recovery cell starts at 0xB8.
Row identities are reference labels, not evidence that an effect is active.
See stamina-sources.md for provenance and the unresolved engine-baseline scope.
"""
from __future__ import annotations

import math

from plugins.ds3.formats import FieldSpec, ParamView, read_field, write_field
from .formats import FormatError, ItemDocument

EFFECT_TABLE = "SpEffectParam"
EFFECT_TYPE = "SP_EFFECT_PARAM_ST"
EFFECT_ROW_SIZE = 368
RECOVERY_KEY = "staminaRecoverChangeSpeed"
RECOVERY_FIELD = FieldSpec(
    RECOVERY_KEY, "s32", 184, 1, None, None,
    "Recovery adjustment (stamina/second)",
    "Adds to stamina recovery while this effect is active. Negative values slow recovery. "
    "This is a modifier, not the final recovery rate or a percentage.",
    "Stamina",
)
RECOVERY_MINIMUM = -100
RECOVERY_MAXIMUM = 100

STAMINA_SUBTABS = (
    ("stamina-equipment", "Equipment effects", EFFECT_TABLE),
    ("stamina-armor", "Armour penalties", EFFECT_TABLE),
    ("stamina-player", "Player effects", EFFECT_TABLE),
    ("stamina-all", "All effects", EFFECT_TABLE),
)
PLAYER_EFFECT_IDS = frozenset(range(40, 45))
ARMOR_EFFECT_IDS = frozenset(
    slot + level for slot in (6200, 6210, 6220, 6230) for level in range(4)
)
REFERENCE_NAMES = {
    40: "Player: no miracle resonance",
    41: "Player: miracle resonance 1",
    42: "Player: miracle resonance 2",
    43: "Player: miracle resonance 3",
    44: "Player: miracle resonance 4",
    1090: "Power Within",
    2013: "Cloranthy Ring",
    3040: "Green Blossom",
    6890: "Grass Crest Shield",
    6920: "Mask of the Child",
}
for _base, _slot in ((6200, "Head"), (6210, "Body"), (6220, "Arms"), (6230, "Legs")):
    for _level in range(4):
        REFERENCE_NAMES[_base + _level] = f"{_slot}: recovery penalty {_level + 1}"

# These are equipped passive-effect references, not on-hit effect IDs.
# Read the actual references rather than assuming a modified shield still uses 6890.
EQUIPMENT_REFERENCES = {
    "EquipParamWeapon": ("residentSpEffectId", "residentSpEffectId1", "residentSpEffectId2"),
    "EquipParamProtector": ("residentSpEffectId", "residentSpEffectId2", "residentSpEffectId3"),
    "EquipParamAccessory": ("refId",),
}


class StaminaDocument(ItemDocument):
    """Extend the existing byte-preserving document without replacing its codecs."""

    def __init__(self, source: bytes):
        super().__init__(source)
        self._effect_param = None
        self._equipment_sources = None
        member = self.members.get(EFFECT_TABLE + ".param")
        if member is None:
            return
        payload = self.plain[member.offset:member.offset + member.size]
        if len(payload) < 48 or payload[44:48] != b"\0\x02\0\0":
            raise FormatError("Unsupported stamina-effect PARAM header")
        param = ParamView(payload)
        if param.big_endian or param.param_type != EFFECT_TYPE or param.header_version != 1:
            raise FormatError("Unsupported stamina-effect layout/version")
        if not param.rows or len({row.row_id for row in param.rows}) != len(param.rows):
            raise FormatError("Empty or duplicate stamina-effect row IDs")
        directory_end = (
            64 if param.format2d & 4 or param.format2d & 3 == 3 else 48
        ) + len(param.rows) * (24 if param.long_offsets else 12)
        offsets = sorted(row.data_offset for row in param.rows)
        if (not directory_end <= param.strings_offset <= member.size
                or offsets[0] < directory_end
                or any(b - a != EFFECT_ROW_SIZE for a, b in zip(offsets, offsets[1:]))
                or offsets[-1] + EFFECT_ROW_SIZE > param.strings_offset):
            raise FormatError("Stamina-effect row boundaries do not match the reviewed layout")
        self._effect_param = param
        self._effect_ids = frozenset(row.row_id for row in param.rows)

    @property
    def stamina_available(self) -> bool:
        return self._effect_param is not None

    def _effect_row(self, row_id: int):
        if not self.stamina_available:
            raise FormatError(
                "SpEffectParam.param is missing. Open a complete Remastered parameter archive "
                "to edit stamina effects."
            )
        if type(row_id) is not int:
            raise FormatError("Invalid stamina-effect identity")
        row = self._effect_param.row(row_id)
        start = self.members[EFFECT_TABLE + ".param"].offset + row.data_offset
        return row, start, bytes(self.plain[start:start + EFFECT_ROW_SIZE])

    def _effect_name(self, row) -> str:
        return REFERENCE_NAMES.get(row.row_id) or row.name or f"Effect {row.row_id}"

    def _passive_ids(self, table: str, row_id: int) -> list[int]:
        keys = EQUIPMENT_REFERENCES.get(table, ())
        if not keys or not self.stamina_available:
            return []
        specs = {entry["spec"].key: entry["spec"] for entry in self.schemas[table]["fields"]}
        data = self._row(table, row_id)[2]
        if table == "EquipParamAccessory":
            category = specs.get("refCategory")
            if category is None or read_field(data, category, "<") != 2:
                return []
        result = []
        for key in keys:
            field = specs.get(key)
            if field is None:
                continue
            effect_id = read_field(data, field, "<")
            if effect_id in self._effect_ids and effect_id not in result:
                result.append(effect_id)
        return result

    def equipment_sources(self) -> dict[int, list[dict]]:
        if self._equipment_sources is None:
            sources = {}
            for table in EQUIPMENT_REFERENCES:
                for row in self.params[table].rows:
                    for effect_id in self._passive_ids(table, row.row_id):
                        sources.setdefault(effect_id, []).append({
                            "table": table, "id": row.row_id,
                            "name": self.schemas[table]["names"].get(row.row_id)
                                    or row.name or f"Item {row.row_id}",
                        })
            self._equipment_sources = sources
        return self._equipment_sources

    def list_rows(self, tab):
        if tab not in {entry[0] for entry in STAMINA_SUBTABS}:
            return super().list_rows(tab)
        if not self.stamina_available:
            self._effect_row(0)  # Report an actionable missing-table error.
        selected = None
        if tab == "stamina-equipment":
            selected = set(self.equipment_sources())
            selected.update((1090, 2013, 3040, 6890, 6920))
            selected.difference_update(ARMOR_EFFECT_IDS)
        elif tab == "stamina-armor":
            selected = ARMOR_EFFECT_IDS
        elif tab == "stamina-player":
            selected = PLAYER_EFFECT_IDS
        return [
            {"id": row.row_id, "name": self._effect_name(row), "table": EFFECT_TABLE}
            for row in self._effect_param.rows
            if selected is None or row.row_id in selected
        ]

    def read_row(self, table, row_id):
        if table != EFFECT_TABLE:
            result = super().read_row(table, row_id)
            links = self._passive_ids(table, row_id)
            if links:
                result["staminaEffects"] = [
                    {"id": effect_id,
                     "name": self._effect_name(self._effect_param.row(effect_id)),
                     "value": read_field(self._effect_row(effect_id)[2], RECOVERY_FIELD, "<")}
                    for effect_id in links
                ]
            return result
        row, _start, data = self._effect_row(row_id)
        owners = self.equipment_sources().get(row_id, [])
        if row_id in ARMOR_EFFECT_IDS:
            context = (
                "This is an armour-piece recovery penalty, not an equip-load percentage tier. "
                "Only equipment referencing this effect is changed."
            )
        elif row_id in PLAYER_EFFECT_IDS:
            context = (
                "This is a player resonance-effect modifier, not the engine's base recovery constant. "
                "Its active-state and stacking behaviour must be checked in game. "
                "Changing one row is not a verified global baseline change."
            )
        else:
            context = (
                "All equipment and abilities referencing this effect share this recovery adjustment. "
                "The reference name alone does not prove which items use it in a modified archive."
            )
        return {
            "id": row_id, "table": EFFECT_TABLE, "name": self._effect_name(row),
            "fields": [{
                "key": RECOVERY_KEY, "label": RECOVERY_FIELD.label,
                "description": RECOVERY_FIELD.description,
                "group": "Stamina", "dtype": "s32", "type": "number",
                "value": read_field(data, RECOVERY_FIELD, "<"),
                "minimum": RECOVERY_MINIMUM, "maximum": RECOVERY_MAXIMUM,
                "enum": {}, "editable": True,
            }],
            "staminaContext": context,
            "staminaSourceCount": len(owners),
            "staminaSourceNames": [entry["name"] for entry in owners[:12]],
        }

    def edit(self, table, row_id, key, value):
        if table != EFFECT_TABLE:
            result = super().edit(table, row_id, key, value)
            if key in EQUIPMENT_REFERENCES.get(table, ()) or (
                    table == "EquipParamAccessory" and key == "refCategory"):
                self._equipment_sources = None
            return result
        row, start, data = self._effect_row(row_id)
        if key != RECOVERY_KEY:
            raise FormatError("Only the reviewed stamina-recovery modifier is editable")
        if (type(value) not in (int, float)
                or not RECOVERY_MINIMUM <= value <= RECOVERY_MAXIMUM
                or not math.isfinite(value) or int(value) != value):
            raise FormatError("Recovery adjustment must be a whole number from -100 to 100")
        changed = write_field(data, RECOVERY_FIELD, int(value), "<")
        self.plain[start:start + EFFECT_ROW_SIZE] = changed
        original = self.original_plain[start:start + EFFECT_ROW_SIZE]
        identity = (EFFECT_TABLE, row.row_id, RECOVERY_KEY)
        if read_field(original, RECOVERY_FIELD, "<") == int(value):
            self.dirty.discard(identity)
        else:
            self.dirty.add(identity)
        return self.read_row(table, row_id)
