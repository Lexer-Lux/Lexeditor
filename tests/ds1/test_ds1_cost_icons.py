"""Costs carry the game's own icons.

Sell value is souls paid out, so it takes the level-up screen's souls
glyph in every item table: weapons, armor, accessories and goods.
Stamina Consumption is stamina spent per cast, so it takes the green
stamina bar frame.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ds1.formats import schema  # noqa: E402

TABLES = ('EquipParamWeapon', 'EquipParamProtector',
          'EquipParamAccessory', 'EquipParamGoods')


def test_sell_value_carries_the_souls_icon_in_every_item_table():
    for table in TABLES:
        items = {item['spec'].key: item for item in schema(table)['fields']}
        assert items['sellValue']['icon'] == 'souls', table


def test_stamina_consumption_carries_the_stamina_icon():
    items = {item['spec'].key: item for item in schema('Magic')['fields']}
    assert items['stamina']['icon'] == 'stamina'


def test_behavior_action_costs_carry_their_cost_icons():
    items = {item['spec'].key: item for item in schema('BehaviorParam')['fields']}
    assert items['stamina']['icon'] == 'stamina'
    assert items['mp']['icon'] == 'mp'
    assert items['heroPoint']['icon'] == 'humanity'
