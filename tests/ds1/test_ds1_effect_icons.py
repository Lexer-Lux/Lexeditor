"""Effect absorption and resistance carry the game's own icons.

Slash, strike and thrust absorption reuse the physical shield, like
every other slash/strike/thrust field: the game draws those kinds as
text, never as glyphs. Poison and toxic resistance take the status
cure-item icons, matching bleed and curse.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ds1.formats import schema  # noqa: E402


def effects():
    return {item['spec'].key: item for item in schema('SpEffectParam')['fields']}


def test_slash_strike_thrust_absorption_reuse_the_physical_shield():
    items = effects()
    assert items['slashDamageCutRate']['icon'] == 'physicalDef'
    assert items['blowDamageCutRate']['icon'] == 'physicalDef'
    assert items['thrustDamageCutRate']['icon'] == 'physicalDef'


def test_poison_and_toxic_resistance_take_the_status_icons():
    items = effects()
    assert items['registPoizonChangeRate']['icon'] == 'poison'
    assert items['registIllnessChangeRate']['icon'] == 'toxic'
    assert items['registIllness']['icon'] == 'toxic'
    assert items['poizonAttackPower']['icon'] == 'poison'


def test_bleed_and_curse_icons_are_unchanged():
    items = effects()
    assert items['registBlood']['icon'] == 'bleed'
    assert items['registCurse']['icon'] == 'curse'
    assert items['registBloodChangeRate']['icon'] == 'bleed'
    assert items['registCurseChangeRate']['icon'] == 'curse'
