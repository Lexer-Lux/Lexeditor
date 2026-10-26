"""Stats tab: curves, upgrades, materials, classes and gifts."""
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive, make_menu_archive
from ds1_stats_fixture import make_stats_archive, CURVE_ROWS, MATERIAL_ROWS, CHARA_ROWS
from plugins.ds1.charainit import GIFT_FIELDS
from plugins.ds1 import data_map, texts
from plugins.ds1.formats import (
    GRAPH_TABLE, STATS_FIELDS, STATS_SUBTABS, TABLES, FormatError, ItemDocument,
    schema, stats_fields,
)
from plugins.ds1.plugin import DS1Session
from plugins.ds1.store import MARKER, RELATIVE, ItemStore


def project(tmp_path, raw=None):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_stats_archive() if raw is None else raw)
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def test_curve_metadata_matches_vanilla_shape():
    assert GRAPH_TABLE == 'CalcCorrectGraph'
    assert TABLES[GRAPH_TABLE] == (80, 1)
    definition = schema(GRAPH_TABLE)
    assert definition['type'] == 'CACL_CORRECT_GRAPH_ST' and definition['size'] == 80
    editable = {item['spec'].key: item for item in definition['fields'] if item['editable']}
    assert set(editable) == set(STATS_FIELDS[GRAPH_TABLE])
    assert editable['stageMaxVal0']['min'] == 0 and editable['stageMaxVal0']['max'] == 999
    assert editable['stageMaxGrowVal0']['min'] == 0 and editable['stageMaxGrowVal0']['max'] == 9999
    assert editable['adjPt_maxGrowVal0']['min'] == -99 and editable['adjPt_maxGrowVal0']['max'] == 99
    assert editable['boundry_value']['min'] == 0 and editable['boundry_value']['max'] == 1000000
    assert definition['names'][100] == 'Max HP (Vitality Stat)'
    assert definition['names'][200] == 'Level up cost'


def test_stats_subtabs_list_their_rows():
    document = ItemDocument(make_stats_archive())
    assert [entry[0] for entry in STATS_SUBTABS] == ['curves', 'weapon-upgrades',
                                                      'armor-upgrades', 'upgrade-materials',
                                                      'starting-classes', 'starting-gifts',
                                                      'levelup']
    curves = document.list_rows('curves')
    assert {row['id'] for row in curves} == set(CURVE_ROWS)
    assert all(row['table'] == GRAPH_TABLE for row in curves)
    assert all(row['values'] and row['display'] is not None for row in curves)
    assert next(row['name'] for row in curves if row['id'] == 100) == 'Max HP (Vitality Stat)'
    upgrades = document.list_rows('weapon-upgrades')
    assert {row['id'] for row in upgrades} == {100, 101, 102}
    assert all(row['table'] == 'ReinforceParamWeapon' for row in upgrades)
    assert next(row['name'] for row in upgrades if row['id'] == 100) == 'Crystal +0'
    armors = document.list_rows('armor-upgrades')
    assert {row['id'] for row in armors} == {100, 101, 102}
    assert all(row['table'] == 'ReinforceParamProtector' for row in armors)
    assert next(row['name'] for row in armors if row['id'] == 100) == 'Armor - Unique +0'
    materials = document.list_rows('upgrade-materials')
    assert {row['id'] for row in materials} == set(MATERIAL_ROWS)
    assert all(row['table'] == 'EquipMtrlSetParam' for row in materials)
    stone = document.display_name('EquipParamGoods', 100)
    key = document.display_name('EquipParamGoods', 101)
    assert next(row['name'] for row in materials if row['id'] == 1) == f'{stone} x 1'
    assert next(row['name'] for row in materials if row['id'] == 2) == f'{stone} x 2, {key} x 3'
    assert next(row['name'] for row in materials if row['id'] == 3) == 'Empty set'


