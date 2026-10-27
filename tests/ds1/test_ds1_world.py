"""World directory: enemy drops and treasure behavior. Merchant shops live on each merchant's NPC page."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive
from plugins.ds1 import data_map, mod_loader
from plugins.ds1.formats import (
    TABLES, WORLD_SUBTABS, FormatError, ItemDocument, schema,
)
from plugins.ds1.store import MARKER, RELATIVE, ItemStore


def project(tmp_path, raw=None):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive() if raw is None else raw)
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def test_world_metadata_matches_vanilla_shape():
    assert TABLES['ItemLotParam'] == (148, 2)
    assert TABLES['ShopLineupParam'] == (32, 1)
    assert TABLES['ObjActParam'] == (32, 1)
    lots = schema('ItemLotParam')
    assert lots['type'] == 'ITEMLOT_PARAM_ST' and lots['size'] == 148
    assert len(lots['names']) == 1524
    shops = schema('ShopLineupParam')
    assert shops['type'] == 'SHOP_LINEUP_PARAM' and shops['size'] == 32
    assert len(shops['names']) == 391
    treasure = schema('ObjActParam')
    assert treasure['type'] == 'OBJ_ACT_PARAM_ST' and treasure['size'] == 32
    assert len(treasure['names']) == 49
    categories = next(item for item in lots['fields'] if item['spec'].key == 'lotItemCategory01')
    assert categories['enum'] == {'-1': 'None', '0': 'Weapons', '268435456': 'Armor',
                                  '536870912': 'Rings', '1073741824': 'Goods'}
    equip = next(item for item in shops['fields'] if item['spec'].key == 'equipType')
    assert equip['enum'] == {'0': 'Weapon', '1': 'Armor', '2': 'Accessory', '3': 'Good',
                             '4': 'Attunement'}


def test_world_subtabs_list_their_rows():
    document = ItemDocument(make_archive())
    assert [entry[0] for entry in WORLD_SUBTABS] == ['drops', 'treasure']
    drops = document.list_rows('drops')
    assert {row['id'] for row in drops} == {100, 101, 102}
    assert all(row['table'] == 'ItemLotParam' for row in drops)
    assert next(row['name'] for row in drops if row['id'] == 100) == 'Drop 100'
    treasure = document.list_rows('treasure')
    assert {row['id'] for row in treasure} == {100, 101, 102}
    assert next(row['name'] for row in treasure if row['id'] == 100) == 'Treasure 100'


def test_world_detail_shows_reviewed_fields():
    document = ItemDocument(make_archive())
    fields = document.read_row('ItemLotParam', 100)['fields']
    assert len(fields) == 68 and all(field['editable'] for field in fields)
    assert next(field for field in fields if field['key'] == 'lotItemCategory01')['type'] == 'enum'
    fields = document.read_row('ShopLineupParam', 100)['fields']
    assert len(fields) == 8 and all(field['editable'] for field in fields)
    fields = document.read_row('ObjActParam', 100)['fields']
    assert len(fields) == 16
    assert {field['key'] for field in fields if not field['editable']} == {
        'objDummyId', 'spQualifiedType', 'spQualifiedType2', 'chrSorbType', 'eventKickTiming'}


def test_world_edits_roundtrip_and_validate():
    document = ItemDocument(make_archive())
    document.edit('ItemLotParam', 100, 'lotItemId01', 101)
    document.edit('ItemLotParam', 100, 'lotItemCategory01', 268435456)
    document.edit('ItemLotParam', 100, 'lotItemBasePoint01', 500)
    document.edit('ShopLineupParam', 100, 'value', 500)
    document.edit('ShopLineupParam', 100, 'sellQuantity', 3)
    document.edit('ShopLineupParam', 100, 'shopType', 2)
    document.edit('ObjActParam', 100, 'validDist', 80)
    assert document.dirty_count == 7
    reopened = ItemDocument(document.export())
    assert reopened.value('ItemLotParam', 100, 'lotItemId01') == 101
    assert reopened.value('ItemLotParam', 100, 'lotItemCategory01') == 268435456
    assert reopened.value('ShopLineupParam', 100, 'sellQuantity') == 3
    assert reopened.value('ObjActParam', 100, 'validDist') == 80
    for table, key, value in (('ItemLotParam', 'lotItemId01', 1000000001),
                              ('ItemLotParam', 'lotItemId01', 400),
                              ('ItemLotParam', 'lotItemCategory01', 5),
                              ('ItemLotParam', 'lotItemBasePoint01', 2001),
                              ('ShopLineupParam', 'sellQuantity', 10000),
                              ('ShopLineupParam', 'value', -2),
                              ('ShopLineupParam', 'shopType', 6),
                              ('ObjActParam', 'validDist', 60001),
                              ('ObjActParam', 'validDist', float('nan'))):
        try:
            document.edit(table, 100, key, value)
        except FormatError:
            continue
        raise AssertionError(f'{table} {key}={value} was accepted')
    for table, key in (('ObjActParam', 'spQualifiedType'), ('ObjActParam', 'chrSorbType'),
                       ('ObjActParam', 'objDummyId'), ('ObjActParam', 'eventKickTiming')):
        with pytest.raises(FormatError):
            document.edit(table, 100, key, 1)


def test_world_rows_merge_by_field_and_conflict_by_name():
    vanilla = make_archive()
    game = {RELATIVE: vanilla}

    def edited(*edits):
        document = ItemDocument(vanilla)
        for table, row, key, value in edits:
            document.edit(table, row, key, value)
        return document.export()

    def mod(name, params):
        return mod_loader.Mod(name, Path(name), {RELATIVE: params})

    label = next(item['spec'].label for item in schema('ItemLotParam')['fields']
                 if item['spec'].key == 'lotItemId01')
    a = mod('A', edited(('ItemLotParam', 100, 'lotItemId01', 101)))
    b = mod('B', edited(('ItemLotParam', 100, 'lotItemBasePoint01', 500)))
    result = mod_loader.compose(game, [a, b])
    assert result.conflicts == []
    merged = ItemDocument(result.files[RELATIVE])
    assert merged.value('ItemLotParam', 100, 'lotItemId01') == 101
    assert merged.value('ItemLotParam', 100, 'lotItemBasePoint01') == 500
    c = mod('C', edited(('ItemLotParam', 100, 'lotItemId01', 102)))
    result = mod_loader.compose(game, [a, c])
    assert [(c.part, c.mods) for c in result.conflicts] == [(f'Drops 100, {label}', ['A', 'C'])]
    assert ItemDocument(result.files[RELATIVE]).value('ItemLotParam', 100, 'lotItemId01') == 102


def test_state_reports_world_tabs_and_no_shop_tabs(tmp_path):
    game, mod = project(tmp_path)
    state = ItemStore(game, mod, False).state()
    assert [(tab['id'], tab['table'], tab['count']) for tab in state['worldTabs']] == [
        ('drops', 'ItemLotParam', 3), ('treasure', 'ObjActParam', 3)]
    assert 'shopTabs' not in state


def test_data_map_points_drops_treasure_and_shops_at_their_tabs(tmp_path):
    game, mod = project(tmp_path)
    rows = data_map.payload(ItemStore(game, mod, False))['rows']
    for filename, target, sub, label in (
            ('ItemLotParam.param', 'drops', 'drops', 'Drops'),
            ('ObjActParam.param', 'maps', 'treasure', 'Maps')):
        row = next(entry for entry in rows if entry['filename'] == filename)
        assert row['coverage'] == 'structured' and row['status'] == 'integrated'
        assert row['openable'] and row['target'] == target and row['sub'] == sub
        assert row['targets'] == [{'id': target, 'label': label}]
    row = next(entry for entry in rows if entry['filename'] == 'ShopLineupParam.param')
    assert row['coverage'] == 'structured' and row['status'] == 'integrated'
    assert row['openable'] and row['target'] == 'npcs' and row['sub'] == 'npcs'
    assert row['targets'] == [{'id': 'npcs', 'label': 'NPCs'}]
