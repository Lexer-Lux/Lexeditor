"""Issue #742: the Spells tab's per-spell mana cost override.

Vanilla Dark Souls ignores Magic.mp (all 141 vanilla rows are 0), so the
Mana tweak reads it as the spell's mana cost, and 0 keeps the derived
X/N default. These tests pin the editor property that carries that
override, using synthetic archives only.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument, schema


def test_mana_override_label_and_help():
    fields = schema('Magic')['fields']
    mp = next(item for item in fields if item['spec'].key == 'mp')
    assert mp['spec'].label == 'Mana cost override'
    assert '0 uses the tweak' in mp['spec'].description
    assert 'ignores' in mp['spec'].description


def test_usage_count_names_mana_derivation():
    fields = schema('Magic')['fields']
    usages = next(item for item in fields if item['spec'].key == 'maxQuantity')
    assert usages['spec'].label == 'Usage Count'
    assert 'mana' in usages['spec'].description.casefold()


def test_spells_show_an_editable_mana_override():
    document = ItemDocument(make_archive())
    rows = [row for row in document.list_rows('spells') if row['table'] == 'Magic']
    assert [row['id'] for row in rows] == [100, 101, 102]
    fields = document.read_row('Magic', 100)['fields']
    mp = next(field for field in fields if field['key'] == 'mp')
    assert mp['label'] == 'Mana cost override'
    assert mp['editable'] and mp['type'] == 'number'
    assert mp['value'] == 0 and mp['vanilla'] == 0


def test_mana_override_roundtrip():
    document = ItemDocument(make_archive())
    document.edit('Magic', 100, 'mp', 25)
    assert document.value('Magic', 100, 'mp') == 25
    assert document.value('Magic', 100, 'maxQuantity') == 0
    reopened = ItemDocument(document.export())
    assert reopened.value('Magic', 100, 'mp') == 25
    assert reopened.value('Magic', 101, 'mp') == 0
