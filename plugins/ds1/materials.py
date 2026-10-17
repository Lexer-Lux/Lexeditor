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
