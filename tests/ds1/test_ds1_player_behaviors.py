"""The AI tab's Player behaviors subtab and player-behavior references."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive
from plugins.ds1.formats import (
    AI_SUBTABS, BEHAVIOR_EDITABLE, FormatError, ItemDocument, TABLES)


def test_player_behaviors_table_lists_and_reads():
    doc = ItemDocument(make_archive())
    assert TABLES['BehaviorParam_PC'] == (32, 2)
    assert ('player-behaviors', 'Player behaviors', 'BehaviorParam_PC') in AI_SUBTABS
    rows = doc.list_rows('player-behaviors')
    assert [(row['table'], row['id']) for row in rows] == [
        ('BehaviorParam_PC', 100), ('BehaviorParam_PC', 101), ('BehaviorParam_PC', 102)]
    assert [row['name'] for row in rows] == ['Behavior 100', 'Behavior 101', 'Behavior 102']
    fields = doc.read_row('BehaviorParam_PC', 100)['fields']
    assert {field['key'] for field in fields} == set(BEHAVIOR_EDITABLE)
    assert all(field['editable'] for field in fields)


def test_player_behavior_costs_edit_and_identity_stays_protected():
    doc = ItemDocument(make_archive())
    fields = doc.edit('BehaviorParam_PC', 100, 'stamina', 25)['fields']
    assert next(field['value'] for field in fields if field['key'] == 'stamina') == 25
    assert doc.value('BehaviorParam_PC', 100, 'stamina') == 25
    with pytest.raises(FormatError):
        doc.edit('BehaviorParam_PC', 100, 'variationId', 1)


def test_behavior_id_references_resolve_to_player_behaviors():
    raw = make_archive(field_values={
        'EquipParamAccessory': {100: {'behaviorId': 101}},
        'EquipParamGoods': {100: {'behaviorId': 102}},
        'Magic': {100: {'behaviorId': 100}}})
    doc = ItemDocument(raw)
    for table, target in (('EquipParamAccessory', 101), ('EquipParamGoods', 102), ('Magic', 100)):
        links = doc.read_row(table, 100)['recordLinks']
        entry = next(item for item in links if item['field'] == 'behaviorId')
        assert (entry['kind'], entry['table'], entry['id']) == ('behavior', 'BehaviorParam_PC', target)
        assert entry['resolved'] and entry['name'] == f'Behavior {target}'


def test_behavior_attack_calls_link_their_own_side():
    raw = make_archive(field_values={'BehaviorParam_PC': {100: {'refType': 0, 'refId': 101}}})
    doc = ItemDocument(raw)
    entry = next(item for item in doc.read_row('BehaviorParam_PC', 100)['recordLinks']
                 if item['field'] == 'refId')
    assert (entry['kind'], entry['table'], entry['id']) == ('attack', 'AtkParam_Pc', 101)
    assert entry['resolved']
    entry = next(item for item in doc.read_row('BehaviorParam', 100)['recordLinks']
                 if item['field'] == 'refId')
    assert (entry['kind'], entry['table']) == ('attack', 'AtkParam_Npc')
