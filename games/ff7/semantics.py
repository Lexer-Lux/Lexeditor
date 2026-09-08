"""Human-facing metadata for FF7 binary editor fields.

This module deliberately separates storage representation from editor language.
Writers keep the original integer/bitfield values; the UI consumes these
metadata dictionaries to present enums, named flags, references and explicit
advanced/raw fallbacks.
"""
from __future__ import annotations


def choices(*pairs):
    return [{"value": value, "label": label} for value, label in pairs]


def flags(*pairs):
    return [{"value": value, "label": label} for value, label in pairs]


STATUSES = (
    (0x00000001, "Death"), (0x00000002, "Near Death"), (0x00000004, "Sleep"),
    (0x00000008, "Poison"), (0x00000010, "Sadness"), (0x00000020, "Fury"),
    (0x00000040, "Confusion"), (0x00000080, "Silence"), (0x00000100, "Haste"),
    (0x00000200, "Slow"), (0x00000400, "Stop"), (0x00000800, "Frog"),
    (0x00001000, "Small"), (0x00002000, "Slow Numb"), (0x00004000, "Petrify"),
    (0x00008000, "Regen"), (0x00010000, "Barrier"), (0x00020000, "Magic Barrier"),
    (0x00040000, "Reflect"), (0x00080000, "Dual"), (0x00100000, "Shield"),
    (0x00200000, "Death Sentence"), (0x00400000, "Manipulate"), (0x00800000, "Berserk"),
    (0x01000000, "Peerless"), (0x02000000, "Paralysis"), (0x04000000, "Darkness"),
    (0x08000000, "Dual Drain"), (0x10000000, "Death Force"), (0x20000000, "Resist"),
    (0x40000000, "Lucky Girl"), (0x80000000, "Imprisoned"),
)

STATUS_INDEX = tuple((index, label) for index, (_, label) in enumerate(STATUSES)) + ((0xFF, "None"),)
ELEMENTS = (
    (0x0001, "Fire"), (0x0002, "Ice"), (0x0004, "Lightning"), (0x0008, "Earth"),
    (0x0010, "Poison"), (0x0020, "Gravity"), (0x0040, "Water"), (0x0080, "Wind"),
    (0x0100, "Holy"), (0x0200, "Restorative"), (0x0400, "Cut"), (0x0800, "Hit"),
    (0x1000, "Punch"), (0x2000, "Shoot"), (0x4000, "Shout"), (0x8000, "Hidden"),
)
TARGET_FLAGS = (
    (0x01, "Choose target"), (0x02, "Start cursor on enemies"),
    (0x04, "Start with multiple targets"), (0x08, "Allow single/all toggle"),
    (0x10, "Lock to one side"), (0x20, "Short range"),
    (0x40, "Target all rows"), (0x80, "Random target"),
)
EQUIPABLE = (
    (0x0001, "Cloud"), (0x0002, "Barret"), (0x0004, "Tifa"), (0x0008, "Aerith"),
    (0x0010, "Red XIII"), (0x0020, "Yuffie"), (0x0040, "Cait Sith"),
    (0x0080, "Vincent"), (0x0100, "Cid"), (0x0200, "Young Cloud"), (0x0400, "Sephiroth"),
)
CHARACTER_FLAGS = ((0x10, "Sadness"), (0x20, "Fury"))
LEARNED_LIMITS = (
    (0x0001, "Limit 1-1"), (0x0002, "Limit 1-2"), (0x0008, "Limit 2-1"),
    (0x0010, "Limit 2-2"), (0x0040, "Limit 3-1"), (0x0080, "Limit 3-2"),
    (0x2000, "Limit 4"),
)
CHARACTER_STATS = ((0, "Strength"), (1, "Vitality"), (2, "Magic"), (3, "Spirit"), (4, "Dexterity"), (5, "Luck"), (0xFF, "None"))
GROWTH_RATES = ((0, "No AP growth"), (1, "Normal AP growth"), (2, "Double AP growth"), (3, "Triple AP growth"))
DAMAGE_MODIFIERS = ((0, "Absorb"), (1, "Nullify"), (2, "Halve"), (0xFF, "Normal damage"))
ACCESSORY_EFFECTS = (
    (0xFF, "None"), (0, "Auto-Haste"), (1, "Auto-Berserk"), (2, "Curse Ring effect"),
    (3, "Auto-Reflect"), (4, "Increase stealing rate"), (5, "Increase Manipulate rate"), (6, "Auto-Wall"),
)
ATTACK_CONDITIONS = ((0, "HP"), (1, "MP"), (2, "Status"), (0xFF, "None"))
SHOP_TYPES = ((0, "Item"), (1, "Weapon"), (2, "Item (alternate)"), (3, "Materia"), (4, "General"), (5, "Vegetable"), (6, "Accessory"), (7, "Tool"), (8, "Hotel"))
SHOP_SLOT_KINDS = ((0, "Item / equipment"), (1, "Materia"))
CHOCOBO_RATINGS = ((1, "Wonderful"), (2, "Great"), (3, "Good"), (4, "Fair"), (5, "Average"), (6, "Poor"), (7, "Bad"), (8, "Terrible"))
COMMAND_ACTIONS = (
    (0x00, "Perform command using target data"), (0x01, "Magic menu"),
    (0x02, "Summon menu"), (0x03, "Item menu"), (0x04, "Enemy Skill menu"),
    (0x05, "Throw menu"), (0x06, "Limit menu"),
    (0x07, "Enable target selection via cursor"), (0x08, "W-Magic menu"),
    (0x09, "W-Summon menu"), (0x0A, "W-Item menu"), (0x0B, "Coin menu"),
    (0xFF, "No initial cursor action"),
)
MAGIC_MENU_GROUPS = ((0, "Restore"), (1, "Attack"), (2, "Indirect"), (3, "Special"), (0xFF, "Not listed"))

