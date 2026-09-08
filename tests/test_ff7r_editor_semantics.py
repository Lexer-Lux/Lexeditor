from pathlib import Path


EDITOR = Path(__file__).resolve().parents[1] / "games" / "ff7r" / "editor.html"


def test_item_and_enemy_loot_tabs_are_first_class_surfaces():
    html = EDITOR.read_text(encoding="utf-8")
    assert '{id:"economy",label:"Items"}' in html
    assert '{id:"loot",label:"Enemy Loot"}' in html
    assert 'api(`/api/economy?' in html
    assert 'api(`/api/loot?' in html
    assert 'BuyValue' in html
    assert 'SaleValue' in html
    assert 'CanSale' in html
    assert 'BattleItemPossession' in html


def test_loot_chance_editor_is_percent_bounded_and_reuses_generic_save_path():
    html = EDITOR.read_text(encoding="utf-8")
    assert 'min:0,max:100' in html
    assert 'Math.max(0,Math.min(100,value))' in html
    assert 'api("/api/save"' in html
    assert '["data","economy","loot","text"].includes(state.tab)' in html
