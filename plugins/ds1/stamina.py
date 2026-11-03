"""Reviewed stamina-effect editing for Dark Souls Remastered.

This is an additive SpEffect adjustment, NOT the engine's base recovery rate.
The PARAM directory codec is reused from the existing DS1/DS3 adapter.
Only the documented four-byte cell is changed; all other bytes are opaque.

Layout source: Smithbox 057b417887cc7d0ddc8001602be3f5339f42c74f,
Smithbox.Release/Output/Assets/PARAM/DS1R/Defs/SpEffect.xml.
There are 46 consecutive four-byte fields before staminaRecoverChangeSpeed.
The upstream bounds are -100..100. See credits.md for provenance.
"""
import math
import struct

from .formats import FormatError, ItemDocument, ParamView

TABLE = "SpEffectParam"
FIELD = "staminaRecoverChangeSpeed"
OFFSET = 0xB8
CELL_END = OFFSET + 4
MINIMUM, MAXIMUM = -100, 100
EFFECT_NAMES = {
    1090: "Power Within",
    2013: "Chloranthy Ring",
    3040: "Green Blossom",
    6890: "Grass Crest Shield",
    6920: "Mask of the Child",
    **{6200 + slot * 10 + level: f"Armor recovery penalty: {name}, effect {level + 1}"
       for slot, name in enumerate(("head", "body", "arms", "legs"))
       for level in range(4)},
}
HELP = ("Points added to stamina recovery speed while this effect is active. "
        "Negative values slow recovery. Changing a shared effect changes every use of it.")
TAB = {
    "id": "stamina", "label": "Stamina effects", "table": TABLE,
    "help": ("Edit reviewed recovery bonuses and armor penalties. "
             "These values are effect adjustments, not the player's base recovery rate. "
             "Armor penalty effects are not equip-load tiers. Names are reference labels."),
}


class RecoveryEffects:
    """Bounded projection onto a documented PARAM prefix, not a full schema."""

    def __init__(self, document):
        self.document = document
        member = document.members.get(TABLE + ".param")
        if member is None:
            raise FormatError("This archive does not contain stamina effects.")
        payload = document.plain[member.offset:member.offset + member.size]
        if len(payload) < 48 or payload[44:48] != b"\0\x02\0\0":
            raise FormatError("Unsupported stamina-effect PARAM header")
        param = ParamView(payload)
        if param.big_endian or param.param_type != "SP_EFFECT_PARAM_ST" or param.header_version != 1:
            raise FormatError("Unsupported stamina-effect layout/version")
        if not param.rows or len({row.row_id for row in param.rows}) != len(param.rows):
            raise FormatError("Empty or duplicate stamina-effect row IDs")
        directory_end = ((64 if param.format2d & 4 or param.format2d & 3 == 3 else 48)
                         + len(param.rows) * (24 if param.long_offsets else 12))
        if not directory_end <= param.strings_offset <= len(payload):
            raise FormatError("Invalid stamina-effect strings boundary")
        rows = sorted(param.rows, key=lambda row: row.data_offset)
        ends = [row.data_offset for row in rows[1:]] + [param.strings_offset]
        self.cells = {}
        for row, end in zip(rows, ends):
            if row.data_offset < directory_end or row.data_offset + CELL_END > end:
                raise FormatError("Overlapping or truncated stamina-effect rows")
            self.cells[row.row_id] = member.offset + row.data_offset + OFFSET

    def _cell(self, row_id):
        if type(row_id) is not int or row_id not in EFFECT_NAMES or row_id not in self.cells:
            raise FormatError("This is not a reviewed stamina effect")
        return self.cells[row_id]

    def rows(self):
        return [{"id": row_id, "name": name, "table": TABLE}
                for row_id, name in EFFECT_NAMES.items() if row_id in self.cells]

    def read(self, row_id):
        value = struct.unpack_from("<i", self.document.plain, self._cell(row_id))[0]
        return {"id": row_id, "table": TABLE, "name": EFFECT_NAMES[row_id], "fields": [{
            "key": FIELD, "label": "Stamina recovery adjustment", "description": HELP,
            "group": "Stamina recovery", "dtype": "s32", "type": "number", "value": value,
            "minimum": MINIMUM, "maximum": MAXIMUM, "enum": {}, "editable": True,
        }]}

    def edit(self, row_id, key, value):
        cell = self._cell(row_id)
        if key != FIELD:
            raise FormatError("This field is protected")
        if type(value) not in (int, float) or not math.isfinite(value):
            raise FormatError("Enter a finite number")
        if int(value) != value:
            raise FormatError("Enter a whole number")
        if not MINIMUM <= value <= MAXIMUM:
            raise FormatError(f"Stamina recovery adjustment must be between {MINIMUM} and {MAXIMUM}")
        struct.pack_into("<i", self.document.plain, cell, int(value))
        dirty_key = (TABLE, row_id, FIELD)
        if self.document.plain[cell:cell + 4] == self.document.original_plain[cell:cell + 4]:
            self.document.dirty.discard(dirty_key)
        else:
            self.document.dirty.add(dirty_key)
        return self.read(row_id)


class StaminaDocument(ItemDocument):
    """Keep existing item/archive behavior and add the optional effects view."""

    def recovery_effects(self):
        if not hasattr(self, "_recovery_effects"):
            self._recovery_effects = RecoveryEffects(self)
        return self._recovery_effects

    def stamina_tabs(self):
        # Older/minimal projects remain usable. Malformed optional data is
        # reported when this view is opened, never silently made editable.
        return [dict(TAB)] if TABLE + ".param" in self.members else []

    def list_rows(self, tab):
        if tab == "stamina":
            return self.recovery_effects().rows()
        return super().list_rows(tab)

    def read_row(self, table, row_id):
        if table == TABLE:
            return self.recovery_effects().read(row_id)
        return super().read_row(table, row_id)

    def edit(self, table, row_id, key, value):
        if table == TABLE:
            return self.recovery_effects().edit(row_id, key, value)
        return super().edit(table, row_id, key, value)