RESTRICTION_FLAGS = (
    (0x0001, "Can be sold"), (0x0002, "Can be used in battle"),
    (0x0004, "Can be used from the menu"), (0x0008, "Can be thrown"),
)
MATERIA_SLOTS = (
    (0, "No slot"), (1, "Unlinked — no AP growth"),
    (2, "Linked left — no AP growth"), (3, "Linked right — no AP growth"),
    (5, "Unlinked"), (6, "Linked left"), (7, "Linked right"),
)

SPECIAL_ATTACK_FLAGS = (
    (0x0001, "Damage MP instead of HP"),
    (0x0004, "Force physical damage"),
    (0x0010, "Drain part of inflicted damage"),
    (0x0020, "Drain HP and MP"),
    (0x0040, "Diffuse attack"),
    (0x0080, "Ignore status defense"),
    (0x0100, "Miss unless target is dead / undead"),
    (0x0200, "Reflectable"),
    (0x0400, "Ignore defense"),
    (0x0800, "Do not retarget after original target dies"),
    (0x2000, "Always critical"),
)

ADDITIONAL_EFFECTS = (
    (0xFF, "None"),
    (0x00, "Multiple hits (modifier = hit count)"),
    (0x01, "Gunge Lance if enemies are immune to status"),
    (0x02, "Fat Chocobo chance (modifier threshold)"),
    (0x03, "Transform caster to character ID in modifier"),
    (0x04, "Back-row damage rule using modifier"),
    (0x05, "End battle with no reward"),
    (0x06, "Steal gil"), (0x07, "Steal item"),
    (0x08, "Randomly choose one of next six animations"),
    (0x09, "8× damage if attacker and target levels match"),
    (0x0A, "Master Fist multiplier"), (0x0B, "Powersoul multiplier"),
    (0x0C, "Damage from KO'd allies"), (0x0D, "Power from average target level"),
    (0x0E, "Resurrect dead allies"), (0x0F, "Cait Sith Slots"), (0x10, "Cait Sith Transform"),
    (0x11, "Remove target as dead"), (0x12, "Remove target as escaped"),
    (0x13, "Tifa Slots damage"), (0x14, "Fill allies' Limit gauges"),
    (0x15, "Modify attack and defense by modifier − 100%"),
    (0x16, "Modify evasion by modifier − 100%"),
    (0x17, "Modify attack by modifier − 100%"),
    (0x18, "Perform attack ID stored in modifier"),
    (0x19, "Change target row"),
    (0x1A, "Perform modifier attack on other row members"),
    (0x1B, "Remove caster from battle"),
    (0x1C, "Modify defense by modifier − 100%"),
    (0x1D, "Return target from escaped state"),
    (0x1E, "Power from current HP"), (0x1F, "Power from current MP"),
    (0x20, "Power from current AP"), (0x21, "Power from character kills"),
    (0x22, "Power from Limit level"), (0x23, "No rewards from target"),
)

# Human summaries for the byte's upper/lower-nibble encoding. The exact raw
# value remains the edited value; unknown/modded combinations are preserved.
_NORMAL_FORMULAS = {
    0x0: "No damage", 0x1: "Standard stat/level formula", 0x2: "Simple stat/level formula",
    0x3: "Current HP percentage", 0x4: "Maximum HP percentage", 0x5: "Stronger simple formula",
    0x6: "Static damage (Power × 20)", 0x7: "Power ÷ 32", 0x8: "Full HP/MP recovery",
    0x9: "Throw formula", 0xA: "Coin formula",
}
_SPECIAL_FORMULAS = {0x0: "User current HP", 0x1: "User max HP − current HP", 0x8: "Dice × 100", 0x9: "Escapes × 256", 0xA: "Leave target at 1 HP", 0xB: "Clock time", 0xC: "Target kill count × 10", 0xD: "Materia count × 1111"}
_MULTIPLIER_FORMULAS = {0x0: "Master Fist", 0x1: "Powersoul", 0x2: "Dead allies", 0x3: "Average target level", 0x4: "Current HP multiplier", 0x5: "Current MP multiplier", 0x6: "Missing Score (weapon AP)", 0x7: "Death Penalty (kills)", 0x8: "Premium Heart (Limit gauge)"}


def damage_formula_choices():
    result = []
    accuracy = {0x0: "never misses", 0x1: "normal accuracy; can crit", 0x2: "normal magical accuracy", 0x3: "never misses (type 2)", 0x4: "never misses magical", 0x5: "never misses magical (type 2)", 0x6: "normal accuracy; can crit", 0x7: "normal magical accuracy", 0x8: "hit chance modified by target level", 0x9: "Manipulate accuracy", 0xA: "normal accuracy; can crit", 0xB: "normal accuracy"}
    for value in range(0xC0):
        upper, lower = value >> 4, value & 0xF
        if upper in (6, 7): formula = _SPECIAL_FORMULAS.get(lower)
        elif upper == 0xA: formula = _MULTIPLIER_FORMULAS.get(lower)
        else: formula = _NORMAL_FORMULAS.get(lower)
        if formula:
            damage = "magical" if upper in (2,4,5,7,8,9) else "physical"
            result.append((value, f"{formula} — {damage}; {accuracy[upper]}"))
    result.append((0xFF, "No damage calculation"))
    return tuple(result)

