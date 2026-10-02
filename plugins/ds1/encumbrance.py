"""Editable native encumbrance fields, expressed in player-facing units."""
from . import stamina_patch as native

DEFAULTS = {key: value for key, value in native.DEFAULT_RULES.items() if key != "baseRecovery"}
NAMES = ("Ultralight", "Light", "Medium", "Heavy", "Overloaded")
HELP = (
    "Edit each movement class's load range and stamina recovery. Enable Encumbrance rules in Tweaks, then save and Apply. "
    "Ultralight requires the game's special movement effect and shares the Light limit. "
    "These controls do not edit animation timing, invincibility frames or other load-dependent formulas."
)
RECOVERY_HELP = (
    "Multiplies base recovery plus active effect bonuses. 100% keeps the full amount. "
    "Armour penalties and other recovery conditions still apply."
)
LIMIT_HELP = (
    "The highest equipment load percentage in this class, including the boundary. "
    "Limits must increase from Light through Heavy. "
    "Changing limits also adjusts the game's within-class movement interpolation."
)


def number(key, label, value, minimum, maximum, help_text="", editable=True, group="Rules"):
    return {"key": key, "label": label, "value": value, "minimum": minimum, "maximum": maximum,
            "dtype": "f32", "type": "number", "enum": {}, "description": help_text,
            "editable": editable, "group": group, "step": 0.01}


def row(tier, config, *, read_only=False):
    if type(tier) is not int or not 0 <= tier < len(NAMES):
        raise ValueError("Unknown encumbrance class")
    lower = (0, 0, config["lightLimit"], config["mediumLimit"], config["heavyLimit"])[tier]
    upper = (config["lightLimit"], config["lightLimit"], config["mediumLimit"],
             config["heavyLimit"], "No upper limit")[tier]
    limit_key = ("lightLimit", "lightLimit", "mediumLimit", "heavyLimit", None)[tier]
    rate_key = native.RECOVERY_KEYS[tier]
    active = config["encumbranceEnabled"]
    fields = [
        number("lower", "Load above (%)" if tier > 1 else "Minimum load (%)",
               lower, 0, 1000, "Derived from the previous class's upper limit." if tier > 1
               else "This class starts at zero equipment load.", editable=False),
        number(limit_key or "upper", "Load up to (%)", upper, 0.01, 1000, LIMIT_HELP,
               editable=tier in (1, 2, 3)),
        number(rate_key, "Stamina recovery (%)", config[rate_key], 0, 1000, RECOVERY_HELP),
    ]
    # Timing and invincibility do not live in this table. Do not invent editable numbers.
    fields.append({"key": "movement", "label": "Native movement class", "value": NAMES[tier],
                   "description": "The game supplies this class's animations. Their timing is not edited here.",
                   "editable": False, "type": "text", "dtype": "", "minimum": None, "maximum": None,
                   "enum": {}, "group": "Rules"})
    for field in fields:
        field["disabled"] = read_only or not active
        if not field["editable"]:
            field["protectedReason"] = field["description"]
    return {"table": "NativeRules", "id": 10 + tier, "name": NAMES[tier], "fields": fields,
            "help": HELP}
