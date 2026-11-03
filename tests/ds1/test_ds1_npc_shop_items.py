"""Shop stock lines name the item each line sells.

The NPC Shop tab renders a standard table with an icon column; every
stock line therefore resolves its equipId through its equipType to the
(item table, item id) the /api/icon endpoint needs. The mapping mirrors
the equipId Refs in the ShopLineupParam meta XML, and this file guards
that mirror against drift.
"""
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from plugins.ds1.formats import ItemDocument  # noqa: E402
from plugins.ds1 import shops  # noqa: E402

NPC = 251001


def _stock(lines):
    raw = make_archive(
        table_ids={'NpcParam': [NPC], 'ShopLineupParam': sorted(lines)},
        field_values={'ShopLineupParam': lines},
    )
    document = ItemDocument(raw)
    return shops.stock(document, NPC)


def test_stock_resolves_sold_item():
    rows = _stock({
        1100: {'equipId': 11210000, 'equipType': 3, 'value': 500, 'sellQuantity': 3},
        1101: {'equipId': 10000, 'equipType': 0, 'value': 750, 'sellQuantity': -1},
    })
    assert [(row['id'], row['item']) for row in rows] == [
        (1100, {'table': 'EquipParamGoods', 'id': 11210000}),
        (1101, {'table': 'EquipParamWeapon', 'id': 10000}),
    ]


def test_stock_item_absent_for_unknown_equip_type():
    rows = _stock({1100: {'equipId': 5, 'equipType': 9, 'value': 1, 'sellQuantity': 1}})
    assert rows[0]['item'] is None


def test_shop_item_tables_match_meta_refs():
    meta = ElementTree.parse(ROOT / 'plugins' / 'ds1' / 'metadata' / 'meta' / 'ShopLineupParam.xml')
    refs = meta.getroot().find('./Field/equipId').get('Refs')
    pairs = re.findall(r'(\w+)\(equipType=(\d+)\)', refs)
    assert pairs, refs
    assert shops.SHOP_ITEM_TABLES == {int(code): table for table, code in pairs}