DAMAGE_FORMULAS = damage_formula_choices()
LOOT_RATES = tuple((rate, f"Drop — {rate}/63 ({rate * 100 / 63:.1f}%)") for rate in range(64)) + tuple(
    (0x80 + rate, f"Steal — {rate}/63 ({rate * 100 / 63:.1f}%)") for rate in range(1, 64)
)


def _field(**kwargs):
    return kwargs


def reference(category, *, label=None, empty=None, help=None, value_key="id", scope=None):
    data = {"dataType": "reference", "referenceCategory": category, "referenceValueKey": value_key}
    if label is not None: data["label"] = label
    if empty is not None: data["emptyValue"] = empty
    if help: data["help"] = help
    if scope: data["referenceScope"] = scope
    return data


def advanced(label, help):
    return {"label": label, "group": "Advanced / engine data", "help": help, "advanced": True}


CORE = {
    "initialState": {
        "party1": reference("characters", label="Party member 1", empty=255, help="First character placed in the party when a new save is initialized."),
        "party2": reference("characters", label="Party member 2", empty=255, help="Second character placed in the party when a new save is initialized."),
        "party3": reference("characters", label="Party member 3", empty=255, help="Third character placed in the party when a new save is initialized."),
        "gil": _field(label="Starting gil", group="Starting resources", help="Gil copied into a newly initialized save. Existing saves are not changed."),
    },
    "initialInventory": {
        "item": _field(label="Item / equipment", dataType="inventoryReference", emptyValue=0x1FF, includeMateria=False, group="Starting inventory", help="Item or equipment stored in this new-game inventory slot. 511 means empty."),
        "amount": _field(label="Quantity", group="Starting inventory", help="Initial quantity in this packed inventory slot (0–127)."),
    },
    "initialMateria": {
        "materia": reference("materia", label="Materia", empty=255, help="Materia stored in this initial stock slot; 255 means empty."),
        "ap": _field(label="AP", group="Starting Materia", help="AP already accumulated on this initial Materia instance."),
    },
    "stolenMateria": {
        "materia": reference("materia", label="Materia", empty=255, help="Materia in Yuffie's temporary stolen-Materia inventory for the Wutai sequence."),
        "ap": _field(label="AP", group="Stolen Materia", help="AP retained on this temporary stolen-Materia instance."),
    },
    "magicOrder": {
        "menuGroup": _field(label="Magic-menu section", dataType="enum", choices=choices(*MAGIC_MENU_GROUPS), group="Menu placement", help="Which Magic submenu section contains this player spell: Restore, Attack, Indirect or Special. Not listed stores 0xFF."),
        "position": _field(label="Position within section", group="Menu placement", help="Zero-based position inside the selected Magic submenu section."),
    },
    "growthCurves": {
        **{f"gradient{i}": _field(label="Gradient", group=f"Levels {bracket}", help="Slope/coefficient used by this level bracket's growth formula.") for i, bracket in enumerate(("2–11","12–21","22–31","32–41","42–51","52–61","62–81","82–99"))},
        **{f"base{i}": _field(label="Base", group=f"Levels {bracket}", help="Base/intercept used by this level bracket. Experience curves store this byte but do not use it in the EXP formula.") for i, bracket in enumerate(("2–11","12–21","22–31","32–41","42–51","52–61","62–81","82–99"))},
    },
    "growthBonuses": {
        **{f"bonus{i}": _field(label=f"Difference bracket {i}", group="Randomized level gain", help="Result/factor selected when the growth calculation lands in difference bracket %d." % i) for i in range(12)},
    },
    "commands": {
        "initialCursorAction": _field(label="Command action", dataType="enum", choices=choices(*COMMAND_ACTIONS), group="Command behavior", help="What selecting this battle command does first: perform the command directly, open a submenu such as Magic/Item/Limit, or enter target selection."),
        "targetData": _field(label="Targeting", dataType="flags", flags=flags(*TARGET_FLAGS), group="Targeting", help="Who a directly executed command can target and how the battle cursor behaves."),
        "cameraMovementIdSingle": advanced("Single-target camera ID", "Raw battle-camera program ID for single-target use."),
        "cameraMovementIdMulti": advanced("Multi-target camera ID", "Raw battle-camera program ID for multi-target use."),
    },
    "playerAttacks": {
        "targetData": _field(label="Targeting", dataType="flags", flags=flags(*TARGET_FLAGS), group="Targeting", help="Who this player attack/spell can target and how its battle cursor behaves."),
        "damageCalculationId": _field(label="Damage / healing formula", dataType="enum", choices=choices(*DAMAGE_FORMULAS), group="Damage", help="Formula, damage type, accuracy behavior and critical capability encoded in the calculation byte."),
        "conditionSubmenu": _field(label="Condition submenu", dataType="enum", choices=choices(*ATTACK_CONDITIONS), group="Status / condition", help="Conditional submenu mode used by the attack."),
        "statusChange": _field(label="Status change", dataType="statusChange", group="Status / condition", help="Inflict/cure/swap mode and chance encoded in one byte."),
        "additionalEffects": _field(label="Additional behavior", dataType="enum", choices=choices(*ADDITIONAL_EFFECTS), group="Extra behavior", help="Hard-coded behavior beyond ordinary damage/status processing."),
        "additionalEffectsModifier": _field(label="Additional-behavior modifier", group="Extra behavior", help="Parameter used by additional behaviors that require one."),
        "statusFlags": _field(label="Statuses affected", dataType="flags", flags=flags(*STATUSES), group="Status / condition", help="Statuses affected according to Status change."),
        "elementFlags": _field(label="Elements", dataType="flags", flags=flags(*ELEMENTS), group="Damage", help="Elemental tags carried by this attack."),
        "specialAttackFlags": _field(label="Special attack properties", dataType="flags", flags=flags(*SPECIAL_ATTACK_FLAGS), invertBits=True, bitWidth=16, group="Extra behavior", help="Named special properties. KERNEL.BIN stores these bits inverted; the editor presents their logical meaning."),
        "accuracyRate": _field(label="Accuracy", group="Damage", help="Base accuracy parameter used by formulas that perform an accuracy check."),
        "mpCost": _field(label="MP cost", group="Cost", help="MP consumed when this attack is used normally."),
        "attackPower": _field(label="Power", group="Damage", help="Base power consumed by the selected damage/healing formula."),
        "impactEffectId": advanced("Impact effect ID", "Raw impact visual-effect ID."),
        "targetHurtActionIndex": advanced("Target hurt action ID", "Raw target reaction/animation index."),
        "impactSound": advanced("Impact sound ID", "Raw battle sound-effect ID."),
        "cameraMovementIdSingle": advanced("Single-target camera ID", "Raw battle-camera program ID for single-target use."),
        "cameraMovementIdMulti": advanced("Multi-target camera ID", "Raw battle-camera program ID for multi-target use."),
        "attackEffectId": advanced("Attack visual effect ID", "Raw attack-effect program ID."),
    },
    "items": {
        "targetData": _field(label="Targeting", dataType="flags", flags=flags(*TARGET_FLAGS), group="Targeting", help="Who this item can target and how the battle cursor behaves."),
        "damageCalculationId": _field(label="Damage / healing formula", dataType="enum", choices=choices(*DAMAGE_FORMULAS), group="Effect", help="The battle formula and accuracy mode used by the item. The raw byte combines formula, physical/magical mode, accuracy and critical-hit behavior."),
        "conditionSubmenu": _field(label="Condition submenu", dataType="enum", choices=choices(*ATTACK_CONDITIONS), group="Effect", help="Which conditional submenu the battle UI uses: HP, MP, Status, or none."),
        "statusChange": _field(label="Status change", dataType="statusChange", group="Status", help="Whether this item inflicts, cures or swaps the selected status set, plus its encoded chance/amount."),
        "additionalEffects": _field(label="Additional behavior", dataType="enum", choices=choices(*ADDITIONAL_EFFECTS), group="Effect", help="Extra hard-coded battle behavior beyond the normal damage/status calculation."),
        "additionalEffectsModifier": _field(label="Additional-behavior modifier", group="Effect", help="Parameter consumed only by additional behaviors that require one; otherwise ignored."),
        "statusFlags": _field(label="Statuses affected", dataType="flags", flags=flags(*STATUSES), group="Status", help="Named statuses this item can inflict/cure/swap according to Status change."),
        "elementFlags": _field(label="Elements", dataType="flags", flags=flags(*ELEMENTS), group="Effect", help="Elemental tags used by the battle engine."),
        "restrictions": _field(label="Availability / permissions", dataType="flags", flags=flags(*RESTRICTION_FLAGS), invertBits=True, bitWidth=16, group="Availability", help="Where this item is allowed to be sold or used. KERNEL.BIN stores these permission bits inverted."),
        "specialAttackFlags": _field(label="Special attack properties", dataType="flags", flags=flags(*SPECIAL_ATTACK_FLAGS), invertBits=True, bitWidth=16, group="Effect", help="Special battle properties such as reflection, defense bypass or MP damage. KERNEL.BIN stores these bits inverted."),
        "cameraMovementId": advanced("Camera movement ID", "Raw battle-camera program ID. No stable semantic name table is exposed by this plugin yet."),
        "attackEffectId": advanced("Visual attack effect ID", "Raw visual-effect program ID. Kept in Advanced because the current plugin has no authoritative effect-name table."),
    },
    "weapons": {
        "targetData": _field(label="Targeting", dataType="flags", flags=flags(*TARGET_FLAGS), group="Combat", help="Who the basic weapon attack can target and how the cursor behaves."),
        "damageCalculationId": _field(label="Damage formula", dataType="enum", choices=choices(*DAMAGE_FORMULAS), group="Combat", help="Formula/accuracy byte used for this weapon's basic attack."),
        "status": _field(label="Granted status", dataType="enum", choices=choices(*STATUS_INDEX), group="Equipped effects", help="Single status granted by the equipment, or None."),
        "growthRate": _field(label="Materia AP growth", dataType="enum", choices=choices(*GROWTH_RATES), group="Materia slots", help="AP growth multiplier for Materia installed in this weapon."),
        "equipableBy": _field(label="Usable by", dataType="flags", flags=flags(*EQUIPABLE), group="Equipment", help="Characters allowed to equip this weapon."),
        "attackElements": _field(label="Attack elements", dataType="flags", flags=flags(*ELEMENTS), group="Combat", help="Elements applied by the weapon's basic attack."),
        "restrictions": _field(label="Availability / permissions", dataType="flags", flags=flags(*RESTRICTION_FLAGS), invertBits=True, bitWidth=16, group="Availability", help="Whether this weapon may be sold, used in battle/menu contexts, or thrown. KERNEL.BIN stores these permission bits inverted."),
        "weaponModelId": advanced("Weapon model ID", "Raw model index used by the battle renderer; no authoritative model-name table is currently exposed."),
        "highSoundIdMask": advanced("Sound ID high-bit mask", "Raw high-bit selector used with this weapon's hit/miss sound IDs."),
        "normalHitSoundId": advanced("Normal hit sound ID", "Raw sound-effect selector for a normal weapon hit."),
        "criticalHitSoundId": advanced("Critical hit sound ID", "Raw sound-effect selector for a critical weapon hit."),
        "missedAttackSoundId": advanced("Miss sound ID", "Raw sound-effect selector for a missed weapon attack."),
        "impactEffectId": advanced("Impact effect ID", "Raw impact visual-effect selector for this weapon."),
        **{f"boostedStat{i}": _field(label=f"Stat bonus {i}", dataType="enum", choices=choices(*CHARACTER_STATS), group="Stat bonuses", help=f"Character stat modified by equipment bonus slot {i}.") for i in range(1,5)},
        **{f"boostedStat{i}Bonus": _field(label=f"Stat bonus {i} amount", group="Stat bonuses", help=f"Amount added to equipment stat bonus slot {i}.") for i in range(1,5)},
        **{f"materiaSlot{i}": _field(label=f"Materia slot {i}", dataType="enum", choices=choices(*MATERIA_SLOTS), group="Materia slots", help="Whether this position exists, links to its neighbor, and supports AP growth.") for i in range(1,9)},
    },
    "armor": {
        "elementDamageModifier": _field(label="Elemental response", dataType="enum", choices=choices(*DAMAGE_MODIFIERS), group="Elemental defense", help="How the selected elemental-defense bits are treated: absorb, nullify, halve, or normal."),
        "status": _field(label="Granted status", dataType="enum", choices=choices(*STATUS_INDEX), group="Equipped effects", help="Single status granted by the armor, or None."),
        "growthRate": _field(label="Materia AP growth", dataType="enum", choices=choices(*GROWTH_RATES), group="Materia slots", help="AP growth multiplier for Materia installed in this armor."),
        "equipableBy": _field(label="Usable by", dataType="flags", flags=flags(*EQUIPABLE), group="Equipment", help="Characters allowed to equip this armor."),
        "elementalDefense": _field(label="Affected elements", dataType="flags", flags=flags(*ELEMENTS), group="Elemental defense", help="Elements affected by Elemental response."),
        "restrictions": _field(label="Availability / permissions", dataType="flags", flags=flags(*RESTRICTION_FLAGS), invertBits=True, bitWidth=16, group="Availability", help="Whether this armor may be sold, used in battle/menu contexts, or thrown. KERNEL.BIN stores these permission bits inverted."),
        **{f"boostedStat{i}": _field(label=f"Stat bonus {i}", dataType="enum", choices=choices(*CHARACTER_STATS), group="Stat bonuses", help=f"Character stat modified by equipment bonus slot {i}.") for i in range(1,5)},
        **{f"boostedStat{i}Bonus": _field(label=f"Stat bonus {i} amount", group="Stat bonuses", help=f"Amount added to equipment stat bonus slot {i}.") for i in range(1,5)},
        **{f"materiaSlot{i}": _field(label=f"Materia slot {i}", dataType="enum", choices=choices(*MATERIA_SLOTS), group="Materia slots", help="Whether this position exists, links to its neighbor, and supports AP growth.") for i in range(1,9)},
    },
    "accessories": {
        "boostedStat1": _field(label="Stat bonus 1", dataType="enum", choices=choices(*CHARACTER_STATS), group="Stat bonuses", help="First character stat modified by the accessory."),
        "boostedStat2": _field(label="Stat bonus 2", dataType="enum", choices=choices(*CHARACTER_STATS), group="Stat bonuses", help="Second character stat modified by the accessory."),
        "boostedStat1Bonus": _field(label="Stat bonus 1 amount", group="Stat bonuses", help="Amount added to Stat bonus 1."),
        "boostedStat2Bonus": _field(label="Stat bonus 2 amount", group="Stat bonuses", help="Amount added to Stat bonus 2."),
        "elementDamageModifier": _field(label="Elemental response", dataType="enum", choices=choices(*DAMAGE_MODIFIERS), group="Elemental defense", help="How the selected elements are treated: absorb, nullify, halve, or normal."),
        "specialEffect": _field(label="Automatic / special effect", dataType="enum", choices=choices(*ACCESSORY_EFFECTS), group="Equipped effects", help="Hard-coded accessory behavior such as Auto-Haste, Auto-Reflect or increased Steal rate."),
        "elementalDefense": _field(label="Affected elements", dataType="flags", flags=flags(*ELEMENTS), group="Elemental defense", help="Elements affected by Elemental response."),
        "statusDefense": _field(label="Protected statuses", dataType="flags", flags=flags(*STATUSES), group="Status defense", help="Statuses this accessory protects against."),
        "equipableBy": _field(label="Usable by", dataType="flags", flags=flags(*EQUIPABLE), group="Equipment", help="Characters allowed to equip this accessory."),
        "restrictions": _field(label="Availability / permissions", dataType="flags", flags=flags(*RESTRICTION_FLAGS), invertBits=True, bitWidth=16, group="Availability", help="Whether this accessory may be sold, used in battle/menu contexts, or thrown. KERNEL.BIN stores these permission bits inverted."),
    },
}

