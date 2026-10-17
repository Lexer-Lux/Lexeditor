"""Merchant shop attribution is by Smithbox prefix, with pinned exceptions."""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ds1 import shops  # noqa: E402


def document(rows, names, values):
    params = {'ShopLineupParam': SimpleNamespace(
        rows=[SimpleNamespace(row_id=row_id) for row_id in rows])}
    schemas = {'ShopLineupParam': {'names': names}}
    doc = SimpleNamespace(params=params, schemas=schemas)
    doc.display_name = lambda table, row_id, row=None: names.get(row_id, '')
    doc.value = lambda table, row_id, key: values[(row_id, key)]
    return doc


NAMES = {
    1400: '[Andre] Repair Powder',
    1401: '[Andre] Smithbox',
    5000: '[Griggs of Vinheim - Logan in DA] Soul Arrow',
    2000: '[Griggs of Vinheim] Soul Arrow',
    1134: '',
    3000: '[Laurentius] Fireball',
    1: 'Divine Blessing',
}


def values_for(rows):
    return {(row_id, key): value
            for row_id in rows
            for key, value in (('value', row_id), ('sellQuantity', -1))}


def test_prefix_stock_in_shop_order():
    doc = document([1401, 1400], NAMES, values_for([1400, 1401]))
    rows = shops.stock(doc, 264000)
    assert [(row['id'], row['name']) for row in rows] == [
        (1400, 'Repair Powder'), (1401, 'Smithbox')]
    assert rows[0]['value'] == 1400 and rows[0]['sellQuantity'] == -1
    assert shops.stock(doc, 999999) == []


def test_logan_serves_the_archives_block_not_griggs():
    doc = document([5000, 2000], NAMES, values_for([5000, 2000]))
    assert [row['id'] for row in shops.stock(doc, 6030)] == [5000]
    assert [row['id'] for row in shops.stock(doc, 6040)] == [2000]


def test_nameless_dried_finger_row_joins_the_male_merchant():
    doc = document([1134], NAMES, values_for([1134]))
    assert [row['id'] for row in shops.stock(doc, 251001)] == [1134]
    assert shops.stock(doc, 251000) == []


def test_laurentius_and_unprefixed_rows_stay_global_only():
    doc = document([3000, 1], NAMES, values_for([3000, 1]))
    assert shops.stock(doc, 999999) == []
    assert not shops.is_merchant(999999)
    assert 'Laurentius' in shops.MERCHANT_PREFIXES
    assert shops.MERCHANT_PREFIXES['Laurentius'] == ()


def test_bad_npc_ids_answer_empty():
    doc = document([1400], NAMES, values_for([1400]))
    assert shops.stock(doc, '') == []
    assert shops.stock(doc, 'Andre') == []
    assert shops.stock(doc, None) == []


def test_every_mapped_merchant_is_admitted():
    for prefix, ids in shops.MERCHANT_PREFIXES.items():
        for npc in ids:
            assert shops.is_merchant(npc), (prefix, npc)
    assert shops.is_merchant(251001)
