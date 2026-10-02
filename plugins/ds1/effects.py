"""Special-effect presentation and references; binary codecs live in formats.py."""
from __future__ import annotations

import re

TABLE = "SpEffectParam"
SUBTABS = (
    ("effects-all", "All effects", TABLE),
    ("effects-equipment", "Equipment", TABLE),
    ("effects-spells", "Spells", TABLE),
    ("effects-items", "Items", TABLE),
)
RECOVERY_KEY = "staminaRecoverChangeSpeed"
RECOVERY_HELP = (
    "Adds to stamina recovery while this effect is active. Negative values slow recovery. "
    "This is a modifier, not the final recovery rate or a percentage."
)
# The upstream annotation contradicts its PARAMDEF for target routing, and
# describes several matchmaking flags only as probable. Do not guess.
PROTECTED = {
    "effectTargetAttacker": "Published sources disagree about which target receives this effect.",
    **{key: "The published description of this network action is unconfirmed."
       for key in ("requestSOS", "requestBlackSOS", "requestForceJoinBlackSOS",
                   "requestKickSession", "requestLeaveSession")},
    **{f"vowType{i}": "No supported covenant is identified for this flag." for i in range(10, 16)},
}
OVERRIDES = {
    RECOVERY_KEY: ("Recovery adjustment (stamina/second)", RECOVERY_HELP),
    "effectEndurance": ("Duration (seconds)", "How long the effect lasts. -1 means permanent. 0 applies it once."),
    "motionInterval": ("Trigger interval (seconds)", "Time between repeated applications. 0 applies the effect every frame."),
    "conditionHp": ("Maximum HP to activate (%)", "Activates when remaining HP is below this percentage. -1 removes the HP condition."),
    "maxHpRate": ("Maximum HP multiplier", "Multiplies maximum HP. 1 is unchanged. 0.5 halves it. The current-HP setting controls whether current HP changes too."),
    "maxStaminaRate": ("Maximum stamina multiplier", "Multiplies maximum stamina. 1 is unchanged. 0.5 halves it."),
    "changeStaminaRate": ("Stamina damage (%)", "Removes this percentage of maximum stamina each application. Negative values restore stamina."),
    "changeStaminaPoint": ("Stamina damage (points)", "Removes this much stamina each application. Negative values restore stamina."),
    "changeHpRate": ("HP damage (%)", "Removes this percentage of maximum HP each application. Negative values heal."),
    "changeHpPoint": ("HP damage (points)", "Removes this much HP each application. Negative values heal."),
    "insideDurability": ("Durability damage (points)", "Damages equipped weapons and armour. Negative values repair them."),
    "grabityRate": ("Animation speed multiplier", "Multiplies animation speed. 1 is unchanged. 0.5 halves it."),
    "categoryPriority": ("Stacking priority", "Resolves priority within compatible stacking categories. Lower values have higher priority."),
    "spCategory": ("Stacking rule", "Controls how this effect combines with another effect in the same category."),
    "stateInfo": ("Effect behaviour", "Selects the game's built-in effect behaviour. Some properties require a particular behaviour to work."),
    "replaceSpEffectId": ("Effect on expiry", "Adds the selected effect when this effect ends."),
    "cycleOccurrenceSpEffectId": ("Repeated effect", "Adds the selected effect at each trigger interval."),
    "atkOccurrenceSpEffectId": ("Effect on hit", "Adds the selected effect to a victim on a hit. Requires a compatible effect behaviour, such as 152 or 153."),
    "dispIconNonactive": ("Show icon while inactive", "Keeps the icon visible when the activation conditions are not met."),
    "bCurrHPIndependeMaxHP": ("Keep current HP unchanged", "When enabled, changing maximum HP does not change current HP."),
    "maxDurability": ("Extra hits before durability loss", "Adds this many hits before equipment loses durability."),
    "targetPriority": ("Enemy target preference", "Positive values encourage enemies to target the owner. Negative values encourage another target."),
}
GROUPS = (
    "Activation and timing", "HP and stamina", "Damage dealt", "Damage received",
    "Defence and resistances", "Status buildup", "Equipment", "Effect links",
    "Targets", "Immunities", "Movement and perception", "Rewards",
    "Covenants", "Other properties", "Protected properties",
)


