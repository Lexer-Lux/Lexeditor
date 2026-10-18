"""Starting classes and starting gifts: who the player begins as, and with what.

Classes are rows 3000-3009, gifts rows 2401-2408. Every class row has a
twin a thousand IDs below it (3000 mirrors 2000); the two hold the same
stats and gear, so editing a class writes both and they can never drift
apart. Only the draw type is not mirrored: the twins intentionally differ
there. Gifts grant their item (or ring) from their item and ring slots.
"""
from __future__ import annotations

TABLE = 'CharaInitParam'

#: The live starting kits, in class order; the screen lists these.
CLASS_ROWS = tuple(range(3000, 3010))

#: The eight gift rows, in gift-menu order; the ninth gift, None, is no row.
GIFT_ROWS = tuple(range(2401, 2409))

#: Each class row and its twin, both directions.
TWINS = {row: row - 1000 for row in CLASS_ROWS} | {row - 1000: row for row in CLASS_ROWS}

#: The twin rows intentionally differ here, so it is never mirrored.
UNMIRRORED = frozenset({'npcPlayerDrawType'})

#: What a gift grants: its item slots with counts, and its ring slots.
GIFT_FIELDS = tuple([f'item_{index:02d}' for index in range(1, 11)]
                    + [f'itemNum_{index:02d}' for index in range(1, 11)]
                    + [f'equip_Accessory{index:02d}' for index in range(1, 6)])

#: Detail sections by field; the rest stay under Properties.
GROUPS = {
    'soulLv': 'Basics', 'baseVit': 'Basics', 'baseWil': 'Basics', 'baseEnd': 'Basics',
    'baseStr': 'Basics', 'baseDex': 'Basics', 'baseMag': 'Basics', 'baseFai': 'Basics',
    'baseDurability': 'Basics', 'baseHp': 'Basics', 'baseMp': 'Basics', 'baseSp': 'Basics',
    'soul': 'Basics', 'baseRec_mp': 'Basics', 'baseRec_sp': 'Basics', 'red_Falldam': 'Basics',
    'npcPlayerSex': 'Basics', 'vowType': 'Basics',
    'equip_Wep_Right': 'Starting gear', 'equip_Subwep_Right': 'Starting gear',
    'equip_Wep_Left': 'Starting gear', 'equip_Subwep_Left': 'Starting gear',
    'equip_Helm': 'Starting gear', 'equip_Armer': 'Starting gear', 'equip_Gaunt': 'Starting gear',
    'equip_Leg': 'Starting gear', 'equip_Arrow': 'Starting gear', 'equip_Bolt': 'Starting gear',
    'equip_SubArrow': 'Starting gear', 'equip_SubBolt': 'Starting gear',
    'equip_Accessory01': 'Starting gear', 'equip_Accessory02': 'Starting gear',
    'equip_Accessory03': 'Starting gear', 'equip_Accessory04': 'Starting gear',
    'equip_Accessory05': 'Starting gear', 'equip_Skill_01': 'Starting gear',
    'equip_Skill_02': 'Starting gear', 'equip_Skill_03': 'Starting gear',
    'equip_Spell_01': 'Starting spells', 'equip_Spell_02': 'Starting spells',
    'equip_Spell_03': 'Starting spells', 'equip_Spell_04': 'Starting spells',
    'equip_Spell_05': 'Starting spells', 'equip_Spell_06': 'Starting spells',
    'equip_Spell_07': 'Starting spells',
    **{f'item_{index:02d}': 'Starting items' for index in range(1, 11)},
    **{f'itemNum_{index:02d}': 'Starting items' for index in range(1, 11)},
    'bodyScaleHead': 'Body & gestures', 'bodyScaleBreast': 'Body & gestures',
    'bodyScaleAbdomen': 'Body & gestures', 'bodyScaleArm': 'Body & gestures',
    'bodyScaleLeg': 'Body & gestures', 'gestureId0': 'Body & gestures',
    'gestureId1': 'Body & gestures', 'gestureId2': 'Body & gestures',
    'gestureId3': 'Body & gestures', 'gestureId4': 'Body & gestures',
    'gestureId5': 'Body & gestures', 'gestureId6': 'Body & gestures',
}

#: What the picker refusal calls one row of each linked table.
REF_NOUNS = {'EquipParamWeapon': 'weapon', 'EquipParamProtector': 'armor piece',
             'EquipParamAccessory': 'accessory', 'Magic': 'spell'}


def catalog_links(document, table):
    """{field key: linked table} for the catalog-linked fields of one table."""
    if table != TABLE:
        return {}
    return {item['spec'].key: item['spec'].reference
            for item in document.schemas[table]['fields']
            if (item['spec'].reference or '') in REF_NOUNS}


class CatalogReferences:
    """One linked table as picker choices: every row by its live name.

    Both -1 and 0 read as None: classes leave slots at -1, gift rows at 0,
    and the game treats either as empty.
    """

    def __init__(self, document, table: str):
        self.choices = {'-1': 'None', '0': 'None'}
        if table not in document.params:
            return
        for row in document.params[table].rows:
            self.choices[str(row.row_id)] = document.display_name(table, row.row_id, row)