CHARACTERS = {
    "storedId": _field(label="Character identity", dataType="enum", choices=choices((0,"Cloud"),(1,"Barret"),(2,"Tifa"),(3,"Aerith"),(4,"Red XIII"),(5,"Yuffie"),(6,"Cait Sith / Young Cloud slot"),(7,"Vincent / Sephiroth slot"),(8,"Cid")), group="Identity", help="Stored character ID. This does not change which initialization slot is being edited."),
    "limitLevel": _field(label="Starting Limit level", group="Starting Limit", help="Limit level selected when a new game/character initialization uses this record."),
    "limitBar": _field(label="Starting Limit gauge", group="Starting Limit", help="Raw 0–255 Limit gauge fill used at initialization."),
    "weaponId": reference("weapons", label="Starting weapon", help="Weapon equipped when this initialization record is used."),
    "armorId": reference("armor", label="Starting armor", help="Armor equipped when this initialization record is used."),
    "accessoryId": reference("accessories", label="Starting accessory", empty=255, help="Accessory equipped when this initialization record is used; 255 means none."),
    "characterFlags": _field(label="Starting battle mood", dataType="flags", flags=flags(*CHARACTER_FLAGS), group="Starting status", help="Initial Sadness/Fury flags."),
    "rowByte": _field(label="Starting row", dataType="enum", choices=choices((0xFF,"Front row"),(0xFE,"Back row")), group="Starting status", help="Initial battle row. FF7 stores back row as 0xFE."),
    "learnedLimits": _field(label="Limits already learned", dataType="flags", flags=flags(*LEARNED_LIMITS), group="Starting Limit", help="Limit Breaks marked learned in the initialization record."),
    "recruitOffsetRaw": _field(label="Recruitment level adjustment", dataType="scaled", displayScale=0.5, group="Recruitment", help="Level adjustment relative to Cloud when this growth record is recruited. Stored in half-level units."),
}
for equipment in ("weapon", "armor"):
    for slot in range(8):
        CHARACTERS[f"{equipment}Materia{slot}"] = reference("materia", label=f"{equipment.title()} Materia slot {slot+1}", empty=255, help="Materia installed in this starting equipment slot; 255 means empty.")
        CHARACTERS[f"{equipment}MateriaAp{slot}"] = _field(label=f"{equipment.title()} Materia slot {slot+1} AP", group="Starting Materia", help="AP already accumulated on this starting Materia instance.")
