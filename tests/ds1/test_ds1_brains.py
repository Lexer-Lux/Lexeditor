"""AI tab think records/behaviors and Attacks tab projectiles: curated brains."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive
from plugins.ds1 import data_map, mod_loader
from plugins.ds1.formats import (
    AI_SUBTABS, ATTACK_SUBTABS, BEHAVIOR_EDITABLE, BULLET_EDITABLE, ENEMY_SUBTABS,
    TABLES, THINK_EDITABLE, FormatError, ItemDocument, field_link, schema,
)
from plugins.ds1.store import MARKER, RELATIVE, ItemStore


def project(tmp_path, raw=None):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive() if raw is None else raw)
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def test_brains_metadata_matches_vanilla_shape():
    assert TABLES['BehaviorParam'] == (32, 2)
    assert TABLES['Bullet'] == (160, 2)
    assert TABLES['NpcThinkParam'] == (112, 1)
    behaviors = schema('BehaviorParam')
    assert behaviors['type'] == 'BEHAVIOR_PARAM_ST' and behaviors['size'] == 32
    assert len(behaviors['names']) == 2400
    bullets = schema('Bullet')
    assert bullets['type'] == 'BULLET_PARAM_ST' and bullets['size'] == 160
    assert len(bullets['names']) == 631
    think = schema('NpcThinkParam')
    assert think['type'] == 'NPC_THINK_PARAM_ST' and think['size'] == 112
    assert len(think['names']) == 476
    ref = next(item for item in behaviors['fields'] if item['spec'].key == 'refType')
    assert ref['enum'] == {'0': 'Attack', '1': 'Bullet', '2': 'SpEffect'}
    goal = next(item for item in think['fields'] if item['spec'].key == 'goalAction_ToCaution')
    assert goal['enum'] == {'0': 'Do nothing', '1': 'Face towards Target',
                            '2': 'Walk to Target', '3': 'Run to Target',
                            '4': 'Set any Goal', '5': 'Away from Target',
                            '6': 'Wander Around',
                            '7': 'Hold up Shield -> Walk to Target',
                            '8': 'Route movement', '9': 'Walk around nearby'}


def test_brains_subtabs_list_their_rows():
    assert [entry[0] for entry in ENEMY_SUBTABS] == ['monsters', 'bosses']
    assert [(entry[0], entry[1], entry[2]) for entry in AI_SUBTABS] == [
        ('ai', 'AI tables', 'NpcThinkParam'), ('behaviors', 'Behaviors', 'BehaviorParam')]
    assert [entry[0] for entry in ATTACK_SUBTABS] == ['attacks', 'player-attacks', 'projectiles']
    document = ItemDocument(make_archive())
    behaviors = document.list_rows('behaviors')
    assert {row['id'] for row in behaviors} == {100, 101, 102}
    assert all(row['table'] == 'BehaviorParam' for row in behaviors)
    assert next(row['name'] for row in behaviors if row['id'] == 100) == 'Behavior 100'
    think = document.list_rows('ai')
    assert {row['id'] for row in think} == {100, 101, 102}
    assert all(row['table'] == 'NpcThinkParam' and row['name'] for row in think)
    bullets = document.list_rows('projectiles')
    assert {row['id'] for row in bullets} == {100, 101, 102}
    assert all(row['table'] == 'Bullet' and row['name'] for row in bullets)


def test_brains_detail_shows_reviewed_fields():
    document = ItemDocument(make_archive())
    fields = document.read_row('BehaviorParam', 100)['fields']
    assert {field['key'] for field in fields} == set(BEHAVIOR_EDITABLE)
    assert all(field['editable'] for field in fields)
    assert next(field for field in fields if field['key'] == 'refType')['type'] == 'enum'
    fields = document.read_row('Bullet', 100)['fields']
    assert {field['key'] for field in fields} == set(BULLET_EDITABLE)
    assert all(field['editable'] for field in fields)
    assert next(field for field in fields if field['key'] == 'launchConditionType')['type'] == 'enum'
    fields = document.read_row('NpcThinkParam', 100)['fields']
    assert {field['key'] for field in fields} == set(THINK_EDITABLE)
    assert all(field['editable'] for field in fields)
    assert next(field for field in fields if field['key'] == 'goalAction_ToCaution')['type'] == 'enum'


def test_brains_edits_roundtrip_and_validate():
    original = make_archive()
    document = ItemDocument(original)
    edits = [('BehaviorParam', 100, 'stamina', 12),
             ('BehaviorParam', 100, 'refType', 2),
             ('BehaviorParam', 100, 'refId', 105),
             ('Bullet', 100, 'life', 5.0),
             ('Bullet', 100, 'atkId_Bullet', 101),
             ('Bullet', 100, 'launchConditionType', 1),
             ('NpcThinkParam', 100, 'backhomeDist', 30.0),
             ('NpcThinkParam', 100, 'goalAction_ToCaution', 3),
             ('NpcThinkParam', 100, 'disablePathMove', 1)]
    saved = {(table, row, key): document.value(table, row, key) for table, row, key, _ in edits}
    for table, row, key, value in edits:
        document.edit(table, row, key, value)
    assert document.dirty_count == len(edits)
    reopened = ItemDocument(document.export())
    for table, row, key, value in edits:
        assert reopened.value(table, row, key) == value
    for table, key, value in (('BehaviorParam', 'refType', 3),
                              ('BehaviorParam', 'stamina', 1.5),
                              ('Bullet', 'launchConditionType', 7),
                              ('Bullet', 'life', float('nan')),
                              ('NpcThinkParam', 'goalAction_ToCaution', 10),
                              ('NpcThinkParam', 'backhomeDist', float('inf'))):
        with pytest.raises(FormatError):
            document.edit(table, 100, key, value)
    for table, key in (('BehaviorParam', 'variationId'),
                       ('BehaviorParam', 'behaviorJudgeId'),
                       ('Bullet', 'sfxId_Hit'),
                       ('NpcThinkParam', 'logicId'),
                       ('NpcThinkParam', 'battleGoalID')):
        with pytest.raises(FormatError, match='protected'):
            document.edit(table, 100, key, 1)
    for (table, row, key), value in saved.items():
        document.edit(table, row, key, value)
    assert document.dirty_count == 0 and document.export() == original


def test_brains_rows_merge_by_field_and_conflict_by_name():
    vanilla = make_archive()
    game = {RELATIVE: vanilla}

    def edited(*edits):
        document = ItemDocument(vanilla)
        for table, row, key, value in edits:
            document.edit(table, row, key, value)
        return document.export()

    def mod(name, params):
        return mod_loader.Mod(name, Path(name), {RELATIVE: params})

    label = next(item['spec'].label for item in schema('BehaviorParam')['fields']
                 if item['spec'].key == 'stamina')
    a = mod('A', edited(('BehaviorParam', 100, 'stamina', 12)))
    b = mod('B', edited(('BehaviorParam', 100, 'refId', 101)))
    result = mod_loader.compose(game, [a, b])
    assert result.conflicts == []
    merged = ItemDocument(result.files[RELATIVE])
    assert merged.value('BehaviorParam', 100, 'stamina') == 12
    assert merged.value('BehaviorParam', 100, 'refId') == 101
    c = mod('C', edited(('BehaviorParam', 100, 'stamina', 14)))
    result = mod_loader.compose(game, [a, c])
    assert [(c.part, c.mods) for c in result.conflicts] == [(f'Behaviors 100, {label}', ['A', 'C'])]
    assert ItemDocument(result.files[RELATIVE]).value('BehaviorParam', 100, 'stamina') == 14


def test_state_reports_brains_tabs(tmp_path):
    game, mod = project(tmp_path)
    state = ItemStore(game, mod, False).state()
    assert [tab['id'] for tab in state['enemyTabs']] == ['monsters', 'bosses']
    ai = {tab['id']: tab for tab in state['aiTabs']}
    assert [(ai[key]['table'], ai[key]['count']) for key in ('ai', 'behaviors')] == [
        ('NpcThinkParam', 3), ('BehaviorParam', 3)]
    attacks = {tab['id']: tab for tab in state['attackTabs']}
    assert (attacks['projectiles']['table'], attacks['projectiles']['count']) == ('Bullet', 3)


def test_data_map_points_brains_at_ai_and_attacks(tmp_path):
    game, mod = project(tmp_path)
    rows = data_map.payload(ItemStore(game, mod, False))['rows']
    for filename, target, sub in (('BehaviorParam.param', 'ai', 'behaviors'),
                                  ('NpcThinkParam.param', 'ai', 'ai'),
                                  ('Bullet.param', 'attacks', 'projectiles')):
        row = next(entry for entry in rows if entry['filename'] == filename)
        assert row['coverage'] == 'structured' and row['status'] == 'partial'
        assert row['openable'] and row['target'] == target and row['sub'] == sub


def test_ai_think_id_links_to_its_think_record():
    document = ItemDocument(make_archive())
    schemas = {item['spec'].key: item['spec'] for item in schema('NpcParam')['fields']}
    assert field_link(document, 'NpcParam', 120000, schemas['aiThinkId']) == ('ai', 'NpcThinkParam')
    field = next(item for item in document.read_row('NpcParam', 120000)['fields']
                 if item['key'] == 'aiThinkId')
    assert field['type'] == 'enum' and field['enum']['101'] == document.display_name('NpcThinkParam', 101)
    document.edit('NpcParam', 120000, 'aiThinkId', 101)
    assert document.value('NpcParam', 120000, 'aiThinkId') == 101
    with pytest.raises(FormatError, match='existing AI table'):
        document.edit('NpcParam', 120000, 'aiThinkId', 999)


def test_moves_resolve_each_behavior_call_target():
    document = ItemDocument(make_archive())
    moves = document.attack_references().moves(12000)
    assert [move['id'] for move in moves] == [100, 101]
    direct, projectile = (move['target'] for move in moves)
    assert (direct['kind'], direct['table'], direct['id'], direct['projectile']) == (
        'attack', 'AtkParam_Npc', 100, False)
    assert (projectile['kind'], projectile['table'], projectile['projectile']) == (
        'attack', 'AtkParam_Npc', True)
    assert document.attack_references().moves(99999) == []


def test_variation_write_validates_and_refreshes():
    document = ItemDocument(make_archive())
    assert document.value('NpcParam', 120000, 'behaviorVariationId') == 12000
    document.edit('NpcParam', 120000, 'behaviorVariationId', 12010)
    assert document.value('NpcParam', 120000, 'behaviorVariationId') == 12010
    assert sorted(document.attack_references().variants[12010]) == [120000, 120100]
    assert document.dirty_count == 1
    with pytest.raises(FormatError, match='No behavior set 99999 exists'):
        document.edit('NpcParam', 120000, 'behaviorVariationId', 99999)
    with pytest.raises(FormatError, match='whole number'):
        document.edit('NpcParam', 120000, 'behaviorVariationId', 12010.5)
    document.edit('NpcParam', 120000, 'behaviorVariationId', 12000)
    assert document.dirty_count == 0
