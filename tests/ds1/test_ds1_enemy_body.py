"""Enemy hitbox and damage-taken fields live on their own Body tab.

The Defense tab used to mix flat defenses and resistances with the
hitbox (Body height/radius/offset) and the damage-taken multipliers
(weak point, body parts). Those are the enemy's body, not its armor,
so they group under Body, ordered just before Defense. Bosses and
monsters share NpcParam, so one grouping covers both.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ds1.monsters import NPC_FIELDS  # noqa: E402

BODY_KEYS = ({"hitHeight", "hitRadius", "hitYOffset", "weakPartsDamageRate"}
             | {f"partsDamageRate{index}" for index in range(1, 9)})
DEFENSE_KEYS = ({"def_phys", "def_mag", "def_fire", "def_thunder",
                 "def_slash", "def_blow", "def_thrust",
                 "resist_poison", "resist_desease", "resist_blood", "resist_curse",
                 "isWeakSaint", "isWeakA", "isWeakB"})


def group_of(key):
    return NPC_FIELDS[key][1]


def test_hitbox_and_damage_taken_group_under_body():
    assert BODY_KEYS <= set(NPC_FIELDS), BODY_KEYS - set(NPC_FIELDS)
    assert {key for key in BODY_KEYS if group_of(key) == "Body"} == BODY_KEYS


def test_flat_defense_and_resistance_stay_under_defense():
    assert {key for key in DEFENSE_KEYS if group_of(key) == "Defense"} == DEFENSE_KEYS


def test_body_tab_orders_just_before_defense():
    source = (ROOT / "plugins" / "ds1" / "editor.js").read_text()
    match = re.search(r"GROUP_ORDER=\[(.*?)\]", source, re.DOTALL)
    assert match, "GROUP_ORDER not found in the DS1 editor"
    order = re.findall(r'"([^"]+)"', match.group(1))
    assert "Body" in order and "Defense" in order, order
    assert order.index("Body") < order.index("Defense"), order