for stat in ("strength","vitality","magic","spirit","dexterity","luck","hp","mp","experience"):
    CHARACTERS[f"{stat}Curve"] = reference("growthCurves", label=f"{stat.title()} growth curve", help="Growth curve used for this stat.")

SCENE = {
    "enemies": {
        "morph": _field(label="Morph reward", dataType="inventoryReference", emptyValue=65535, group="Rewards", help="Global item/equipment rewarded by Morph; 65535 means none."),
        "backMultiplier": _field(label="Back-attack damage multiplier", dataType="scaled", displayScale=0.125, group="Stats / rewards", help="Damage multiplier when this enemy is struck from behind. The stored byte is measured in eighths."),
        "statusImmunity": _field(label="Status immunities", dataType="flags", flags=flags(*STATUSES), invertBits=True, bitWidth=32, group="Defenses", help="Statuses this enemy cannot normally receive. scene.bin stores this mask inverted; Lexeditor shows the logical immunities."),
        **{f"element{i}": _field(label=f"Resistance slot {i+1} target", dataType="enum", choices=choices(
            *(([(value, label) for value, label in ((0,"Fire"),(1,"Ice"),(2,"Lightning"),(3,"Earth"),(4,"Poison"),(5,"Gravity"),(6,"Water"),(7,"Wind"),(8,"Holy"),(9,"Restorative"),(10,"Cut"),(11,"Hit"),(12,"Punch"),(13,"Shoot"),(14,"Shout"),(15,"Hidden"))] +
              [(0x20 + value, label + " (status)") for value, label in STATUS_INDEX if value != 0xFF] + [(0xFF,"None")]))), group="Resistances", help="Element or status affected by this resistance slot. Status IDs are stored with FF7's 0x20 offset." ) for i in range(8)},
        **{f"rate{i}": _field(label=f"Resistance slot {i+1} response", dataType="enum", choices=choices((0,"Killed by"),(1,"Cannot miss"),(2,"Double damage"),(4,"Half damage"),(5,"Nullify"),(6,"Absorb"),(7,"Full cure"),(0xFF,"None")), group="Resistances", help="How this enemy reacts to the element/status in the matching resistance slot.") for i in range(8)},
        **{f"attack{i}": reference("enemyAttacks", label=f"Action {i+1} attack", empty=65535, help="Scene-local enemy attack used by this action slot.", value_key="gameId", scope="scene") for i in range(16)},
        **{f"manipulate{i}": reference("enemyAttacks", label=f"Manipulate / Berserk action {i+1}", empty=65535, help="Scene-local attack available to Manipulate/Berserk logic.", value_key="gameId", scope="scene") for i in range(3)},
        **{f"item{i}": _field(label=f"Loot slot {i+1}", dataType="inventoryReference", emptyValue=65535, group="Loot", help="Global item/equipment referenced by this drop/steal slot.") for i in range(4)},
        **{f"dropRate{i}": _field(label=f"Loot slot {i+1} method / chance", dataType="enum", choices=choices(*LOOT_RATES), group="Loot", help="Canonical FF7 loot rates are 0–63 for drops and 0x81–0xBF for steals. Existing noncanonical raw bytes are preserved unless edited.") for i in range(4)},
        **{f"animation{i}": advanced(f"Action {i+1} animation ID", "Raw enemy action-animation index; no authoritative human animation-name table is available.") for i in range(16)},
        **{f"camera{i}": advanced(f"Action {i+1} camera ID", "Raw battle-camera program ID; no authoritative human camera-name table is available.") for i in range(16)},
    },
    "enemyAttacks": {
        "target": _field(label="Targeting", dataType="flags", flags=flags(*TARGET_FLAGS), group="Targeting", help="Who this attack can target and how its battle cursor/selection behaves."),
        "formula": _field(label="Damage / healing formula", dataType="enum", choices=choices(*DAMAGE_FORMULAS), group="Damage", help="Formula, damage type, accuracy behavior and critical capability encoded in the calculation byte."),
        "condition": _field(label="Condition submenu", dataType="enum", choices=choices(*ATTACK_CONDITIONS), group="Status / condition", help="Conditional submenu mode used by the attack."),
        "statusChance": _field(label="Status change", dataType="statusChange", group="Status / condition", help="Inflict/cure/swap mode and chance encoded in one byte."),
        "additionalEffect": _field(label="Additional behavior", dataType="enum", choices=choices(*ADDITIONAL_EFFECTS), group="Extra behavior", help="Hard-coded behavior beyond ordinary damage/status processing."),
        "modifier": _field(label="Additional-behavior modifier", group="Extra behavior", help="Parameter used by additional behaviors that require one."),
        "statuses": _field(label="Statuses affected", dataType="flags", flags=flags(*STATUSES), group="Status / condition", help="Statuses affected according to Status change."),
        "elements": _field(label="Elements", dataType="flags", flags=flags(*ELEMENTS), group="Damage", help="Elemental tags carried by this attack."),
        "specialFlags": _field(label="Special attack properties", dataType="flags", flags=flags(*SPECIAL_ATTACK_FLAGS), invertBits=True, bitWidth=16, group="Extra behavior", help="Named special properties. scene.bin stores these bits inverted; the editor presents their logical meaning."),
        "singleCamera": advanced("Single-target camera ID", "Raw battle camera program ID; no authoritative camera-name table is available here."),
        "multiCamera": advanced("Multi-target camera ID", "Raw battle camera program ID; no authoritative camera-name table is available here."),
        "impact": advanced("Impact effect ID", "Raw impact visual-effect ID."),
        "targetAnimation": advanced("Target hurt animation ID", "Raw target animation/action index."),
        "effect": advanced("Attack visual effect ID", "Raw attack-effect program ID."),
        "impactSound": advanced("Impact sound ID", "Raw battle sound effect ID."),
    },
    "encounters": {
        "nextBattle": reference("encounters", label="Next battle", empty=65535, help="Battle loaded immediately after this one; 65535 means none."),
        **{f"slot{i}_enemy": reference("enemies", label=f"Enemy slot {i+1}", empty=65535, help="Enemy occupying this formation slot; 65535 means empty.", value_key="gameId", scope="scene") for i in range(6)},
        **{f"slot{i}_row": _field(label=f"Enemy slot {i+1} row", dataType="enum", choices=choices((0,"Front row"),(1,"Back row")), group=f"Enemy slot {i+1}", help="Battle row for this enemy slot.") for i in range(6)},
        "flags": advanced("Battle setup flags", "Packed battle-setup flags. Kept in Advanced until every bit has an authoritative name."),
        "layout": advanced("Battle layout code", "Formation layout code. Kept in Advanced instead of presenting an unexplained byte as a normal setting."),
        "location": advanced("Battle arena ID", "Battle arena/location ID. A human arena-name table is not yet available to this plugin."),
    },
}

