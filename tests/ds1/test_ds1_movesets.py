"""Weapon animation sets are movesets, not single animations.

The weapon dropdowns pick a whole moveset - every attack, guard and
motion of a weapon family - with names from the community motion
category lists. Single animations are edited per character in the
Animations tab, where each row is the animation's own HKX file. The
field help says which is which, so the dropdowns no longer read as
a second, better-named animations list.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive  # noqa: E402
from plugins.ds1.formats import ItemDocument, schema  # noqa: E402


def test_moveset_dropdowns_carry_the_community_names():
    items = {item['spec'].key: item for item in schema('EquipParamWeapon')['fields']}
    assert items['wepmotionCategory']['enum']['23'] == 'Straight Sword'
    assert items['guardmotionCategory']['enum']['0'] == 'Shield'


def fields():
    document = ItemDocument(make_archive())
    row_id = document.params['EquipParamWeapon'].rows[0].row_id
    return {field['key']: field
            for field in document.read_row('EquipParamWeapon', row_id)['fields']}


def test_weapon_moveset_help_points_past_the_dropdown():
    description = fields()['wepmotionCategory']['description']
    assert 'moveset' in description.lower(), description
    assert 'Animations tab' in description, description


def test_guard_moveset_help_points_past_the_dropdown():
    description = fields()['guardmotionCategory']['description']
    assert 'moveset' in description.lower(), description
    assert 'Animations tab' in description, description