def test_stats_detail_shows_only_stat_fields():
    document = ItemDocument(make_stats_archive())
    assert stats_fields('weapons', 'EquipParamWeapon') is None
    assert stats_fields('curves', GRAPH_TABLE) is None
    assert stats_fields('weapon-upgrades', 'ReinforceParamWeapon') is None
    assert stats_fields('armor-upgrades', 'ReinforceParamProtector') is None
    assert stats_fields('upgrade-materials', 'EquipMtrlSetParam') is None
    assert stats_fields('starting-classes', 'CharaInitParam') is None
    assert stats_fields('starting-gifts', 'CharaInitParam') == GIFT_FIELDS
    weapon_fields = ('properStrength', 'properAgility', 'properMagic', 'properFaith',
                     'correctStrength', 'correctAgility', 'correctMagic', 'correctFaith',
                     'correctType', 'isLuckCorrect', 'levelSyncCorrectID')
    row = document.read_row('EquipParamWeapon', 100, only=weapon_fields)
    assert [field['key'] for field in row['fields']] == [
        field['key'] for field in document.read_row('EquipParamWeapon', 100)['fields']
        if field['key'] in weapon_fields]
    assert {field['key'] for field in row['fields']} == set(weapon_fields)
    graph = next(field for field in row['fields'] if field['key'] == 'correctType')
    assert not graph['editable']
    row = document.read_row('Magic', 100, only=('requirementIntellect', 'requirementFaith',
                                                'slotLength', 'stamina'))
    assert {field['key'] for field in row['fields']} == {
        'requirementIntellect', 'requirementFaith', 'slotLength', 'stamina'}
    assert all(field['editable'] for field in row['fields'])
    stamina = next(field for field in row['fields'] if field['key'] == 'stamina')
    assert stamina['label'] == 'Stamina Consumption'
    assert stamina['minimum'] == 0 and stamina['maximum'] == 9999
    assert stamina['description'] == ('Each cast of this spell spends '
                                     'this much stamina. All spells cost 0 in vanilla DS1.')
    curves = document.read_row(GRAPH_TABLE, 200)
    assert {field['key'] for field in curves['fields']} == set(STATS_FIELDS[GRAPH_TABLE])
    groups = {field['key']: field['group'] for field in curves['fields']}
    assert groups['stageMaxVal0'] == 'Thresholds' and groups['stageMaxGrowVal4'] == 'Growth'
    assert groups['adjPt_maxGrowVal0'] == 'Curve shape' and groups['boundry_value'] == 'Level-up cost'
    weapon = document.read_row('ReinforceParamWeapon', 100)
    assert {field['key'] for field in weapon['fields']} == set(STATS_FIELDS['ReinforceParamWeapon'])
    assert all(field['editable'] for field in weapon['fields'])
    assert weapon['name'] == 'Crystal +0'
    armor = document.read_row('ReinforceParamProtector', 100)
    assert {field['key'] for field in armor['fields']} == set(STATS_FIELDS['ReinforceParamProtector'])
    assert all(field['editable'] for field in armor['fields'])
    sets = document.read_row('EquipMtrlSetParam', 1)
    assert {field['key'] for field in sets['fields']} == set(STATS_FIELDS['EquipMtrlSetParam'])
    assert all(field['editable'] for field in sets['fields'])
    groups = {field['key']: field['group'] for field in sets['fields']}
    assert groups['materialId01'] == groups['itemNum01'] == groups['isDisableDispNum01'] == 'Material 1'
    assert groups['isDisableDispNum05'] == 'Material 5'
    picker = next(field for field in sets['fields'] if field['key'] == 'materialId01')
    assert picker['type'] == 'enum'
    assert picker['enum']['-1'] == 'None'
    assert picker['enum']['100'] == document.display_name('EquipParamGoods', 100)
    assert picker['enum']['0'] == 'None'
    assert set(picker['enum']) == {'-1', '0', '100', '101', '102'}
    count = next(field for field in sets['fields'] if field['key'] == 'itemNum01')
    assert count['type'] == 'number' and (count['minimum'], count['maximum']) == (-1, 99)
    hide = next(field for field in sets['fields'] if field['key'] == 'isDisableDispNum01')
    assert hide['type'] == 'bool'