SHOP = {
    "type": _field(label="Shop type", dataType="enum", choices=choices(*SHOP_TYPES), group="Shop", help="Menu behavior used by this shop."),
    "count": _field(label="Active inventory slots", group="Shop", help="How many of the ten inventory slots the shop actually exposes."),
}
for i in range(10):
    SHOP[f"type{i}"] = _field(label=f"Slot {i+1} kind", dataType="enum", choices=choices(*SHOP_SLOT_KINDS), group=f"Inventory slot {i+1}", help="Whether this slot references the global item/equipment table or Materia table.")
    SHOP[f"item{i}"] = _field(label=f"Slot {i+1} product", dataType="shopReference", kindField=f"type{i}", group=f"Inventory slot {i+1}", help="Human-readable product selected from the table chosen by Slot kind.")

ENCOUNTERS = {
    "enabled": _field(label="Random encounters", dataType="boolean", group="Encounter settings", help="Whether this table generates random encounters."),
    "rate": _field(label="Encounter rate", group="Encounter settings", help="FF7's raw encounter-rate parameter; lower nonzero values produce more frequent encounters."),
}
for i in range(14):
    ENCOUNTERS[f"battle{i}"] = reference("encounters", label=None, help="Battle/formation selected by this weighted encounter entry.")
    ENCOUNTERS[f"chance{i}"] = _field(help="Relative weight out of 64 for this encounter entry.")

