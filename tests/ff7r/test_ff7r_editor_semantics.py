from pathlib import Path


import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui


def test_item_and_enemy_loot_tabs_are_first_class_surfaces():
    html = plugin_ui("ff7r")
    # Equipment, Item and Materia are three top-level tabs, not one tab with a
    # subtab bar: they are three separate tables in the game and the plugin
    # already knows all three names.
    for tab in ('{id:"equipment",label:"Equipment"}',
                '{id:"item",label:"Items"}',
                '{id:"materia",label:"Materia"}'):
        assert tab in html
    assert '{id:"loot",label:"Enemy Loot"}' in html
    assert 'api(`/api/economy?' in html
    assert 'api(`/api/loot?' in html
    assert 'BuyValue' in html
    assert 'SaleValue' in html
    assert 'CanSale' in html
    assert 'MaxCount' in html
    assert 'MAX CARRY' in html
    assert 'BattleItemPossession' in html


def test_loot_chance_editor_is_percent_bounded_and_reuses_generic_save_path():
    html = plugin_ui("ff7r")
    assert 'min:0,max:100' in html
    assert 'Math.max(0,Math.min(100,value))' in html
    assert 'api("/api/save"' in html
    assert '["misc","loot","text","tweaks"].includes(state.tab)' in html
    assert "isEconomyTab(state.tab)" in html
    assert "!!curatedSpec(state.tab)" in html