def test_spell_stamina_cost_edits_roundtrip_and_validate():
    document = ItemDocument(make_stats_archive())
    document.edit('Magic', 100, 'stamina', 25)
    assert document.value('Magic', 100, 'stamina') == 25
    assert ItemDocument(document.export()).value('Magic', 100, 'stamina') == 25
    assert document.dirty_count == 1
    for value in (-1, 10000, 2.5, float('nan')):
        try:
            document.edit('Magic', 100, 'stamina', value)
        except FormatError:
            continue
        raise AssertionError(f'stamina={value} was accepted')
    assert document.value('Magic', 100, 'stamina') == 25


def test_curve_edits_roundtrip_and_validate():
    document = ItemDocument(make_stats_archive())
    document.edit(GRAPH_TABLE, 0, 'stageMaxGrowVal2', 55.5)
    document.edit(GRAPH_TABLE, 200, 'boundry_value', 20)
    assert document.value(GRAPH_TABLE, 0, 'stageMaxGrowVal2') == 55.5
    assert document.value(GRAPH_TABLE, 200, 'boundry_value') == 20
    assert document.dirty_count == 2
    reopened = ItemDocument(document.export())
    assert reopened.value(GRAPH_TABLE, 0, 'stageMaxGrowVal2') == 55.5
    assert reopened.value(GRAPH_TABLE, 200, 'boundry_value') == 20
    for key, value in (('stageMaxVal0', -1), ('stageMaxVal0', 1000),
                       ('stageMaxGrowVal0', 10000), ('adjPt_maxGrowVal0', 100),
                       ('boundry_value', -1), ('boundry_value', float('nan'))):
        try:
            document.edit(GRAPH_TABLE, 0, key, value)
        except FormatError:
            continue
        raise AssertionError(f'{key}={value} was accepted')
    with pytest.raises(FormatError):
        document.edit(GRAPH_TABLE, 0, 'pad', 0)


def test_archives_without_curves_fail_with_a_complete_archive_hint():
    document = ItemDocument(make_archive())
    assert GRAPH_TABLE not in document.params
    with pytest.raises(FormatError, match='complete Remastered parameter archive'):
        document.list_rows('curves')
    with pytest.raises(FormatError, match='complete Remastered parameter archive'):
        document.read_row(GRAPH_TABLE, 0)
    # The other Stats lists do not need the curve table.
    assert len(document.list_rows('weapon-upgrades')) == 3
    assert len(document.list_rows('armor-upgrades')) == 3
    with pytest.raises(FormatError, match='complete Remastered parameter archive'):
        document.list_rows('upgrade-materials')


def test_state_reports_stats_tabs(tmp_path):
    game, mod = project(tmp_path)
    tabs = ItemStore(game, mod, False).state()['statsTabs']
    assert [(tab['id'], tab['count']) for tab in tabs] == [
        ('curves', 3),
        ('weapon-upgrades', 3), ('armor-upgrades', 3), ('upgrade-materials', 3),
        ('starting-classes', 1), ('starting-gifts', 2), ('levelup', 0)]
    game, mod = project(tmp_path / 'plain', make_archive())
    tabs = ItemStore(game, mod, False).state()['statsTabs']
    assert [(tab['id'], tab['count']) for tab in tabs] == [
        ('curves', 0),
        ('weapon-upgrades', 3), ('armor-upgrades', 3), ('upgrade-materials', 0),
        ('starting-classes', 0), ('starting-gifts', 0), ('levelup', 0)]


def test_data_map_points_curves_at_stats(tmp_path):
    game, mod = project(tmp_path)
    rows = data_map.payload(ItemStore(game, mod, False))['rows']
    curves = next(row for row in rows if row['filename'] == 'CalcCorrectGraph.param')
    assert curves['coverage'] == 'structured' and curves['status'] == 'integrated'
    assert curves['openable'] and curves['target'] == 'stats' and curves['sub'] == 'curves'
    assert curves['targets'] == [{'id': 'stats', 'label': 'Stats'}]
    game, mod = project(tmp_path / 'plain', make_archive())
    rows = data_map.payload(ItemStore(game, mod, False))['rows']
    missing = next(row for row in rows if row['id'] == 'curves-missing')
    assert missing['coverage'] == 'unavailable' and not missing['openable']