def presentation(key, label, description):
    """Return one shared label/help definition for each effect property."""
    label, description = OVERRIDES.get(key, (label, description))
    if key not in OVERRIDES and ("Multiplies" in description or "Multiplier" in description):
        label = label.replace(" %", " multiplier")
        if "1 =" not in description and "1 mean" not in description and "1 is" not in description:
            description = description.rstrip(".") + ". 1 is unchanged."
    if key in PROTECTED:
        group = "Protected properties"
    elif key.startswith("effectTarget"):
        group = "Targets"
        if key not in OVERRIDES and key not in PROTECTED:
            description = ""
    elif key.startswith("vowType"):
        group = "Covenants"
    elif key.startswith(("disable", "corrosionIgnore", "antiMagicIgnore", "noDead", "enableCharm")):
        group = "Immunities"
    elif key.endswith("SpEffectId") or key in ("behaviorId", "stateInfo", "useSpEffectEffect"):
        group = "Effect links"
    elif key.startswith(("condition", "effectEndurance", "motionInterval", "spCategory",
                          "categoryPriority", "saveCategory", "iconId", "dispIcon",
                          "isFireDamage", "isExtend", "enableLifeTime", "lifeReduction", "magicEffectTime")):
        group = "Activation and timing"
    elif key in ("poizonAttackPower", "registIllness", "registBlood", "registCurse"):
        group = "Status buildup"
    elif "Diffence" in key or key.startswith("regist"):
        group = "Defence and resistances"
    elif "DamageCutRate" in key or key in ("NoGuardDamageRate", "vitalSpotChangeRate",
                                         "normalSpotChangeRate", "bloodDamageRate"):
        group = "Damage received"
    elif "Attack" in key or key in ("atkAttribute", "spAttribute", "bAdjustMagicAblity",
                                   "bAdjustFaithAblity", "magParamChange", "miracleParamChange"):
        group = "Damage dealt"
    elif any(word in key.lower() for word in ("hp", "mp", "stamina")):
        group = "HP and stamina"
    elif any(word in key.lower() for word in ("durability", "guard", "flick", "weight", "bowdist", "slot", "superarmor", "wepparam")):
        group = "Equipment"
    elif any(word in key.lower() for word in ("move", "anim", "grabity", "targetpriority", "search", "raycast", "faketarget")):
        group = "Movement and perception"
    elif "soul" in key.lower() or key == "heroPointDamage":
        group = "Rewards"
    else:
        group = "Other properties"
    return label, group, description


def reference_keys(document, table, row_id):
    """Resolve only explicit SpEffectParam references and their discriminators."""
    for item in document.schemas[table]["fields"]:
        field = item["spec"]
        for expression in (field.reference or "").split(","):
            match = re.fullmatch(r"SpEffectParam(?:\((\w+)=(-?\d+)\))?", expression)
            if not match:
                continue
            if match[1] and document.value(table, row_id, match[1]) != int(match[2]):
                continue
            yield field.key
            break


class EffectReferences:
    """A current-archive index, not an inference from vanilla item names."""

    def __init__(self, document):
        self.document = document
        self.incoming = {}
        self.outgoing = {}
        self.choices = {"-1": "None"}
        if TABLE not in document.params:
            return
        for row in document.params[TABLE].rows:
            self.choices[str(row.row_id)] = f"{document.row_name(TABLE, row.row_id)} ({row.row_id})"
        for table, param in document.params.items():
            for row in param.rows:
                links = []
                for key in reference_keys(document, table, row.row_id):
                    target = document.value(table, row.row_id, key)
                    if target == -1:
                        continue
                    resolved = str(target) in self.choices
                    links.append({"id": target, "field": key, "resolved": resolved,
                                  "name": document.row_name(TABLE, target) if resolved else f"Missing effect {target}"})
                    if resolved:
                        self.incoming.setdefault(target, []).append({
                            "table": table, "id": row.row_id, "field": key,
                            "name": document.row_name(table, row.row_id),
                        })
                if links:
                    self.outgoing[table, row.row_id] = links

    def rows(self, tab):
        sources = {
            "effects-equipment": {"EquipParamWeapon", "EquipParamProtector", "EquipParamAccessory"},
            "effects-spells": {"Magic"},
            "effects-items": {"EquipParamGoods"},
        }.get(tab)
        return [{"id": row.row_id, "name": self.document.row_name(TABLE, row.row_id), "table": TABLE}
                for row in self.document.params[TABLE].rows
                if sources is None or any(link["table"] in sources for link in self.incoming.get(row.row_id, []))]
