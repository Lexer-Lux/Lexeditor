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


def test_drop_tables_say_which_slot_is_live():
    label, group, description = NPC_FIELDS['itemLotId_1']
    assert label == 'Drop table 1'
    assert group == 'Value & rewards'
    assert '-1' in description
    for index in range(2, 7):
        label, group, description = NPC_FIELDS[f'itemLotId_{index}']
        assert label == f'Drop table {index}'
        assert 'spare' in description.lower()
        assert '-1' in description


def test_only_reviewed_monsters_and_only_stat_fields_are_accessible():
    doc = ItemDocument(make_archive())
    assert [row['id'] for row in doc.list_rows('monsters')] == [120000, 120100]
    assert {field['key'] for field in doc.read_row('NpcParam', 120000)['fields']} == set(NPC_FIELDS) | {'effectiveHp'}
    fields = doc.read_row('NpcParam', 120000)['fields']
    assert all(field['editable'] for field in fields if field['key'] != 'effectiveHp')
    effective = next(field for field in fields if field['key'] == 'effectiveHp')
    assert not effective['editable'] and effective['value'] == 0
    # Stray Demon has type 0 like a monster but lists under Bosses now; Egg
    # Carrier shares a monster family name but has type 2. Neither name-only
    # nor type-only filtering works.
    # 251000 and 321001 are friendly (type 2): the NPCs tab reviews them.
    for excluded in (502, 999999):
        with pytest.raises(FormatError, match='not a reviewed'):
            doc.read_row('NpcParam', excluded)
        with pytest.raises(FormatError, match='not a reviewed'):
            doc.edit('NpcParam', excluded, 'def_phys', 10)
    others = [f['spec'].key for f in doc.schemas['NpcParam']['fields']
              if f['spec'].key not in NPC_FIELDS and f['spec'].key != 'behaviorVariationId']
    assert others and 'npcType' in others
    for key in others:
        with pytest.raises(FormatError, match='protected'):
            doc.edit('NpcParam', 120000, key, 1)
    # The behavior set writes through its own validated path, not the field gate.
    doc.edit('NpcParam', 120000, 'behaviorVariationId', 12010)
    assert doc.value('NpcParam', 120000, 'behaviorVariationId') == 12010


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
        value = 101 if key == 'aiThinkId' else 1 if spec.is_bool else int(sorted(item['enum'], key=int)[-1]) if item['enum'] else 25.5 if spec.dtype == 'f32' else 25
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
    # Damage and defense labels show the equipment screen's own icons. Slash,
    # strike and thrust have no glyph of their own, so they reuse the physical
    # shield: every one of these fields scales physical defense. Resistances
    # show the shared status glyphs before their labels. Kinds with no icon
    # and no parent stat (weaknesses, stamina guard) ship with none: game art
    # or shared glyphs only, no invented glyphs.
    fields = {field['key']: field.get('icon')
              for field in ItemDocument(make_archive()).read_row('NpcParam', 120000)['fields']}
    assert fields['def_fire'] == 'fireDef'
    assert fields['physGuardCutRate'] == 'physicalDef'
    assert fields['def_slash'] == 'physicalDef'
    assert fields['slashGuardCutRate'] == 'physicalDef'
    assert fields['blowGuardCutRate'] == 'physicalDef'
    assert fields['thrustGuardCutRate'] == 'physicalDef'
    assert fields['resist_poison'] == 'poison'
    assert fields['resist_desease'] == 'toxic'
    assert fields['resist_blood'] == 'bleed'
    assert fields['resist_curse'] == 'curse'
    assert fields['isWeakSaint'] is None
    assert fields['staminaGuardDef'] is None
    assert fields['hp'] == 'vit'
    assert fields['mp'] == 'att'
    assert fields['stamina'] == 'end'
    assert fields['staminaRecoverBaseVel'] == 'end'
    assert fields['getSoul'] == 'souls'
    assert fields['humanityLotId'] == 'humanity'
    assert fields['superArmorDurability'] == 'poise'
    assert fields['superArmorRecoverCorrection'] == 'poise'
    assert fields['superArmorBrakeKnockbackDist'] == 'poise'



def test_damage_taken_labels_carry_multiplier_unit():
    doc = ItemDocument(make_archive())
    labels = {field['key']: field['label']
              for field in doc.read_row('NpcParam', 120000)['fields']}
    assert labels['weakPartsDamageRate'] == 'Damage taken: weak point (x)'
    for index in range(1, 9):
        assert labels[f'partsDamageRate{index}'] == f'Damage taken: Part {index} (x)'
    assert labels['staminaRecoverBaseVel'] == 'Stamina recovery (stamina/second)'


PLACED_BOSS_PART_IDS = (273100, 342100, 342200, 343100, 347200, 353100, 353101, 451100,
                        520100, 520200, 526100, 535200, 535300, 535301, 540000, 540100)


def test_placed_rows_are_admitted_by_id_and_other_parts_stay_out():
    ids = [120000, 342101, *PLACED_BOSS_PART_IDS, 342201, 273101, 502]
    doc = ItemDocument(make_archive({'NpcParam': ids}))
    monsters = {row['id'] for row in doc.list_rows('monsters')}
    bosses = {row['id'] for row in doc.list_rows('bosses')}
    assert 342101 in monsters and 342101 not in bosses
    assert doc.schemas['NpcParam']['names'][342101] == 'Bounding Demon of Izalith'
    assert set(PLACED_BOSS_PART_IDS) <= bosses
    assert not set(PLACED_BOSS_PART_IDS) & monsters
    # 342100 keeps its reference name, distinct from 342101.
    assert doc.schemas['NpcParam']['names'][342100] == 'Undead Dragon - Legs'
    # An unplaced part of the same boss, a sibling ID and a test row stay shut.
    for excluded in (342201, 273101, 502):
        assert not doc.is_monster(excluded) and not doc.is_boss(excluded)
        with pytest.raises(FormatError, match='not a reviewed'):
            doc.read_row('NpcParam', excluded)


def test_bounding_demon_takes_armor_rework_absorption_edits():
    base = 40_000_000 + 342101
    doc = ItemDocument(make_effects_archive(extra_ids=(base,), table_ids={'NpcParam': [120000, 342101]}))
    _row, start, data = doc._row('NpcParam', 342101)
    spec = next(f['spec'] for f in doc.schemas['NpcParam']['fields'] if f['spec'].key == 'spEffectID0')
    doc.plain[start:start + len(data)] = write_field(data, spec, base, '<')
    doc.edit('NpcParam', 342101, 'absorption:thunderDamageCutRate', -50)
    assert doc.row_values('NpcParam', 342101)[0]['absorption:thunderDamageCutRate'] == -50.0
