"""Projectile properties arrive in named sections, not one Properties pile."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive
from plugins.ds1.attacks import BULLET_GROUPS
from plugins.ds1.formats import ItemDocument, BULLET_EDITABLE


def test_bullet_groups_cover_every_editable_field():
    assert set(BULLET_GROUPS) == set(BULLET_EDITABLE)


def test_every_bullet_field_shows_a_named_section():
    fields = ItemDocument(make_archive()).read_row('Bullet', 100)['fields']
    assert {entry['key'] for entry in fields} == set(BULLET_EDITABLE)
    groups = {entry['key']: entry['group'] for entry in fields}
    assert all(group and group != 'Properties' for group in groups.values()), \
        sorted(key for key, group in groups.items() if not group or group == 'Properties')


def test_bullet_sections_read_in_flight_order():
    fields = ItemDocument(make_archive()).read_row('Bullet', 100)['fields']
    assert list(dict.fromkeys(entry['group'] for entry in fields)) == [
        'Lifetime & range', 'Flight', 'Homing', 'Spread', 'Hitbox',
        'Damage', 'Flags', 'Attack & effects']
