"""Record links: every reference kind resolves, validates and names itself."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive  # noqa: E402
from ds1_effects_fixture import make_effects_archive  # noqa: E402
from plugins.ds1 import texts  # noqa: E402
from plugins.ds1.formats import FormatError, ItemDocument, field_link  # noqa: E402
from plugins.ds3.formats import write_field  # noqa: E402


def poke(document, table, row_id, key, value):
    """Set one field without validation, for link-resolution setups."""
    _, start, row = document._row(table, row_id)
    field = next(item['spec'] for item in document.schemas[table]['fields']
                 if item['spec'].key == key)
    document.plain[start:start + len(row)] = write_field(row, field, value, '<')


def links(document, table, row_id):
    return {entry['field']: entry
            for entry in document.read_row(table, row_id)['recordLinks']}


def test_plain_goods_and_magic_references_link():
    document = ItemDocument(make_archive())
    poke(document, 'EquipParamGoods', 100, 'replaceItemId', 101)
    poke(document, 'EquipParamGoods', 100, 'magicId', 102)
    found = links(document, 'EquipParamGoods', 100)
    assert found['replaceItemId']['kind'] == 'goods'
    assert found['replaceItemId']['table'] == 'EquipParamGoods'
    assert found['replaceItemId']['id'] == 101
    assert found['replaceItemId']['resolved']
    assert found['magicId']['kind'] == 'catalog'
    assert found['magicId']['table'] == 'Magic'
    assert found['magicId']['id'] == 102
    row = document.read_row('EquipParamGoods', 100)
    by_key = {field['key']: field for field in row['fields']}
    assert by_key['replaceItemId']['type'] == 'enum'
    assert by_key['magicId']['type'] == 'enum'
    assert set(by_key['magicId']['enum']) >= {'-1', '100', '101', '102'}
    _values, display = document.row_values('EquipParamGoods', 100)
    assert display['magicId'] == document.display_name('Magic', 102)


def test_switch_decides_the_targets_table():
    document = ItemDocument(make_effects_archive())
    poke(document, 'EquipParamAccessory', 100, 'refCategory', 2)
    poke(document, 'EquipParamAccessory', 100, 'refId', 6890)
    found = links(document, 'EquipParamAccessory', 100)
    assert (found['refId']['kind'], found['refId']['table']) == ('effect', 'SpEffectParam')
    poke(document, 'EquipParamAccessory', 100, 'refCategory', 1)
    assert 'refId' not in links(document, 'EquipParamAccessory', 100)
    row = document.read_row('EquipParamAccessory', 100)
    assert next(field for field in row['fields'] if field['key'] == 'refId')['type'] == 'number'


def test_behavior_refid_links_attacks_and_effects():
    document = ItemDocument(make_effects_archive())
    found = links(document, 'BehaviorParam', 100)
    assert (found['refId']['kind'], found['refId']['table']) == ('attack', 'AtkParam_Npc')
    assert 'refId' not in links(document, 'BehaviorParam', 101)
    poke(document, 'BehaviorParam', 101, 'refType', 2)
    poke(document, 'BehaviorParam', 101, 'refId', 6890)
    found = links(document, 'BehaviorParam', 101)
    assert (found['refId']['kind'], found['refId']['table']) == ('effect', 'SpEffectParam')


def test_projectile_attack_falls_through_to_npc():
    document = ItemDocument(make_archive())
    poke(document, 'Bullet', 100, 'atkId_Bullet', 101)
    found = links(document, 'Bullet', 100)
    assert (found['atkId_Bullet']['kind'], found['atkId_Bullet']['table']) == ('attack', 'AtkParam_Npc')


def test_shop_and_drop_links_follow_their_category():
    document = ItemDocument(make_archive())
    poke(document, 'ItemLotParam', 100, 'lotItemCategory01', 1073741824)
    poke(document, 'ItemLotParam', 100, 'lotItemId01', 101)
    found = links(document, 'ItemLotParam', 100)
    assert (found['lotItemId01']['kind'], found['lotItemId01']['table']) == ('goods', 'EquipParamGoods')
    poke(document, 'ItemLotParam', 100, 'lotItemCategory01', 0)
    found = links(document, 'ItemLotParam', 100)
    assert (found['lotItemId01']['kind'], found['lotItemId01']['table']) == ('catalog', 'EquipParamWeapon')
    poke(document, 'ShopLineupParam', 100, 'equipType', 3)
    poke(document, 'ShopLineupParam', 100, 'equipId', 102)
    found = links(document, 'ShopLineupParam', 100)
    assert (found['equipId']['kind'], found['equipId']['table']) == ('goods', 'EquipParamGoods')
    poke(document, 'ShopLineupParam', 100, 'equipType', 1)
    poke(document, 'ShopLineupParam', 100, 'equipId', 100)
    found = links(document, 'ShopLineupParam', 100)
    assert (found['equipId']['kind'], found['equipId']['table']) == ('catalog', 'EquipParamProtector')
    poke(document, 'ShopLineupParam', 100, 'equipType', 4)
    poke(document, 'ShopLineupParam', 100, 'equipId', 101)
    found = links(document, 'ShopLineupParam', 100)
    assert (found['equipId']['kind'], found['equipId']['table']) == ('catalog', 'Magic')
    assert found['equipId']['resolved']


def test_treasure_links_follow_their_qualified_type():
    document = ItemDocument(make_effects_archive())
    poke(document, 'ObjActParam', 100, 'spQualifiedType', 1)
    poke(document, 'ObjActParam', 100, 'spQualifiedId', 101)
    found = links(document, 'ObjActParam', 100)
    assert (found['spQualifiedId']['kind'], found['spQualifiedId']['table']) == ('goods', 'EquipParamGoods')
    poke(document, 'ObjActParam', 100, 'spQualifiedType', 2)
    poke(document, 'ObjActParam', 100, 'spQualifiedId', 6890)
    found = links(document, 'ObjActParam', 100)
    assert (found['spQualifiedId']['kind'], found['spQualifiedId']['table']) == ('effect', 'SpEffectParam')


def test_missing_targets_stay_visible_but_unresolved():
    document = ItemDocument(make_effects_archive())
    poke(document, 'EquipParamGoods', 100, 'replaceItemId', 400)
    found = links(document, 'EquipParamGoods', 100)
    assert found['replaceItemId']['resolved'] is False
    assert found['replaceItemId']['name'] == 'Missing item 400'
    _values, display = document.row_values('EquipParamGoods', 100)
    assert display['replaceItemId'] == 'Unknown (400)'


def test_none_values_have_no_link():
    document = ItemDocument(make_effects_archive())
    poke(document, 'EquipParamGoods', 100, 'replaceItemId', -1)
    poke(document, 'EquipParamGoods', 100, 'magicId', 0)
    found = links(document, 'EquipParamGoods', 100)
    assert 'replaceItemId' not in found
    assert 'magicId' not in found


def test_linked_writes_accept_only_existing_targets_or_none():
    document = ItemDocument(make_effects_archive())
    document.edit('EquipParamGoods', 100, 'replaceItemId', 101)
    document.edit('EquipParamGoods', 100, 'magicId', -1)
    document.edit('BehaviorParam', 100, 'refId', 102)
    with pytest.raises(FormatError):
        document.edit('EquipParamGoods', 100, 'replaceItemId', 400)
    with pytest.raises(FormatError):
        document.edit('EquipParamGoods', 100, 'magicId', 400)
    with pytest.raises(FormatError):
        document.edit('BehaviorParam', 100, 'refId', 400)
    with pytest.raises(FormatError):
        document.edit('EquipParamAccessory', 100, 'refId', 400)


def test_dialog_link_shows_the_yes_no_prompt():
    document = ItemDocument(make_archive())
    document.menu_texts = texts.MenuDocument(make_menu_archive(
        extra={'Event_text_.fmg': {10010710: 'Return to the last bonfire?'}}))
    assert document.menu_texts.event_text(10010710) == 'Return to the last bonfire?'
    assert document.menu_texts.event_text(999) is None
    poke(document, 'EquipParamGoods', 100, 'yesNoDialogMessageId', 10010710)
    dialogs = document.read_row('EquipParamGoods', 100)['dialogLinks']
    assert dialogs == [{'field': 'yesNoDialogMessageId', 'id': 10010710,
                        'text': 'Return to the last bonfire?'}]
    poke(document, 'EquipParamGoods', 101, 'yesNoDialogMessageId', 0)
    assert document.read_row('EquipParamGoods', 101)['dialogLinks'] == [
        {'field': 'yesNoDialogMessageId', 'id': 0, 'text': ''}]


def test_field_link_ignores_unlinked_tables():
    document = ItemDocument(make_archive())
    schemas = document.schemas['EquipParamAccessory']['fields']
    spec = next(item['spec'] for item in schemas if item['spec'].key == 'refId')
    poke(document, 'EquipParamAccessory', 100, 'refCategory', 0)
    assert field_link(document, 'EquipParamAccessory', 100, spec) is None


def test_gear_upgrade_fields_link_to_stats_records():
    # materialSetId and reinforceTypeId name Stats-tab records, so they show
    # what they point to, preview it and open it (kind "stat"), never a bare ID.
    document = ItemDocument(make_archive(table_ids={
        'EquipMtrlSetParam': [1000, 1001], 'ReinforceParamWeapon': [0, 100],
        'ReinforceParamProtector': [0, 200]}))
    for table, set_id, reinforce_id, reinforce_table, noun in (
            ('EquipParamWeapon', 1000, 100, 'ReinforceParamWeapon', 'weapon upgrade table'),
            ('EquipParamProtector', 1001, 200, 'ReinforceParamProtector', 'armor upgrade table')):
        poke(document, table, 100, 'materialSetId', set_id)
        poke(document, table, 100, 'reinforceTypeId', reinforce_id)
        found = links(document, table, 100)
        assert (found['materialSetId']['kind'], found['materialSetId']['table']) == ('stat', 'EquipMtrlSetParam')
        assert found['materialSetId']['id'] == set_id and found['materialSetId']['resolved']
        assert found['materialSetId']['name'] == document.display_name('EquipMtrlSetParam', set_id)
        assert (found['reinforceTypeId']['kind'], found['reinforceTypeId']['table']) == ('stat', reinforce_table)
        assert found['reinforceTypeId']['resolved']
        assert document.link_noun('stat', reinforce_table) == noun
        by_key = {field['key']: field for field in document.read_row(table, 100)['fields']}
        assert by_key['materialSetId']['type'] == by_key['reinforceTypeId']['type'] == 'enum'
        assert str(set_id) in by_key['materialSetId']['enum']
        _values, display = document.row_values(table, 100)
        assert display['reinforceTypeId'] == document.display_name(reinforce_table, reinforce_id)
        with pytest.raises(FormatError):
            document._write(table, 100, 'materialSetId', 5555)


def test_weapon_scaling_curves_link_to_stats_curves():
    document = ItemDocument(make_archive(table_ids={'CalcCorrectGraph': [0, 5]}))
    poke(document, 'EquipParamWeapon', 100, 'correctType', 5)
    found = links(document, 'EquipParamWeapon', 100)
    assert (found['correctType']['kind'], found['correctType']['table']) == ('stat', 'CalcCorrectGraph')
    assert found['correctType']['resolved']
