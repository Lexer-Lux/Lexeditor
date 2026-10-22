"""Trophy fields read as achievement names, not bare numbers.

Decoded from the shipped Remastered GameParam: trophySeqId holds the
achievement an item grants (16-25 the ten upgrade-path weapons at
their final step, 27 Estus Flask, 31 Rite of Kindling, 32 Art of
Abysswalking, 34 Lordvessel); trophySGradeId holds a Knight's Honor
checklist slot (the 47 graded weapons are exactly the 47 rare
weapons); compTrophySedId on goods holds the collection achievement
a spell scroll counts toward (4 Wisdom of a Sage, 5 Bond of a
Pyromancer, 6 Prayer of a Maiden).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive  # noqa: E402
from plugins.ds1.formats import ItemDocument, schema  # noqa: E402


def enums(table):
    return {item['spec'].key: item['enum']
            for item in schema(table)['fields']}


def test_seq_dropdown_names_the_achievements():
    seq = enums('EquipParamWeapon')['trophySeqId']
    assert seq['-1'] == 'None'
    assert seq['16'] == 'Strongest Weapon'
    assert seq['17'] == 'Crystal Weapon'
    assert seq['25'] == 'Chaos Weapon'
    assert seq['27'] == 'Estus Flask'
    assert seq['31'] == 'Rite of Kindling'
    assert seq['32'] == 'Art of Abysswalking'
    assert seq['34'] == 'Lordvessel'


def test_grade_dropdown_names_knights_honor_slots():
    grade = enums('EquipParamWeapon')['trophySGradeId']
    assert grade['-1'] == 'None'
    assert grade['0'] == 'None'
    assert grade['104'] == "Knight's Honor (#104)"
    assert grade['1545'] == "Knight's Honor (#1545)"
    assert len(grade) == 2 + 47


def test_comp_dropdown_names_collection_achievements():
    comp = enums('EquipParamGoods')['compTrophySedId']
    assert comp['-1'] == 'None'
    assert comp['4'] == 'Wisdom of a Sage'
    assert comp['5'] == 'Bond of a Pyromancer'
    assert comp['6'] == 'Prayer of a Maiden'


def payload(table):
    document = ItemDocument(make_archive())
    row_id = document.params[table].rows[0].row_id
    return {field['key']: field
            for field in document.read_row(table, row_id)['fields']}


def test_trophy_fields_render_as_enum_dropdowns():
    weapons = payload('EquipParamWeapon')
    assert weapons['trophySeqId']['type'] == 'enum'
    assert weapons['trophySGradeId']['type'] == 'enum'
    assert payload('EquipParamGoods')['compTrophySedId']['type'] == 'enum'


def test_weapon_seq_help_names_the_final_step():
    description = payload('EquipParamWeapon')['trophySeqId']['description']
    assert 'final step' in description, description
    assert 'upgrade path' in description, description


def test_item_seq_help_says_pickup():
    description = payload('EquipParamGoods')['trophySeqId']['description']
    assert 'picks up' in description, description


def test_grade_help_names_knights_honor():
    description = payload('EquipParamWeapon')['trophySGradeId']['description']
    assert "Knight's Honor" in description, description


def test_comp_help_says_counts_toward():
    description = payload('EquipParamGoods')['compTrophySedId']['description']
    assert 'counts toward' in description, description