SPECIAL = {
    "yuffieEncounters": {"battle": reference("encounters", label="Battle", help="Battle used once Cloud meets this level threshold.")},
    "chocoboRatings": {
        "battle": reference("encounters", label="Battle", help="Battle associated with this Chocobo encounter mapping."),
        "rating": _field(label="Chocobo quality", dataType="enum", choices=choices(*CHOCOBO_RATINGS), help="Human quality label for FF7's 1–8 Chocobo rating."),
    },
}


def metadata_for(category: str, key: str) -> dict:
    if category == 'limitBreaks' and key in CORE['playerAttacks']: return dict(CORE['playerAttacks'][key])
    if category in CORE and key in CORE[category]: return dict(CORE[category][key])
    if category in SCENE and key in SCENE[category]: return dict(SCENE[category][key])
    if category in ("characters", "recruits") and key in CHARACTERS: return dict(CHARACTERS[key])
    if category == "shops" and key in SHOP: return dict(SHOP[key])
    if category in ("fieldEncounters", "worldEncounters") and key in ENCOUNTERS: return dict(ENCOUNTERS[key])
    if category in SPECIAL and key in SPECIAL[category]: return dict(SPECIAL[category][key])
    return {}


DEFAULT_GROUPS = {
    "commands": "Command behavior", "playerAttacks": "Attack",
    "items": "Effect", "weapons": "Combat", "armor": "Defense", "accessories": "Equipment",
    "characters": "Starting stats", "recruits": "Starting data", "enemies": "Stats / rewards",
    "enemyAttacks": "Attack", "encounters": "Battle setup", "shops": "Shop",
    "prices": "Price", "limitBreaks": "Attack", "materiaEquipEffects": "Stat changes",
    "itemSortOrder": "Menu ordering", "materiaPriority": "Menu ordering", "audioMixing": "Audio mixing",
    "apMultiplier": "Economy", "fieldEncounters": "Encounter settings", "worldEncounters": "Encounter settings",
}
RAW_HINTS = (" id", " flags", " mask", " byte", "camera", "animation", "layout", "arena", "cover flags")


