"""Typed Stardew Valley 1.6 data families safe for field-level Content Patcher editing."""
from __future__ import annotations

import math

INT_MAX = 2_147_483_647

_DEBRIS = [
    {"value": 0, "label": "Copper"}, {"value": 2, "label": "Iron"},
    {"value": 4, "label": "Coal"}, {"value": 6, "label": "Gold"},
    {"value": 8, "label": "Coins"}, {"value": 10, "label": "Iridium"},
    {"value": 12, "label": "Wood"}, {"value": 14, "label": "Stone"},
    {"value": 32, "label": "Big stone"}, {"value": 34, "label": "Big wood"},
]


def _int(label, minimum=0, maximum=INT_MAX, default=None, help=""):
    value = {"label": label, "kind": "int", "min": minimum, "max": maximum, "help": help}
    if default is not None:
        value["default"] = default
    return value


def _number(label, minimum, maximum, default=None, step=0.01, help=""):
    value = {"label": label, "kind": "number", "min": minimum, "max": maximum, "step": step, "help": help}
    if default is not None:
        value["default"] = default
    return value


def _bool(label, default=False, help=""):
    return {"label": label, "kind": "bool", "default": default, "help": help}


def _enum(label, values, default=None, help=""):
    value = {"label": label, "kind": "enum", "options": values, "help": help}
    if default is not None:
        value["default"] = default
    return value


DATASET_SPECS = {
    "objects": {
        "label": "Objects", "noun": "objects", "target": "Data/Objects", "source": "Objects",
        "fields": {
            "Price": _int("Sell price", 0, INT_MAX, 0, "Base sell price in gold; shops can define separate purchase prices."),
            "Edibility": _int("Edibility", -300, INT_MAX, -300, "Energy/health recovery factor. -300 is Stardew's inedible sentinel."),
            "IsDrink": _bool("Drink", False, "Use drinking behavior instead of eating behavior when the item is edible."),
        },
    },
    "big-craftables": {
        "label": "Big craftables", "noun": "big craftables", "target": "Data/BigCraftables", "source": "BigCraftables",
        "fields": {
            "Price": _int("Sell price", 0, INT_MAX, 0, "Base sell price in gold."),
            "Fragility": _enum("Pickup behavior", [
                {"value": 0, "label": "Any tool"}, {"value": 1, "label": "Breaks with axe/hoe/pickaxe"},
                {"value": 2, "label": "Cannot be removed"},
            ], 0, "How the placed craftable can be picked up."),
            "CanBePlacedIndoors": _bool("Place indoors", True),
            "CanBePlacedOutdoors": _bool("Place outdoors", True),
            "IsLamp": _bool("Produces light", False),
            "SpriteIndex": _int("Sprite index", 0, INT_MAX, 0),
        },
    },
    "crops": {
        "label": "Crops", "noun": "crops", "target": "Data/Crops", "source": "Crops",
        "fields": {
            "RegrowDays": _int("Regrow days", -1, INT_MAX, -1, "-1 means the crop does not regrow after harvest."),
            "IsRaised": _bool("Raised crop", False),
            "IsPaddyCrop": _bool("Paddy crop", False),
            "NeedsWatering": _bool("Needs watering", True),
            "HarvestMethod": _enum("Harvest method", [
                {"value": "Grab", "label": "Grab"}, {"value": "Scythe", "label": "Scythe"},
            ], "Grab"),
            "HarvestMinStack": _int("Minimum harvest", 1, INT_MAX, 1),
            "HarvestMaxStack": _int("Maximum harvest", 1, INT_MAX, 1),
            "ExtraHarvestChance": _number("Extra harvest chance", 0.0, 0.9, 0.0, 0.01),
            "SpriteIndex": _int("Sprite index", 0, INT_MAX, 0),
            "CountForMonoculture": _bool("Counts for Monoculture", False),
            "CountForPolyculture": _bool("Counts for Polyculture", False),
        },
    },
    "fences": {
        "label": "Fences", "noun": "fences", "target": "Data/Fences", "source": "Fences",
        "fields": {
            "Health": _number("Health", 0.0, float(INT_MAX), None, 0.1, "Initial fence health, which controls degradation time."),
            "RemovalDebrisType": _enum("Removal debris", _DEBRIS, 14),
        },
    },
    "floors-paths": {
        "label": "Floors & paths", "noun": "floors and paths", "target": "Data/FloorsAndPaths", "source": "FloorsAndPaths",
        "fields": {
            "RemovalDebrisType": _enum("Removal debris", _DEBRIS, 14),
            "ShadowType": _enum("Shadow", [
                {"value": "None", "label": "None"}, {"value": "Square", "label": "Square"},
                {"value": "Contoured", "label": "Contoured"},
            ], "None"),
            "ConnectType": _enum("Connection style", [
                {"value": "Default", "label": "Default"}, {"value": "Path", "label": "Path"},
                {"value": "CornerDecorated", "label": "Corner decorated"}, {"value": "Random", "label": "Random"},
            ], "Default"),
            "CornerSize": _int("Corner size", 0, INT_MAX, 0),
        },
    },
    "machines": {
        "label": "Machines", "noun": "machines", "target": "Data/Machines", "source": "Machines",
        "fields": {
            "OnlyCompleteOvernight": _bool("Only complete overnight", False),
            "AllowLoadWhenFull": _bool("Allow load when full", False),
            "WorkingEffectChance": _number("Working effect chance", 0.0, 1.0, 0.33, 0.01),
        },
    },
    "weapons": {
        "label": "Weapons", "noun": "weapons", "target": "Data/Weapons", "source": "Weapons",
        "fields": {
            "Type": _enum("Weapon type", [
                {"value": 0, "label": "Stabbing sword"}, {"value": 1, "label": "Dagger"},
                {"value": 2, "label": "Club / hammer"}, {"value": 3, "label": "Slashing sword"},
            ]),
            "SpriteIndex": _int("Sprite index", 0, INT_MAX),
            "MinDamage": _int("Minimum damage", 0, INT_MAX),
            "MaxDamage": _int("Maximum damage", 0, INT_MAX),
            "CritChance": _number("Critical hit chance", 0.0, 1.0, 0.02, 0.01),
            "CanBeLostOnDeath": _bool("Can be lost on death", True),
            "MineBaseLevel": _int("Base mine level", -1, INT_MAX, -1),
            "MineMinLevel": _int("Minimum mine level", -1, INT_MAX, -1),
        },
    },
}


def dataset_spec(key: str) -> dict:
    try:
        return DATASET_SPECS[key]
    except KeyError as error:
        raise ValueError(f"Unsupported Stardew data family: {key}") from error


def schema(key: str) -> dict:
    spec = dataset_spec(key)
    return {
        "key": key, "label": spec["label"], "noun": spec["noun"], "target": spec["target"],
        "fields": [{"key": field_key, **field} for field_key, field in spec["fields"].items()],
    }


def validate_field_value(field: dict, value):
    kind = field["kind"]
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{field['label']} must be true or false")
    elif kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field['label']} must be an integer")
        if value < field["min"] or value > field["max"]:
            raise ValueError(f"{field['label']} is outside the supported range")
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{field['label']} must be a finite number")
        if float(value) < field["min"] or float(value) > field["max"]:
            raise ValueError(f"{field['label']} is outside the supported range")
    elif kind == "enum":
        allowed = [option["value"] for option in field["options"]]
        if not any(type(value) is type(candidate) and value == candidate for candidate in allowed):
            raise ValueError(f"{field['label']} is not a supported value")
    else:
        raise ValueError(f"Unsupported Stardew field kind: {kind}")
    return value
