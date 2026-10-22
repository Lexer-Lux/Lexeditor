"""Upgrade material sets: the items each upgrade level spends, and how many.

A weapon or armor piece names a base set (its materialSetId); each upgrade
level adds its Material Set Offset, and the resulting set lists what the
forge takes: up to five inventory items with a count each. A count of -1
leaves its slot empty. The forge's soul price is not stored in any
parameter; the game computes it, so it cannot be edited here.
"""

TABLE = 'EquipMtrlSetParam'
GOODS_TABLE = 'EquipParamGoods'

SLOTS = ('01', '02', '03', '04', '05')


def goods_keys(document, table, row_id):
    """Yield the keys of this row that name an inventory item."""
    for item in document.schemas[table]['fields']:
        if (item['spec'].reference or '') == GOODS_TABLE:
            yield item['spec'].key


class GoodsReferences:
    """The archive's inventory items as picker choices, by live name."""

    def __init__(self, document):
        self.document = document
        self.choices = {'-1': 'None', '0': 'None'}
        if GOODS_TABLE not in document.params:
            return
        for row in document.params[GOODS_TABLE].rows:
            self.choices[str(row.row_id)] = document.display_name(GOODS_TABLE, row.row_id, row)


def describe_set(document, row_id):
    """'Titanite Shard x 2' for a set; 'Empty set' when it spends nothing."""
    parts = []
    for slot in SLOTS:
        item = document.value(TABLE, row_id, 'materialId' + slot)
        if item is None or int(item) < 0:
            continue
        try:
            name = document.display_name(GOODS_TABLE, int(item))
        except Exception:
            name = None
        count = document.value(TABLE, row_id, 'itemNum' + slot)
        parts.append(f'{name or f"Item {item}"} x {count}')
    return ', '.join(parts) if parts else 'Empty set'


REINFORCE_TABLES = {'EquipParamWeapon': 'ReinforceParamWeapon',
                    'EquipParamProtector': 'ReinforceParamProtector'}


def set_materials(document, set_id):
    """[(item_id, name, count)] for one set, [] when it spends nothing.

    None when the set row itself is missing.
    """
    try:
        rows = document._rows_by_id.get(TABLE, {})
    except AttributeError:
        rows = {}
    if int(set_id) not in rows and TABLE in getattr(document, 'params', {}):
        return None
    found = []
    for slot in SLOTS:
        try:
            item = document.value(TABLE, set_id, 'materialId' + slot)
        except Exception:
            return None
        if item is None or int(item) < 0:
            continue
        try:
            name = document.display_name(GOODS_TABLE, int(item))
        except Exception:
            name = None
        try:
            count = document.value(TABLE, set_id, 'itemNum' + slot)
        except Exception:
            count = '?'
        found.append((int(item), name or f'Item {item}', count))
    return found


def upgrade_levels(document, gear_table, gear_row_id, base_set=None, reinforce_base=None):
    """[(level, set_id)] for levels 1..max, following the reinforce rows.

    Level N spends materialSetId plus the Material Set Offset stored in
    the reinforce row for reinforceTypeId + N. Level 0 costs nothing to
    already be, so it is not listed. [] when the piece has no upgrade
    rows (an unreviewed type or a test row without them).
    """
    reinforce_table = REINFORCE_TABLES.get(gear_table)
    if reinforce_table is None:
        return []
    try:
        if base_set is None:
            base_set = document.value(gear_table, gear_row_id, 'materialSetId')
        if reinforce_base is None:
            reinforce_base = document.value(gear_table, gear_row_id, 'reinforceTypeId')
        base_set, reinforce_base = int(base_set), int(reinforce_base)
    except Exception:
        return []
    if base_set < 0 or reinforce_base < 0:
        return []
    try:
        rows = document._rows_by_id.get(reinforce_table, {})
    except AttributeError:
        return []
    if reinforce_base not in rows:
        return []
    levels = []
    for level in range(1, 16):
        row_id = reinforce_base + level
        if row_id not in rows:
            break
        try:
            offset = int(document.value(reinforce_table, row_id, 'materialSetId'))
        except Exception:
            break
        levels.append((level, base_set + offset))
    return levels


def describe_path(document, gear_table, gear_row_id, base_set=None, reinforce_base=None):
    """The whole upgrade path as one line, e.g. '+1-3: Titanite Shard 1/1/2'.

    Consecutive levels spending the same items share a group with their
    counts slash-separated. Falls back to the base set alone when the
    piece has no upgrade rows.
    """
    try:
        if base_set is None:
            base_set = int(document.value(gear_table, gear_row_id, 'materialSetId'))
        else:
            base_set = int(base_set)
    except Exception:
        return 'Empty set'
    levels = upgrade_levels(document, gear_table, gear_row_id, base_set, reinforce_base)
    if not levels:
        try:
            return describe_set(document, base_set)
        except Exception:
            return 'Empty set'
    detailed = []
    for level, set_id in levels:
        detailed.append((level, set_id, set_materials(document, set_id)))
    groups = []
    start = None
    current_key = None
    current_levels = []
    for level, set_id, materials in detailed:
        key = ('missing', set_id) if materials is None else tuple(item[0] for item in materials)
        if start is None:
            start, current_key, current_levels = level, key, [(level, set_id, materials)]
            continue
        if key == current_key and level == current_levels[-1][0] + 1:
            current_levels.append((level, set_id, materials))
            continue
        label = f'+{start}' if len(current_levels) == 1 else f'+{start}-{current_levels[-1][0]}'
        groups.append((label, [entry[2] for entry in current_levels],
                       sorted({entry[1] for entry in current_levels})))
        start, current_key, current_levels = level, key, [(level, set_id, materials)]
    label = f'+{start}' if len(current_levels) == 1 else f'+{start}-{current_levels[-1][0]}'
    groups.append((label, [entry[2] for entry in current_levels],
                   sorted({entry[1] for entry in current_levels})))
    parts = []
    for label, per_level, set_ids in groups:
        if per_level and per_level[0] is None:
            if len(set_ids) == 1:
                parts.append(f'{label}: Missing set {set_ids[0]}')
            else:
                parts.append(f'{label}: Missing sets')
            continue
        if not per_level or not per_level[0]:
            parts.append(f'{label}: free')
            continue
        if len(per_level[0]) == 1:
            name = per_level[0][0][1]
            counts = '/'.join(str(level[0][2]) for level in per_level)
            parts.append(f'{label}: {name} {counts}')
        else:
            joined = []
            for index in range(len(per_level[0])):
                name = per_level[0][index][1]
                counts = '/'.join(str(level[index][2]) for level in per_level)
                joined.append(f'{name} {counts}')
            parts.append(f'{label}: ' + ', '.join(joined))
    return ' \u00b7 '.join(parts)


def path_table(document, gear_table, gear_row_id, base_set=None, reinforce_base=None):
    """One row per upgrade level: level, set id, materials and description."""
    levels = upgrade_levels(document, gear_table, gear_row_id, base_set, reinforce_base)
    rows = []
    for level, set_id in levels:
        materials = set_materials(document, set_id)
        if materials is None:
            rows.append({'level': level, 'setId': set_id, 'materials': [],
                         'description': f'Missing set {set_id}'})
            continue
        try:
            description = describe_set(document, set_id)
        except Exception:
            description = 'Empty set'
        rows.append({'level': level, 'setId': set_id,
                     'materials': [{'id': item, 'name': name, 'count': count}
                                   for item, name, count in materials],
                     'description': description})
    return rows
