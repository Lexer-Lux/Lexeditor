"""DS1 starting-ring help: five fields, two ring slots.

CharaInitParam carries five accessory fields but the game has two ring
slots, so Rings 1-2 are the worn rings and Rings 3-5 are unused spares
no shipped class or gift fills. The bubbles must say so instead of
repeating their labels.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ds1.formats import schema  # noqa: E402


def test_ring_help_states_the_two_slot_truth():
    fields = {entry['spec'].key: entry['spec']
              for entry in schema('CharaInitParam')['fields']}
    first = fields['equip_Accessory01'].description
    second = fields['equip_Accessory02'].description
    assert 'first ring slot' in first and 'two ring slots' in first
    assert 'second ring slot' in second and 'two ring slots' in second
    for key in ('equip_Accessory03', 'equip_Accessory04', 'equip_Accessory05'):
        description = fields[key].description
        assert 'Unused' in description, key
        assert 'two ring slots' in description, key