def apply(category: str, fields_in):
    """Return JSON metadata copies with human-facing overrides applied."""
    result = []
    for field in fields_in:
        value = dict(field) if isinstance(field, dict) else {
            "key": field.key, "label": field.label, "dataType": "int",
            "minimum": field.minimum, "maximum": field.maximum, "step": field.scale,
        }
        authored = metadata_for(category, value["key"])
        value.update(authored)
        label = str(value.get("label") or value["key"])
        if not authored and any(hint in label.casefold() for hint in RAW_HINTS):
            value.update(advanced(label, "Engine/storage identifier retained for advanced editing because no authoritative human name mapping is available yet."))
        value.setdefault("group", DEFAULT_GROUPS.get(category, "Data"))
        result.append(value)
    return result

# Scalar fields that are genuinely numeric but still need domain language.
for key, label, help_text in (
    ("attackPower", "Power", "Base power consumed by the selected item formula."),
    ("attackStrength", "Attack power", "Base power used by this weapon's damage formula."),
    ("criticalRate", "Critical rate", "Weapon critical-hit rate parameter."),
    ("accuracyRate", "Accuracy", "Weapon accuracy rate parameter."),
):
    target = CORE["items"] if key == "attackPower" else CORE["weapons"]
    target[key] = _field(label=label, group="Effect" if key == "attackPower" else "Combat", help=help_text)
for key, label in (("defense","Defense"),("magicDefense","Magic defense"),("evade","Evade"),("magicEvade","Magic evade")):
    CORE["armor"][key] = _field(label=label, group="Defense", help=f"Armor {label.casefold()} value.")
for key in ("dialogue",):
    SHOP[key] = advanced("Dialogue set", "Raw shop dialogue/menu text set index; no authoritative named dialogue table is exposed by this plugin.")
for i in range(4):
    SCENE["encounters"][f"arena{i}"] = advanced(f"Arena candidate {i+1} ID", "Raw battle arena candidate ID; no authoritative arena-name table is available here.")
for camera in range(3):
    for axis in ("x","y","z","directionX","directionY","directionZ"):
        SCENE["encounters"][f"camera{camera}_{axis}"] = _field(label=f"Camera {camera+1} {axis}", group="Advanced / engine data", help="Raw formation camera coordinate/direction value.", advanced=True)
for slot in range(6):
    for suffix, label in (("cover","Cover flags"),("flags","Initial condition flags")):
        SCENE["encounters"][f"slot{slot}_{suffix}"] = advanced(f"Enemy slot {slot+1} {label}", "Packed formation-engine flags; retained under Advanced until every bit is authoritatively named.")
for level in ("11","12","21","22","31","32","4"):
    CHARACTERS[f"limitAttack{level}"] = reference("limitBreaks", label=f"Limit {level} attack", value_key="gameId", help="Executable Limit Break attack record used by this slot; stored Limit attack IDs begin at 128.")
CHARACTERS["levelProgress"] = _field(label="Starting level progress", group="Starting progression", help="Progress within the current level at initialization (0–255 gauge).")
for i in range(1,5):
    CHARACTERS[f"limitHpDivisor{i}"] = _field(label=f"Limit level {i} HP divisor", group="Limit gain", help="HP-loss divisor used by FF7's Limit gauge gain calculation for this Limit level.")