def test_service_row_sub_filters_stats_fields(tmp_path):
    game, mod = project(tmp_path)
    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                          'LEXEDITOR_MOD_READ_ONLY': '0', 'LEXEDITOR_NO_MOD': '0'})

    def request(path, payload=None):
        req = Request(session.url.rstrip('/') + path,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json'})
        with urlopen(req) as reply:
            return json.load(reply)

    try:
        session.start()
        assert 'stats' in request('/api/plugin')['capabilities']
        assert [(tab['id'], tab['count']) for tab in request('/api/state')['statsTabs']] == [
            ('curves', 3),
            ('weapon-upgrades', 3), ('armor-upgrades', 3), ('upgrade-materials', 3),
            ('starting-classes', 1), ('starting-gifts', 2), ('levelup', 0)]
        assert {row['id'] for row in request('/api/table?tab=curves')['rows']} == set(CURVE_ROWS)
        full = request('/api/row?table=EquipParamWeapon&id=100')['row']
        assert {'properStrength', 'properAgility', 'properMagic', 'properFaith',
                'correctStrength', 'correctAgility', 'correctMagic', 'correctFaith',
                'correctType', 'isLuckCorrect', 'levelSyncCorrectID'} <= {
                    field['key'] for field in full['fields']}
        curves = request(f'/api/row?table={GRAPH_TABLE}&id=100&sub=curves')['row']
        assert curves['name'] == 'Max HP (Vitality Stat)'
        upgrades = request('/api/table?tab=weapon-upgrades')['rows']
        assert {row['id'] for row in upgrades} == {100, 101, 102}
        upgrade = request('/api/row?table=ReinforceParamWeapon&id=100&sub=weapon-upgrades')['row']
        assert upgrade['name'] == 'Crystal +0'
        assert {field['key'] for field in upgrade['fields']} == set(STATS_FIELDS['ReinforceParamWeapon'])
        mats = request('/api/table?tab=upgrade-materials')['rows']
        assert {row['id'] for row in mats} == {1, 2, 3}
        picker = request('/api/row?table=EquipMtrlSetParam&id=1&sub=upgrade-materials')['row']
        assert {field['key'] for field in picker['fields']} == set(STATS_FIELDS['EquipMtrlSetParam'])
    finally:
        session.stop()
        assert session.wait_closed()


def test_upgrade_metadata_matches_vanilla_shape():
    assert TABLES['ReinforceParamWeapon'] == (88, 1)
    assert TABLES['ReinforceParamProtector'] == (48, 1)
    weapon = schema('ReinforceParamWeapon')
    assert weapon['type'] == 'REINFORCE_PARAM_WEAPON_ST' and weapon['size'] == 88
    assert {item['spec'].key for item in weapon['fields'] if item['editable']} == set(
        STATS_FIELDS['ReinforceParamWeapon'])
    assert weapon['names'][0] == 'Normal +0' and weapon['names'][15] == 'Normal +15'
    assert weapon['names'][100] == 'Crystal +0'
    rates = next(item for item in weapon['fields'] if item['spec'].key == 'physicsAtkRate')
    assert (rates['min'], rates['max']) == (0, 99.99)
    armor = schema('ReinforceParamProtector')
    assert armor['type'] == 'REINFORCE_PARAM_PROTECTOR_ST' and armor['size'] == 48
    assert {item['spec'].key for item in armor['fields'] if item['editable']} == set(
        STATS_FIELDS['ReinforceParamProtector'])
    assert armor['names'][0] == 'Armor - Normal +0' and armor['names'][100] == 'Armor - Unique +0'


def test_upgrade_edits_roundtrip_and_validate():
    document = ItemDocument(make_stats_archive())
    document.edit('ReinforceParamWeapon', 100, 'physicsAtkRate', 2.5)
    document.edit('ReinforceParamWeapon', 100, 'materialSetId', 7)
    document.edit('ReinforceParamProtector', 100, 'physicsDefRate', 1.5)
    assert document.value('ReinforceParamWeapon', 100, 'physicsAtkRate') == 2.5
    assert document.dirty_count == 3
    reopened = ItemDocument(document.export())
    assert reopened.value('ReinforceParamWeapon', 100, 'physicsAtkRate') == 2.5
    assert reopened.value('ReinforceParamWeapon', 100, 'materialSetId') == 7
    assert reopened.value('ReinforceParamProtector', 100, 'physicsDefRate') == 1.5
    for table, key, value in (('ReinforceParamWeapon', 'physicsAtkRate', -1),
                              ('ReinforceParamWeapon', 'physicsAtkRate', 100),
                              ('ReinforceParamWeapon', 'materialSetId', 256),
                              ('ReinforceParamWeapon', 'physicsAtkRate', float('nan')),
                              ('ReinforceParamProtector', 'physicsDefRate', -0.5)):
        try:
            document.edit(table, 100, key, value)
        except FormatError:
            continue
        raise AssertionError(f'{table} {key}={value} was accepted')


def test_data_map_points_upgrades_at_stats(tmp_path):
    game, mod = project(tmp_path)
    rows = data_map.payload(ItemStore(game, mod, False))['rows']
    weapon = next(row for row in rows if row['filename'] == 'ReinforceParamWeapon.param')
    assert weapon['coverage'] == 'structured' and weapon['status'] == 'integrated'
    assert weapon['openable'] and weapon['target'] == 'stats' and weapon['sub'] == 'weapon-upgrades'
    armor = next(row for row in rows if row['filename'] == 'ReinforceParamProtector.param')
    assert armor['openable'] and armor['target'] == 'stats' and armor['sub'] == 'armor-upgrades'
    mats = next(row for row in rows if row['filename'] == 'EquipMtrlSetParam.param')
    assert mats['openable'] and mats['target'] == 'stats' and mats['sub'] == 'upgrade-materials'


def test_material_metadata_matches_vanilla_shape():
    assert TABLES['EquipMtrlSetParam'] == (32, 1)
    definition = schema('EquipMtrlSetParam')
    assert definition['type'] == 'EQUIP_MTRL_SET_PARAM_ST' and definition['size'] == 32
    assert {item['spec'].key for item in definition['fields'] if item['editable']} == set(
        STATS_FIELDS['EquipMtrlSetParam'])
    assert definition['names'] == {}
    first = next(item for item in definition['fields'] if item['spec'].key == 'materialId01')
    assert first['spec'].reference == 'EquipParamGoods'
    assert (first['min'], first['max']) == (-1, 10000000)
    count = next(item for item in definition['fields'] if item['spec'].key == 'itemNum01')
    assert (count['min'], count['max']) == (-1, 99)
    assert next(item for item in definition['fields']
                if item['spec'].key == 'isDisableDispNum01')['spec'].is_bool


def test_material_edits_roundtrip_and_validate():
    document = ItemDocument(make_stats_archive())
    document.edit('EquipMtrlSetParam', 1, 'itemNum01', 5)
    document.edit('EquipMtrlSetParam', 3, 'materialId01', 102)
    document.edit('EquipMtrlSetParam', 3, 'itemNum01', 4)
    assert document.value('EquipMtrlSetParam', 1, 'itemNum01') == 5
    stone = document.display_name('EquipParamGoods', 102)
    assert next(row['name'] for row in document.list_rows('upgrade-materials')
                if row['id'] == 3) == f'{stone} x 4'
    assert document.dirty_count == 3
    reopened = ItemDocument(document.export())
    assert reopened.value('EquipMtrlSetParam', 1, 'itemNum01') == 5
    assert reopened.value('EquipMtrlSetParam', 3, 'materialId01') == 102
    for key, value in (('itemNum01', -2), ('itemNum01', 100), ('materialId01', 999),
                       ('materialId01', 1.5), ('itemNum01', float('nan'))):
        try:
            document.edit('EquipMtrlSetParam', 1, key, value)
        except FormatError:
            continue
        raise AssertionError(f'material {key}={value} was accepted')


def test_charainit_metadata_matches_vanilla_shape():
    assert TABLES['CharaInitParam'] == (240, 2)
    definition = schema('CharaInitParam')
    assert definition['type'] == 'CHARACTER_INIT_PARAM' and definition['size'] == 240
    assert definition['names'][3000] == 'Warrior' and definition['names'][2405] == 'Pendant'
    by_key = {item['spec'].key: item for item in definition['fields']}
    assert by_key['soulLv']['min'] == 0 and by_key['soulLv']['max'] == 9999
    assert by_key['baseVit']['min'] == 0 and by_key['baseVit']['max'] == 99
    assert by_key['itemNum_01']['max'] == 99
    assert by_key['baseDurability']['spec'].label == 'Resistance'
    assert by_key['baseLuc']['spec'].label == 'Unknown value 1'
    assert not by_key['baseLuc']['editable'] and not by_key['baseHeroPoint']['editable']
    assert by_key['vowType']['enum'] == {str(code): f'Covenant: {name}' for code, name in {
        0: 'None', 1: 'Way of White', 2: 'Princess Guard', 3: 'Warrior of Sunlight',
        4: 'Darkwraith', 5: 'Path of the Dragon', 6: 'Gravelord Servant',
        7: 'Forest Hunter', 8: 'Blade of the Dark Moon', 9: 'Chaos Servant'}.items()}
    assert by_key['npcPlayerSex']['enum'] == {'0': 'Female', '1': 'Male'}
    assert by_key['npcPlayerDrawType']['enum']['4'] == 'Ghoul Body'
    assert by_key['equip_Wep_Right']['spec'].reference == 'EquipParamWeapon'
    assert by_key['equip_Helm']['spec'].reference == 'EquipParamProtector'
    assert by_key['equip_Accessory01']['spec'].reference == 'EquipParamAccessory'
    assert by_key['equip_Spell_01']['spec'].reference == 'Magic'
    assert by_key['item_01']['spec'].reference == 'EquipParamGoods'


def test_class_lists_show_kits_and_gifts():
    document = ItemDocument(make_stats_archive())
    classes = document.list_rows('starting-classes')
    assert {row['id'] for row in classes} == {3000}
    assert all(row['table'] == 'CharaInitParam' for row in classes)
    assert next(row['name'] for row in classes if row['id'] == 3000) == 'Warrior'
    assert 2000 not in {row['id'] for row in classes}
    gifts = document.list_rows('starting-gifts')
    assert {row['id'] for row in gifts} == {2405, 2407}
    assert next(row['name'] for row in gifts if row['id'] == 2405) == 'Pendant'
    assert next(row['name'] for row in gifts if row['id'] == 2407) == "Tiny Being's Ring"
    row = document.read_row('CharaInitParam', 3000)
    groups = {field['key']: field['group'] for field in row['fields']}
    assert groups['baseVit'] == 'Basics' and groups['soulLv'] == 'Basics'
    assert groups['equip_Wep_Right'] == 'Starting gear' and groups['equip_Helm'] == 'Starting gear'
    assert groups['equip_Spell_01'] == 'Starting spells'
    assert groups['item_01'] == 'Starting items' and groups['itemNum_01'] == 'Starting items'
    assert groups['gestureId0'] == 'Body & gestures'
    assert all(field['editable'] for field in row['fields']
               if field['key'] not in ('baseLuc', 'baseHeroPoint'))


def test_class_edits_mirror_the_twin():
    document = ItemDocument(make_stats_archive())
    document.edit('CharaInitParam', 3000, 'baseVit', 12)
    assert document.value('CharaInitParam', 3000, 'baseVit') == 12
    assert document.value('CharaInitParam', 2000, 'baseVit') == 12
    document.edit('CharaInitParam', 3000, 'npcPlayerDrawType', 1)
    assert document.value('CharaInitParam', 3000, 'npcPlayerDrawType') == 1
    assert document.value('CharaInitParam', 2000, 'npcPlayerDrawType') == 4
    assert document.pending_changes() == [
        {'label': 'Warrior \u00b7 Draw type', 'before': 0, 'after': 1},
        {'label': 'Warrior \u00b7 Vitality', 'before': 11, 'after': 12}]
    reopened = ItemDocument(document.export())
    assert reopened.value('CharaInitParam', 2000, 'baseVit') == 12
    assert reopened.value('CharaInitParam', 2000, 'npcPlayerDrawType') == 4


def test_gifts_show_only_what_they_grant(tmp_path):
    game, mod = project(tmp_path)
    (game / texts.MENU_RELATIVE).parent.mkdir(parents=True)
    (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive(extra={
        texts.CLASS_DESCRIPTION_FILE: {132355: 'Divine holy water test.'}}))
    document = ItemStore(game, mod, False).get()
    row = document.read_row('CharaInitParam', 2405,
                            only=stats_fields('starting-gifts', 'CharaInitParam'))
    assert {field['key'] for field in row['fields']} == set(GIFT_FIELDS)
    assert all(field['editable'] for field in row['fields'])
    values, display = document.row_values('CharaInitParam', 2405)
    assert (values['item_01'], display['item_01'], values['itemNum_01']) == (
        100, document.display_name('EquipParamGoods', 100), 1)
    assert display['item_02'] == 'None' and display['equip_Accessory02'] == 'None'
    values, display = document.row_values('CharaInitParam', 2407)
    assert (values['equip_Accessory01'], display['equip_Accessory01']) == (
        100, document.display_name('EquipParamAccessory', 100))


def test_gear_pickers_offer_live_names():
    document = ItemDocument(make_stats_archive())
    row = document.read_row('CharaInitParam', 3000)
    by_key = {field['key']: field for field in row['fields']}
    assert by_key['equip_Wep_Right']['type'] == 'enum'
    assert set(by_key['equip_Wep_Right']['enum']) >= {'-1', '0', '100', '101', '102'}
    assert by_key['equip_Wep_Right']['enum']['100'] == document.display_name('EquipParamWeapon', 100)
    assert set(by_key['equip_Helm']['enum']) >= {'-1', '0', '100', '101', '102'}
    assert set(by_key['equip_Spell_01']['enum']) >= {'-1', '0', '100', '101', '102'}
    document.edit('CharaInitParam', 3000, 'equip_Wep_Right', 101)
    assert document.value('CharaInitParam', 3000, 'equip_Wep_Right') == 101
    document.edit('CharaInitParam', 3000, 'equip_Wep_Right', -1)
    for key, noun in (('equip_Wep_Right', 'weapon'), ('equip_Helm', 'armor piece'),
                      ('equip_Accessory01', 'accessory'), ('equip_Spell_01', 'spell')):
        try:
            document.edit('CharaInitParam', 3000, key, 999)
        except FormatError as error:
            assert str(error) == f'Choose an existing {noun} or None'
            continue
        raise AssertionError(f'class {key}=999 was accepted')


def test_classes_need_the_table():
    document = ItemDocument(make_archive())
    assert 'CharaInitParam' not in document.params
    try:
        document.list_rows('starting-classes')
    except FormatError as error:
        assert 'CharaInitParam.param is missing' in str(error)
    else:
        raise AssertionError('starting classes listed without their table')
    try:
        document.list_rows('starting-gifts')
    except FormatError:
        pass
    else:
        raise AssertionError('starting gifts listed without their table')


def test_data_map_points_classes_at_stats(tmp_path):
    game, mod = project(tmp_path)
    rows = data_map.payload(ItemStore(game, mod, False))['rows']
    chara = next(row for row in rows if row['filename'] == 'CharaInitParam.param')
    assert chara['coverage'] == 'structured' and chara['status'] == 'partial'
    assert chara['openable'] and chara['target'] == 'stats' and chara['sub'] == 'starting-classes'
