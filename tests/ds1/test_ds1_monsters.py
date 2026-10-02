"""Resistance-only edits, classification, validation, and byte preservation."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument, FormatError, inflate, SIZES
from plugins.ds1.monsters import RESISTANCES
from plugins.ds1.store import ItemStore, RELATIVE, MARKER
from plugins.ds3.formats import write_field


def test_only_reviewed_monsters_and_only_resistance_fields_are_accessible():
    doc = ItemDocument(make_archive())
    assert [row['id'] for row in doc.list_rows('monsters')] == [120000, 120100]
    assert {field['key'] for field in doc.read_row('NpcParam', 120000)['fields']} == set(RESISTANCES)
    assert all(field['editable'] for field in doc.read_row('NpcParam', 120000)['fields'])
    # Stray Demon deliberately has type 0, and Egg Carrier shares a monster
    # family name but has type 2. Neither name-only nor type-only filtering works.
    for excluded in (251000, 223000, 321001, 502, 999999):
        with pytest.raises(FormatError, match='not a reviewed'):
            doc.read_row('NpcParam', excluded)
        with pytest.raises(FormatError, match='not a reviewed'):
            doc.edit('NpcParam', excluded, 'def_phys', 10)
    for key in ('hp', 'npcType', 'teamType', 'spEffectID0', 'poisonGuardResist'):
        with pytest.raises(FormatError, match='protected'):
            doc.edit('NpcParam', 120000, key, 1)


def test_all_resistances_roundtrip_only_their_cells_and_revert_exactly():
    original = make_archive()
    doc = ItemDocument(original)
    assert doc.export() == original
    allowed = set()
    for key in RESISTANCES:
        spec = next(f['spec'] for f in doc.schemas['NpcParam']['fields'] if f['spec'].key == key)
        start = doc._row('NpcParam', 120000)[1] + spec.offset
        allowed.update(range(start, start + SIZES[spec.dtype]))
        doc.edit('NpcParam', 120000, key, 25.5 if spec.dtype == 'f32' else 25)
    reopened = ItemDocument(doc.export())
    for key in RESISTANCES:
        assert reopened.value('NpcParam', 120000, key) in (25, 25.5)
    changed = {index for index, (a, b) in enumerate(zip(inflate(original), inflate(doc.export()))) if a != b}
    assert changed and changed <= allowed
    for key in RESISTANCES:
        doc.edit('NpcParam', 120000, key, 0)
    assert doc.dirty_count == 0 and doc.export() == original


@pytest.mark.parametrize('field,value', [('def_phys', -1), ('def_phys', 10000), ('def_phys', 1.5),
    ('def_slash', -101), ('resist_poison', 1000), ('physGuardCutRate', 101),
    ('physGuardCutRate', float('nan')), ('def_mag', '10')])
def test_resistance_bounds_and_types_are_enforced(field, value):
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
