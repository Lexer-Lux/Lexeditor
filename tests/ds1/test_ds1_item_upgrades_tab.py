"""Items detail: weapons and armor show an Upgrades panel tab.

Every property that decides what an item becomes as it is reinforced
lives under Upgrades: the upgrade path, materials, reinforcement cost
and (weapons only) ascension. Buffable flags and presentation
materials stay where they were. The Data Map says so per table.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ds1_fixture import make_archive  # noqa: E402
from plugins.ds1 import data_map  # noqa: E402
from plugins.ds1.store import MARKER, RELATIVE, ItemStore  # noqa: E402

EDITOR = (ROOT / "plugins" / "ds1" / "editor.js").read_text(encoding="utf-8")

WEAPON_UPGRADES = (
    {"materialSetId", "reinforceTypeId", "basicPrice", "isCustom",
     "disableBaseChangeReset", "baseChangeCategory"}
    | {"originEquipWep"} | {f"originEquipWep{level}" for level in range(1, 16)}
)
ARMOR_UPGRADES = (
    {"materialSetId", "reinforceTypeId", "basicPrice"}
    | {"originEquipPro"} | {f"originEquipPro{level}" for level in range(1, 16)}
)


def table_keys(table):
    root = ET.parse(ROOT / "plugins" / "ds1" / "metadata" / "meta" / f"{table}.xml").getroot()
    fields = next(child for child in root if child.tag == "Field")
    return [child.tag for child in fields]


def test_upgrade_keys_cover_every_upgrade_field():
    assert 'const UPGRADE_KEYS={EquipParamWeapon:new Set([' in EDITOR
    for table, expected in (("EquipParamWeapon", WEAPON_UPGRADES),
                            ("EquipParamProtector", ARMOR_UPGRADES)):
        keys = table_keys(table)
        for key in expected:
            assert key in keys, (table, key)
        upgrade_like = {key for key in keys
                        if "originequip" in key.lower() or "reinforcetype" in key.lower()
                        or "materialset" in key.lower()}
        assert upgrade_like <= expected, (table, sorted(upgrade_like - expected))
    for key in (WEAPON_UPGRADES | ARMOR_UPGRADES):
        if key.startswith("originEquip"):
            continue
        assert f'"{key}"' in EDITOR, key
    assert 'index?"originEquipWep"+index:"originEquipWep"' in EDITOR
    assert 'index?"originEquipPro"+index:"originEquipPro"' in EDITOR
    # Presentation materials and the buffable flag are not upgrades.
    for key in ("atkMaterial", "defMaterial", "defSfxMaterial", "defenseMaterial",
                "defenseMaterialSfx", "isEnhance"):
        assert key in table_keys("EquipParamWeapon") or key in table_keys("EquipParamProtector")
        assert key not in WEAPON_UPGRADES and key not in ARMOR_UPGRADES


def test_grouping_routes_upgrades_by_table():
    assert "function groupFor(field,table){" in EDITOR
    assert 'if(table&&UPGRADE_KEYS[table]&&UPGRADE_KEYS[table].has(field.key))return "Upgrades";' in EDITOR
    assert "const group=groupFor(byKey.get(keys[0]),row.table);" in EDITOR
    assert "const group=groupFor(field,row.table);" in EDITOR


def test_weapons_and_armor_open_an_upgrades_panel_tab():
    assert "function itemDetail(groups){" in EDITOR
    assert 'title==="Upgrades"' in EDITOR
    assert EDITOR.count("state.itemTab") >= 3
    assert ('if(state.tab==="items"&&(state.row.table==="EquipParamWeapon"'
            '||state.row.table==="EquipParamProtector"))') in EDITOR


def test_data_map_names_the_upgrades_tab(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    rows = {row["filename"]: row
            for row in data_map.payload(ItemStore(game, mod, False))["rows"]}
    weapon = rows["EquipParamWeapon.param"]
    assert weapon["openable"] and weapon["target"] == "items" and weapon["sub"] == "weapons"
    assert "Upgrades tab" in weapon["notes"] and "ascension" in weapon["notes"]
    armor = rows["EquipParamProtector.param"]
    assert armor["openable"] and armor["target"] == "items" and armor["sub"] == "armor"
    assert "Upgrades tab" in armor["notes"] and "ascension" not in armor["notes"]
    goods = rows["EquipParamGoods.param"]
    assert "Upgrades tab" not in goods["notes"]
