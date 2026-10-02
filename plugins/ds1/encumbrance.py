"""Shared-control descriptions for variable load bands and effect overrides."""
from . import load_bands as bands

HELP = bands.HELP


def number(key, label, value, minimum, maximum, help_text="", editable=True, group="Rules"):
    return {"key": key, "label": label, "value": value, "minimum": minimum, "maximum": maximum,
            "dtype": "f32", "type": "number", "enum": {}, "description": help_text,
            "editable": editable, "group": group, "step": 0.01}


def finish(fields, config, read_only):
    for field in fields:
        field["disabled"] = read_only or not config["encumbranceEnabled"]
        if not field["editable"]:
            field["protectedReason"] = field["description"]
    return fields


def row(identity, config, *, read_only=False):
    rows = bands.validate_bands(config["bands"])
    index = bands.locate(rows, identity)
    value = rows[index]
    lower = 0.0 if index == 0 else rows[index - 1]["upper"]
    upper = value["upper"]
    fields = [
        {"key": "name", "label": "Name", "value": value["name"], "type": "text",
         "dtype": "text", "editable": True, "description": "",
         "enum": {}, "minimum": None, "maximum": None, "maxLength": bands.MAX_NAME, "group": "Band"},
        number("lower", "Load above (%)" if index else "Minimum load (%)", lower, 0, 1000,
               "Derived from the preceding band's upper limit." if index else
               "The first band begins at zero equipment load.", editable=False, group="Band"),
        number("upper", "Load up to (%)", "No upper limit" if upper is None else upper,
               round(lower + .01, 2),
               round(rows[index + 1]["upper"] - .01, 2)
               if index + 1 < len(rows) and rows[index + 1]["upper"] is not None else bands.MAX_BOUND,
               bands.UPPER_HELP, editable=upper is not None, group="Band"),
        {"key": "movement", "label": "Movement profile", "value": value["movement"],
         "description": bands.MOVEMENT_HELP, "editable": True, "type": "enum", "dtype": "u32",
         "minimum": 1, "maximum": 4, "enum": {str(k): v for k, v in bands.MOVEMENTS.items()},
         "group": "Behaviour"},
        number("recovery", "Stamina recovery (%)", value["recovery"], 0, 1000,
               bands.RECOVERY_HELP, group="Behaviour"),
    ]
    split_min = round(lower + .01, 2)
    split_max = bands.MAX_BOUND if upper is None else round(upper - .01, 2)
    neighbours = [
        {"id": 1000 + rows[i]["id"], "name": rows[i]["name"],
         "lower": 0.0 if i == 0 else rows[i - 1]["upper"], "upper": rows[i]["upper"],
         "movement": bands.MOVEMENTS[rows[i]["movement"]], "recovery": rows[i]["recovery"]}
        for i in (index - 1, index + 1) if 0 <= i < len(rows)
    ]
    return {"table": "NativeRules", "id": 1000 + identity, "name": value["name"],
            "fields": finish(fields, config, read_only), "help": HELP,
            "band": {"index": index, "lower": lower, "upper": upper,
                     "movement": bands.MOVEMENTS[value["movement"]], "recovery": value["recovery"],
                     "splitMinimum": split_min, "splitMaximum": split_max,
                     "canAdd": len(rows) < bands.MAX_BANDS and split_min <= split_max,
                     "canDelete": len(rows) > 1, "neighbours": neighbours}}


def overrides(config, *, read_only=False):
    fields = [
        {"key": "specialEnabled", "label": "Allow special-light override",
         "value": config["specialLight"]["enabled"], "description": bands.SPECIAL_HELP,
         "editable": True, "type": "bool", "dtype": "bool", "minimum": 0, "maximum": 1,
         "enum": {}, "group": "Special light"},
        number("specialRecovery", "Special-light recovery (%)", config["specialLight"]["recovery"],
               0, 1000, "Replaces the band's recovery while the special-light override is active.",
               group="Special light"),
        number("forcedRecovery", "Forced-overburdened recovery (%)", config["forcedRecovery"],
               0, 1000, bands.FORCED_HELP, group="Forced condition"),
    ]
    finish(fields, config, read_only)
    fields[1]["disabled"] = fields[1]["disabled"] or not config["specialLight"]["enabled"]
    return {"id": 200, "table": "NativeRules", "name": "Effect-driven overrides", "fields": fields,
            "help": "These native conditions take priority over numeric bands. They do not create another load range."}
