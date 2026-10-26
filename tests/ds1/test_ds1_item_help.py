"""Item property help says what is known, and says so when it is unknown."""
import json
from pathlib import Path
METADATA = Path(__file__).resolve().parents[2] / "plugins/ds1/metadata"
def description(relative, field):
    annotations = json.loads((METADATA / relative).read_text("utf-8-sig"))
    return next(entry["Description"] for entry in annotations["Fields"] if entry["Field"] == field)
def test_over_dexterity_says_unknown():
    # The Souls modding param wiki marks overDexterity Unknown on Magic, and
    # no source documents the Goods twin either. The old text ("Skill over
    # start value") explained nothing.
    for relative in ("annotations/EQUIP_PARAM_GOODS_ST.json", "annotations/MAGIC_PARAM_ST.json"):
        assert description(relative, "overDexterity").startswith("Unknown."), relative
def test_drop_weight_help_says_relative_and_guarantee():
    text = description("annotations/ITEMLOT_PARAM_ST.json", "lotItemBasePoint01")
    assert "compared with the other slots" in text
    assert "always grant" in text
def test_drop_accumulation_help_says_bonus_and_off():
    text = description("annotations/ITEMLOT_PARAM_ST.json", "cumulateLotPoint01")
    assert "Lot section" in text
    assert "0 turns the bonus off" in text
def test_drop_item_flag_help_keeps_the_hedge():
    # FromSoftware's own param text only confirms the game sets this flag
    # after granting the slot; nobody has shown a set flag blocks re-drops.
    text = description("annotations/ITEMLOT_PARAM_ST.json", "getItemFlagId01")
    assert "0 uses the Lot section flag" in text
    assert "not established" in text
def test_drop_luck_help_says_discovery_lowers():
    text = description("annotations/ITEMLOT_PARAM_ST.json", "enableLuck01")
    assert "Item Discovery" in text
    assert "lowers" in text
def test_drop_reset_help_says_roll_count():
    text = description("annotations/ITEMLOT_PARAM_ST.json", "cumulateReset01")
    assert "roll count" in text
def test_drop_slot_help_is_one_text_per_property():
    annotations = json.loads((METADATA / "annotations/ITEMLOT_PARAM_ST.json").read_text("utf-8-sig"))
    by_field = {entry["Field"]: entry["Description"] for entry in annotations["Fields"]}
    for stem in ("lotItemBasePoint", "cumulateLotPoint", "getItemFlagId",
                 "enableLuck", "cumulateReset"):
        texts = {by_field[f"{stem}{index:02d}"] for index in range(1, 9)}
        assert len(texts) == 1, stem
def test_sweep_rewrites_speffects():
    assert description("annotations/SP_EFFECT_PARAM_ST.json", "maxHpChangeRate").startswith("Unused.")
    assert description("annotations/SP_EFFECT_PARAM_ST.json", "vowType0") == "The effect only works with no covenant."
    assert description("annotations/SP_EFFECT_PARAM_ST.json", "changeMagicSlot") == ""
    assert description("annotations/SP_EFFECT_PARAM_ST.json", "effectTargetSelf") == ""
    # Lexer's restored line stays untouched.
    assert "stateInfo 158" in description("annotations/SP_EFFECT_PARAM_ST.json", "guardStaminaCutRate")
def test_sweep_rewrites_npcs():
    assert "NG+ bonus" in description("annotations/NPC_PARAM_ST.json", "hp")
    assert description("annotations/NPC_PARAM_ST.json", "knockbackParamId").startswith("Unknown.")
    assert description("annotations/NPC_PARAM_ST.json", "lockDist").startswith("Extra distance")
def test_sweep_rewrites_armor():
    assert description("annotations/EQUIP_PARAM_PROTECTOR_ST.json", "knockbackParamId").startswith("Unknown.")
    assert "deflects" in description("annotations/EQUIP_PARAM_PROTECTOR_ST.json", "flickDamageCutRate")
    assert description("annotations/EQUIP_PARAM_PROTECTOR_ST.json", "saDurability").startswith("Lets you")
def test_sweep_rewrites_chargen_and_shops_and_behavior():
    assert ";" not in description("annotations/CHARACTER_INIT_PARAM.json", "baseLuc")
    assert "lands on" in description("annotations/CHARACTER_INIT_PARAM.json", "red_Falldam")
    assert "unlimited" in description("annotations/SHOP_LINEUP_PARAM.json", "sellQuantity")
    assert "no MP pool" in description("annotations/BEHAVIOR_PARAM_ST.json", "mp")
def test_sweep_rewrites_melee():
    assert "Blown Away" in description("annotations/ATK_PARAM_ST.json", "dmgLevel")
    assert "less HP" in description("annotations/ATK_PARAM_ST.json", "atkObj")
    assert "five stages" in description("annotations/CACL_CORRECT_GRAPH_ST.json", "stageMaxVal0")
    assert "centimetres" in description("annotations/OBJ_ACT_PARAM_ST.json", "validDist")
def test_sweep_rewrites_goods_and_accessories():
    assert "Way of White" in description("annotations/EQUIP_PARAM_GOODS_ST.json", "vowType1")
    assert description("annotations/EQUIP_PARAM_GOODS_ST.json", "basicPrice").startswith("Probably does nothing")
    assert "Equip Load" in description("annotations/EQUIP_PARAM_GOODS_ST.json", "weight")
    assert description("annotations/EQUIP_PARAM_ACCESSORY_ST.json", "accessoryCategory") == ""
    assert "None leaves the slot empty" in description("annotations/EQUIP_MTRL_SET_PARAM_ST.json", "materialId01")
def test_sweep_rewrites_ranged_and_reinforce():
    assert "Do not follow" in description("annotations/BULLET_PARAM_ST.json", "FollowType")
    assert "3 stops dark shots" in description("annotations/BULLET_PARAM_ST.json", "attachEffectType")
    assert "unupgraded weapon" in description("annotations/REINFORCE_PARAM_WEAPON_ST.json", "physicsAtkRate")
    assert "unupgraded armor" in description("annotations/REINFORCE_PARAM_PROTECTOR_ST.json", "physicsDefRate")
def test_sweep_rewrites_magic_and_think():
    assert "turns the swap off" in description("annotations/MAGIC_PARAM_ST.json", "replaceMagicId")
    assert description("annotations/MAGIC_PARAM_ST.json", "vowType10").startswith("Unused.")
    assert "tenths of a second" in description("annotations/NPC_THINK_PARAM_ST.json", "callHelp_MinWaitTime")
    assert "How tall" in description("annotations/NPC_THINK_PARAM_ST.json", "eye_angX")
def test_sweep_rewrites_weapons():
    assert "Equip Load" in description("annotations/EQUIP_PARAM_WEAPON_ST.json", "weight")
    assert description("annotations/EQUIP_PARAM_WEAPON_ST.json", "rightHandEquipable") == ""
    assert "two-handed" in description("annotations/EQUIP_PARAM_WEAPON_ST.json", "bothHandEquipable")
    assert "1 fits Intelligence" in description("annotations/EQUIP_PARAM_WEAPON_ST.json", "correctType")
