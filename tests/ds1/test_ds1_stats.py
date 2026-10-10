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
    assert [entry[0] for entry in STATS_SUBTABS] == ['curves', 'scaling', 'spell-reqs']
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


def test_stats_detail_shows_only_stat_fields():
    document = ItemDocument(make_stats_archive())
    assert stats_fields('scaling', 'EquipParamWeapon') == STATS_FIELDS['EquipParamWeapon']
    assert stats_fields('scaling', 'Magic') is None
    assert stats_fields('weapons', 'EquipParamWeapon') is None
    assert stats_fields('curves', GRAPH_TABLE) is None
    row = document.read_row('EquipParamWeapon', 100, only=STATS_FIELDS['EquipParamWeapon'])
    assert [field['key'] for field in row['fields']] == [
        field['key'] for field in document.read_row('EquipParamWeapon', 100)['fields']
        if field['key'] in STATS_FIELDS['EquipParamWeapon']]
    assert {field['key'] for field in row['fields']} == set(STATS_FIELDS['EquipParamWeapon'])
    graph = next(field for field in row['fields'] if field['key'] == 'correctType')
    assert not graph['editable']
    row = document.read_row('Magic', 100, only=STATS_FIELDS['Magic'])
    assert {field['key'] for field in row['fields']} == {
        'requirementIntellect', 'requirementFaith', 'slotLength'}
    assert all(field['editable'] for field in row['fields'])
    curves = document.read_row(GRAPH_TABLE, 200)
    assert {field['key'] for field in curves['fields']} == set(STATS_FIELDS[GRAPH_TABLE])
    groups = {field['key']: field['group'] for field in curves['fields']}
    assert groups['stageMaxVal0'] == 'Thresholds' and groups['stageMaxGrowVal4'] == 'Growth'
    assert groups['adjPt_maxGrowVal0'] == 'Curve shape' and groups['boundry_value'] == 'Level-up cost'


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


def test_state_reports_stats_tabs(tmp_path):
    game, mod = project(tmp_path)
    tabs = ItemStore(game, mod, False).state()['statsTabs']
    assert [(tab['id'], tab['count']) for tab in tabs] == [
        ('curves', 3), ('scaling', 3), ('spell-reqs', 3)]
    game, mod = project(tmp_path / 'plain', make_archive())
    tabs = ItemStore(game, mod, False).state()['statsTabs']
    assert [(tab['id'], tab['count']) for tab in tabs] == [
        ('curves', 0), ('scaling', 3), ('spell-reqs', 3)]


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
            ('curves', 3), ('scaling', 3), ('spell-reqs', 3)]
        assert {row['id'] for row in request('/api/table?tab=curves')['rows']} == set(CURVE_ROWS)
        filtered = request('/api/row?table=EquipParamWeapon&id=100&sub=scaling')['row']
        assert {field['key'] for field in filtered['fields']} == set(STATS_FIELDS['EquipParamWeapon'])
        full = request('/api/row?table=EquipParamWeapon&id=100')['row']
        assert len(full['fields']) > len(filtered['fields'])
        curves = request(f'/api/row?table={GRAPH_TABLE}&id=100&sub=curves')['row']
        assert curves['name'] == 'Max HP (Vitality Stat)'
    finally:
        session.stop()
        assert session.wait_closed()
