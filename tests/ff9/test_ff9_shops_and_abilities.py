"""Synthetic schemas only: no proprietary or upstream game records committed."""
from pathlib import Path

import pytest

from plugins.ff9 import memoria_csv as csv, paths


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "GAME_ROOT", tmp_path / "game")
    monkeypatch.setattr(paths, "PROJECT_ROOT", tmp_path / "project")
    monkeypatch.setattr(paths, "DATA_ROOT", tmp_path / "cache")
    monkeypatch.setattr(csv, "ensure_baseline", lambda: {"ready": True})
    return csv.MemoriaDataStore()


def fixture(store, relative, data):
    path = store.baseline_roots[0] / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


ITEMS = (b"# Comment;Id;WeaponId;Price;SellingPrice\n"
         b"# ;Int32;Int32;UInt32;Int32\n"
         b"Dagger;1;0;320;160;# Dagger\n"
         b"Mage Masher;2;0;500;250;# Mage Masher\n")
SHOPS = (b"# Comment;Id;Items\n"
         b"# ;Int32;Int32[]\n"
         b"Shop 0000;0;1, 2;# Shop 0000 Dali Weapon Shop\n"
         b"Shop 0023;23;;# Shop 0023 A Closed Shop\n")
ACTIONS = (b"# Comment;id;mp\n"
           b"# ;Int32;Int32\n"
           b"Cura;2;10;# Cura\n"
           b"Life;5;25;# Life\n")
BEATRIX = (b"# Id;AP\n"
           b"# Ability;Int32\n"
           b"AA:2;0;# Cura\n"
           b"AA:5;0;# Life\n"
           b"0;0;# Void\n"
           b"0;0;# Void\n")
GEMS = (b"# Id;Gems\n"
        b"# Int32;Int32\n"
        b"1;2;# Auto-Reflect\n")


def stocked(store):
    fixture(store, "Items/Items.csv", ITEMS)
    fixture(store, "Items/ShopItems.csv", SHOPS)


def test_item_prices_are_named_for_what_they_do(store):
    stocked(store)
    loaded = store.load("items")
    labels = {field["key"]: field["label"] for field in loaded["fields"]}
    assert labels["Price"] == "Buy price" and labels["SellingPrice"] == "Sell price"
    # The column keys do not move: the file still says Price and SellingPrice.
    assert "Price" in loaded["rows"][0]["values"]


def test_synthesis_keeps_its_own_price_name(store):
    fixture(store, "Items/Synthesis.csv",
            b"# Comment;Id;Shops;Price\n# ;Int32;Int32[];UInt32\nButterfly;0;32;300;# Butterfly\n")
    loaded = store.load("synthesis")
    labels = {field["key"]: field["label"] for field in loaded["fields"]}
    assert labels["Price"] == "Price"


def test_shop_stock_resolves_every_id_to_its_item(store):
    stocked(store)
    loaded = store.load("shops")
    first, closed = loaded["rows"][0], loaded["rows"][1]
    assert first["name"] == "Dali Weapon Shop"
    assert first["stock"] == [
        {"id": 1, "name": "Dagger", "buyPrice": 320, "sellPrice": 160, "resolved": True},
        {"id": 2, "name": "Mage Masher", "buyPrice": 500, "sellPrice": 250, "resolved": True},
    ]
    assert closed["stock"] == []
    # The ids stay the editable truth of the row.
    assert first["values"]["Items"] == "1, 2"


def test_shop_stock_survives_a_missing_item_table(store):
    fixture(store, "Items/ShopItems.csv", SHOPS)
    loaded = store.load("shops")
    assert [entry["name"] for entry in loaded["rows"][0]["stock"]] == ["Item 1", "Item 2"]
    assert all(entry["resolved"] is False for entry in loaded["rows"][0]["stock"])


def test_shop_save_still_writes_the_item_list(store):
    stocked(store)
    loaded = store.load("shops")
    saved = store.save("shops", loaded["sha256"],
                       [{"line": loaded["rows"][0]["line"], "values": {"Items": "2, 2"}}])
    assert [entry["name"] for entry in saved["rows"][0]["stock"]] == ["Mage Masher", "Mage Masher"]


def test_ability_rows_gain_their_battle_action_cost(store):
    fixture(store, "Characters/Abilities/Beatrix1.csv", BEATRIX)
    fixture(store, "Battle/Actions.csv", ACTIONS)
    loaded = store.load("ability-beatrix-1")
    assert [field["key"] for field in loaded["fields"]] == ["Id", "AP", "mp"]
    costs = {row["values"]["Id"]: (row["values"]["mp"], row["action"]) for row in loaded["rows"]}
    assert costs["AA:2"] == (10, "Cura")
    assert costs["AA:5"] == (25, "Life")
    assert costs["0"] == ("", None)


def test_unused_ability_slots_are_named_apart(store):
    fixture(store, "Characters/Abilities/Beatrix1.csv", BEATRIX)
    fixture(store, "Battle/Actions.csv", ACTIONS)
    loaded = store.load("ability-beatrix-1")
    assert [row["name"] for row in loaded["rows"]] == ["Cura", "Life", "Empty slot 1", "Empty slot 2"]


def test_support_abilities_gain_no_battle_cost(store):
    fixture(store, "Characters/Abilities/AbilityGems.csv", GEMS)
    fixture(store, "Battle/Actions.csv", ACTIONS)
    loaded = store.load("abilities")
    assert [field["key"] for field in loaded["fields"]] == ["Id", "Gems"]
    assert loaded["rows"][0]["name"] == "Auto-Reflect"


def test_ability_cost_is_derived_and_cannot_be_saved(store):
    fixture(store, "Characters/Abilities/Beatrix1.csv", BEATRIX)
    fixture(store, "Battle/Actions.csv", ACTIONS)
    loaded = store.load("ability-beatrix-1")
    field = next(value for value in loaded["fields"] if value["key"] == "mp")
    assert field["editable"] is False and field["declaredType"] == "DERIVED"
    with pytest.raises(ValueError, match="not an editable field"):
        store.save("ability-beatrix-1", loaded["sha256"],
                   [{"line": loaded["rows"][0]["line"], "values": {"mp": 5}}])


def test_missing_action_table_leaves_the_ability_list_intact(store):
    fixture(store, "Characters/Abilities/Beatrix1.csv", BEATRIX)
    loaded = store.load("ability-beatrix-1")
    assert [field["key"] for field in loaded["fields"]] == ["Id", "AP"]
    assert loaded["rows"][0]["action"] is None
    # AP is still editable, so the list is not degraded into a read-only view.
    saved = store.save("ability-beatrix-1", loaded["sha256"],
                       [{"line": loaded["rows"][0]["line"], "values": {"AP": 40}}])
    assert saved["rows"][0]["values"]["AP"] == 40
