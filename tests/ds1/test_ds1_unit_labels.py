"""Percent units ride the unit control, never the bare label.

Smithbox names carry the % bare ('Critical Hit %') or mid-label
('Guard Absorption %: Physical'), which never engages the client's
trailing-(%) unit control. Every label reaches the UI in the 'Name
(%)' form, so the name reads clean and the % sits in its component.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ds1.formats import TABLES, _unit_suffix, schema  # noqa: E402


def labels(table):
    return {item['spec'].key: item['spec'].label
            for item in schema(table)['fields']}


def test_critical_hit_uses_the_unit_component():
    assert labels('EquipParamWeapon')['throwAtkRate'] == 'Critical Hit (%)'


def test_mid_label_percent_moves_to_the_end():
    assert _unit_suffix('Guard Absorption %: Physical') == 'Guard Absorption: Physical (%)'
    assert _unit_suffix('Critical Hit %') == 'Critical Hit (%)'
    assert _unit_suffix('Weight (kg)') == 'Weight (kg)'
    assert _unit_suffix('Damage Falloff: Physical (%/s)') == 'Damage Falloff: Physical (%/s)'


def test_no_bare_percent_survives_in_any_label():
    for table in TABLES:
        for key, label in labels(table).items():
            scrubbed = label.replace('(%)', '').replace('(%/s)', '')
            assert '%' not in scrubbed, (table, key, label)
