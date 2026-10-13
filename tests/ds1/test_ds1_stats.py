"""Stats tab: scaling curves, weapon scaling and spell requirements."""
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from ds1_stats_fixture import make_stats_archive, CURVE_ROWS
from plugins.ds1 import data_map
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
    assert [entry[0] for entry in STATS_SUBTABS] == ['curves', 'scaling', 'spell-reqs',
                                                      'weapon-upgrades', 'armor-upgrades']
    curves = document.list_rows('curves')
    assert {row['id'] for row in curves} == set(CURVE_ROWS)
    assert all(row['table'] == GRAPH_TABLE for row in curves)
    assert all(row['values'] and row['display'] is not None for row in curves)
    assert next(row['name'] for row in curves if row['id'] == 100) == 'Max HP (Vitality Stat)'
    # Weapon scaling covers every weapon record, including ammunition.
    scaling = document.list_rows('scaling')
    assert {row['id'] for row in scaling} == {100, 101, 102}
    assert all(row['table'] == 'EquipParamWeapon' for row in scaling)
    # Spell requirements are the Magic records, without the inventory items.
    spells = document.list_rows('spell-reqs')
    assert {row['id'] for row in spells} == {100, 101, 102}
    assert all(row['table'] == 'Magic' for row in spells)
    upgrades = document.list_rows('weapon-upgrades')
    assert {row['id'] for row in upgrades} == {100, 101, 102}
    assert all(row['table'] == 'ReinforceParamWeapon' for row in upgrades)
    assert next(row['name'] for row in upgrades if row['id'] == 100) == 'Crystal +0'
    armors = document.list_rows('armor-upgrades')
    assert {row['id'] for row in armors} == {100, 101, 102}
    assert all(row['table'] == 'ReinforceParamProtector' for row in armors)
    assert next(row['name'] for row in armors if row['id'] == 100) == 'Armor - Unique +0'


def test_stats_detail_shows_only_stat_fields():
    document = ItemDocument(make_stats_archive())
    assert stats_fields('scaling', 'EquipParamWeapon') == STATS_FIELDS['EquipParamWeapon']
    assert stats_fields('scaling', 'Magic') is None
    assert stats_fields('weapons', 'EquipParamWeapon') is None
    assert stats_fields('curves', GRAPH_TABLE) is None
    assert stats_fields('weapon-upgrades', 'ReinforceParamWeapon') is None
    assert stats_fields('armor-upgrades', 'ReinforceParamProtector') is None
    row = document.read_row('EquipParamWeapon', 100, only=STATS_FIELDS['EquipParamWeapon'])
    assert [field['key'] for field in row['fields']] == [
        field['key'] for field in document.read_row('EquipParamWeapon', 100)['fields']
        if field['key'] in STATS_FIELDS['EquipParamWeapon']]
    assert {field['key'] for field in row['fields']} == set(STATS_FIELDS['EquipParamWeapon'])
    graph = next(field for field in row['fields'] if field['key'] == 'correctType')
    assert not graph['editable']
    row = document.read_row('Magic', 100, only=STATS_FIELDS['Magic'])
    assert {field['key'] for field in row['fields']} == {
        'requirementIntellect', 'requirementFaith', 'slotLength', 'stamina'}
    assert all(field['editable'] for field in row['fields'])
    stamina = next(field for field in row['fields'] if field['key'] == 'stamina')
    assert stamina['label'] == 'Stamina Consumption'
    assert stamina['minimum'] == 0 and stamina['maximum'] == 9999
    assert 'Spell Stamina Costs' in stamina['description']
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
    assert len(document.list_rows('scaling')) == 3
    assert len(document.list_rows('spell-reqs')) == 3
    assert len(document.list_rows('weapon-upgrades')) == 3
    assert len(document.list_rows('armor-upgrades')) == 3


def test_state_reports_stats_tabs(tmp_path):
    game, mod = project(tmp_path)
    tabs = ItemStore(game, mod, False).state()['statsTabs']
    assert [(tab['id'], tab['count']) for tab in tabs] == [
        ('curves', 3), ('scaling', 3), ('spell-reqs', 3),
        ('weapon-upgrades', 3), ('armor-upgrades', 3)]
    game, mod = project(tmp_path / 'plain', make_archive())
    tabs = ItemStore(game, mod, False).state()['statsTabs']
    assert [(tab['id'], tab['count']) for tab in tabs] == [
        ('curves', 0), ('scaling', 3), ('spell-reqs', 3),
        ('weapon-upgrades', 3), ('armor-upgrades', 3)]


def test_data_map_points_curves_at_stats(tmp_path):
    game, mod = project(tmp_path)
    rows = data_map.payload(ItemStore(game, mod, False))['rows']
    curves = next(row for row in rows if row['filename'] == 'CalcCorrectGraph.param')
    assert curves['coverage'] == 'structured' and curves['status'] == 'partial'
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
            ('curves', 3), ('scaling', 3), ('spell-reqs', 3),
            ('weapon-upgrades', 3), ('armor-upgrades', 3)]
        assert {row['id'] for row in request('/api/table?tab=curves')['rows']} == set(CURVE_ROWS)
        filtered = request('/api/row?table=EquipParamWeapon&id=100&sub=scaling')['row']
        assert {field['key'] for field in filtered['fields']} == set(STATS_FIELDS['EquipParamWeapon'])
        full = request('/api/row?table=EquipParamWeapon&id=100')['row']
        assert len(full['fields']) > len(filtered['fields'])
        curves = request(f'/api/row?table={GRAPH_TABLE}&id=100&sub=curves')['row']
        assert curves['name'] == 'Max HP (Vitality Stat)'
        upgrades = request('/api/table?tab=weapon-upgrades')['rows']
        assert {row['id'] for row in upgrades} == {100, 101, 102}
        upgrade = request('/api/row?table=ReinforceParamWeapon&id=100&sub=weapon-upgrades')['row']
        assert upgrade['name'] == 'Crystal +0'
        assert {field['key'] for field in upgrade['fields']} == set(STATS_FIELDS['ReinforceParamWeapon'])
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
    assert weapon['coverage'] == 'structured' and weapon['status'] == 'partial'
    assert weapon['openable'] and weapon['target'] == 'stats' and weapon['sub'] == 'weapon-upgrades'
    armor = next(row for row in rows if row['filename'] == 'ReinforceParamProtector.param')
    assert armor['openable'] and armor['target'] == 'stats' and armor['sub'] == 'armor-upgrades'
