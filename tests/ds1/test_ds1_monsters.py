"""Reviewed-stat edits, classification, validation, and byte preservation."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive
from ds1_effects_fixture import make_effects_archive
from plugins.ds1.formats import ItemDocument, FormatError, inflate, SIZES
from plugins.ds1.monsters import NPC_FIELDS
from plugins.ds1.store import ItemStore, RELATIVE, MARKER
from plugins.ds3.formats import write_field


def test_only_reviewed_monsters_and_only_stat_fields_are_accessible():
    doc = ItemDocument(make_archive())
    assert [row['id'] for row in doc.list_rows('monsters')] == [120000, 120100]
    assert {field['key'] for field in doc.read_row('NpcParam', 120000)['fields']} == set(NPC_FIELDS) | {'effectiveHp'}
    fields = doc.read_row('NpcParam', 120000)['fields']
    assert all(field['editable'] for field in fields if field['key'] != 'effectiveHp')
    effective = next(field for field in fields if field['key'] == 'effectiveHp')
    assert not effective['editable'] and effective['value'] == 0
    # Stray Demon deliberately has type 0, and Egg Carrier shares a monster
    # family name but has type 2. Neither name-only nor type-only filtering works.
    # 251000 and 321001 are friendly (type 2): the NPCs tab reviews them.
    for excluded in (223000, 502, 999999):
        with pytest.raises(FormatError, match='not a reviewed'):
            doc.read_row('NpcParam', excluded)
        with pytest.raises(FormatError, match='not a reviewed'):
            doc.edit('NpcParam', excluded, 'def_phys', 10)
    others = [f['spec'].key for f in doc.schemas['NpcParam']['fields']
              if f['spec'].key not in NPC_FIELDS]
    assert others and 'npcType' in others and 'behaviorVariationId' in others
    for key in others:
        with pytest.raises(FormatError, match='protected'):
            doc.edit('NpcParam', 120000, key, 1)


def test_all_stats_roundtrip_only_their_cells_and_revert_exactly():
    original = make_archive()
    doc = ItemDocument(original)
    assert doc.export() == original
    allowed, written = set(), {}
    for key in NPC_FIELDS:
        item = next(f for f in doc.schemas['NpcParam']['fields'] if f['spec'].key == key)
        spec = item['spec']
        start = doc._row('NpcParam', 120000)[1] + spec.offset
        allowed.update(range(start, start + SIZES[spec.dtype]))
        value = 1 if spec.is_bool else int(sorted(item['enum'], key=int)[-1]) if item['enum'] else 25.5 if spec.dtype == 'f32' else 25
        doc.edit('NpcParam', 120000, key, value)
        written[key] = value
    reopened = ItemDocument(doc.export())
    for key, value in written.items():
        assert reopened.value('NpcParam', 120000, key) == value
    changed = {index for index, (a, b) in enumerate(zip(inflate(original), inflate(doc.export()))) if a != b}
    assert changed and changed <= allowed
    for key in NPC_FIELDS:
        doc.edit('NpcParam', 120000, key, 0)
    assert doc.dirty_count == 0 and doc.export() == original


@pytest.mark.parametrize('field,value', [('def_phys', -1), ('def_phys', 10000), ('def_phys', 1.5),
    ('def_slash', -101), ('resist_poison', 1000), ('physGuardCutRate', 101),
    ('physGuardCutRate', float('nan')), ('def_mag', '10'),
    ('hp', -1), ('teamType', 27), ('dropType', 2), ('stamina', 1.5)])
def test_stat_bounds_and_types_are_enforced(field, value):
    doc = ItemDocument(make_archive())
    with pytest.raises(FormatError): doc.edit('NpcParam', 120000, field, value)
    assert doc.export() == doc.original


def test_classification_rechecks_live_type_and_preserves_other_fields(tmp_path):
    doc = ItemDocument(make_archive())
    row, start, data = doc._row('NpcParam', 120000)
    spec = next(f['spec'] for f in doc.schemas['NpcParam']['fields'] if f['spec'].key == 'npcType')
    changed = write_field(data, spec, 1, '<')
    doc.plain[start:start + len(data)] = changed
    reopened = ItemDocument(doc.export())
    assert [r['id'] for r in reopened.list_rows('monsters')] == [120100]


def test_project_save_reload_and_readonly_monsters(tmp_path):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    original = make_archive()
    (game / RELATIVE).write_bytes(original)
    mod.mkdir(); (mod / MARKER).touch()
    store = ItemStore(game, mod, False)
    store.edit('NpcParam', 120000, 'def_phys', 123)
    store.edit('NpcParam', 120000, 'def_slash', -25)
    store.edit('NpcParam', 120000, 'resist_poison', 250)
    store.edit('NpcParam', 120000, 'physGuardCutRate', 42.5)
    store.save()
    fresh = ItemStore(game, mod, False)
    assert fresh.get().value('NpcParam', 120000, 'def_phys') == 123
    assert fresh.get().value('NpcParam', 120000, 'def_slash') == -25
    assert fresh.get().value('NpcParam', 120000, 'resist_poison') == 250
    assert fresh.get().value('NpcParam', 120000, 'physGuardCutRate') == 42.5
    assert fresh.state()['enemyTabs'][0]['id'] == 'monsters'
    assert (game / RELATIVE).read_bytes() == original
    with pytest.raises(PermissionError): ItemStore(game).edit('NpcParam', 120000, 'def_phys', 1)


def test_table_values_match_detail_values_for_every_monster_property():
    """Pinned columns and the detail pane read the same values, always."""
    base = 40_000_000 + 120000
    doc = ItemDocument(make_effects_archive(extra_ids=(base,)))
    doc.edit('SpEffectParam', base, 'neutralDamageCutRate', 0.6)
    doc.edit('SpEffectParam', base, 'maxHpRate', 1.4)
    doc.edit('NpcParam', 120000, 'hp', 480)
    # Armor Rework links live past the slot's UI bounds, like retail data.
    _row, start, data = doc._row('NpcParam', 120000)
    spec = next(f['spec'] for f in doc.schemas['NpcParam']['fields'] if f['spec'].key == 'spEffectID0')
    doc.plain[start:start + len(data)] = write_field(data, spec, base, '<')
    for row_id in (120000, 120100):
        values, _display = doc.row_values('NpcParam', row_id)
        fields = {field['key']: field['value']
                  for field in doc.read_row('NpcParam', row_id)['fields']}
        assert set(fields) <= set(values)
        for key, value in fields.items():
            assert values[key] == value, (row_id, key)
    assert doc.row_values('NpcParam', 120000)[0]['absorption:neutralDamageCutRate'] == 40.0
    assert doc.row_values('NpcParam', 120000)[0]['effectiveHp'] == 672


def test_effective_hp_multiplies_resident_rates_and_skips_the_rest():
    doc = ItemDocument(make_effects_archive(extra_ids=(7001, 7002)))
    doc.edit('SpEffectParam', 7001, 'maxHpRate', 1.4)
    doc.edit('SpEffectParam', 7002, 'maxHpRate', 1.15)
    doc.edit('NpcParam', 120000, 'hp', 480)
    assert doc.read_row('NpcParam', 120000)['fields']
    assert doc._effective_hp(120000) == 480
    doc.edit('NpcParam', 120000, 'spEffectID0', 7001)
    assert doc._effective_hp(120000) == 672
    doc.edit('NpcParam', 120000, 'spEffectID1', 7002)
    assert doc._effective_hp(120000) == 773
    # A link to a removed effect, and an empty slot, scale nothing.
    row, start, data = doc._row('NpcParam', 120000)
    spec = next(f['spec'] for f in doc.schemas['NpcParam']['fields'] if f['spec'].key == 'spEffectID2')
    changed = write_field(data, spec, 99999999, '<')
    doc.plain[start:start + len(data)] = changed
    assert doc._effective_hp(120000) == 773
    with pytest.raises(FormatError, match='protected'):
        doc.edit('NpcParam', 120000, 'effectiveHp', 10)



def test_defense_fields_carry_game_art_where_it_exists():
    # Damage and defense labels show the equipment screen's own icons; kinds
    # the game shows no icon for (subtypes, resistances, weaknesses) ship
    # with none: game art only, no invented glyphs.
    fields = {field['key']: field.get('icon')
              for field in ItemDocument(make_archive()).read_row('NpcParam', 120000)['fields']}
    assert fields['def_fire'] == 'fireDef'
    assert fields['physGuardCutRate'] == 'physicalDef'
    assert fields['slashGuardCutRate'] is None
    assert fields['resist_desease'] is None
    assert fields['isWeakSaint'] is None
    assert fields['staminaGuardDef'] is None
    assert fields['hp'] is None



def test_damage_taken_labels_carry_multiplier_unit():
    doc = ItemDocument(make_archive())
    labels = {field['key']: field['label']
              for field in doc.read_row('NpcParam', 120000)['fields']}
    assert labels['weakPartsDamageRate'] == 'Damage taken: weak point (x)'
    for index in range(1, 9):
        assert labels[f'partsDamageRate{index}'] == f'Damage taken: Part {index} (x)'
    assert labels['staminaRecoverBaseVel'] == 'Stamina recovery (stamina/second)'
