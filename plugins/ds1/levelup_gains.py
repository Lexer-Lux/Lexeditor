"""Level-up defense gains: the 36 stat weights behind defense growth.

The Remastered executable computes four defense base values from the
player's stats at RVA 0x2DC850. Each output is a weighted sum over nine
inputs read from the player structure: Vitality (+0x40), Attunement
(+0x48), Endurance (+0x50), Strength (+0x58), Dexterity (+0x60),
Intelligence (+0x68), Faith (+0x70), humanity (+0x84, capped at 99) and
Resistance (+0x88). Offsets +0x78 and +0x80 are never read. The function
writes its four results, in order, to its four pointer arguments; each
caller then reshapes them through correction graph 102 and truncates
them to whole numbers before equipment and effect bonuses apply.

The 36 weights are float constants in the executable's .data section,
nine per output in input order with one zero padding word before the
Resistance weight of each block. Their grouping matches the documented
game mechanics exactly: Resistance alone boosts two outputs (Physical
1.8, Flame 2.2), Faith alone boosts one (Magic 2.2), and the flat
1.0 block is Lightning, which no stat boosts. The block order follows
the game's own Physical, Magic, Flame, Lightning display order.

This module owns the factor table, validates edited rules, and exports
them as a native patch description (see exe_patches.validate): one
four-byte hook per changed weight, applied in memory by Lexeditor's
loader. spec_for_values builds the description from values alone, so a
tweak mod's script can ship these gains without reading the executable;
patch_spec additionally checks the install it builds against.
"""
from __future__ import annotations

from copy import deepcopy
import math
import struct

OUTPUTS = (
    ("physical", "Physical defense"),
    ("magic", "Magic defense"),
    ("flame", "Flame defense"),
    ("lightning", "Lightning defense"),
)
INPUTS = (
    ("vit", "Vitality", 0x40),
    ("att", "Attunement", 0x48),
    ("end", "Endurance", 0x50),
    ("str", "Strength", 0x58),
    ("dex", "Dexterity", 0x60),
    ("int", "Intelligence", 0x68),
    ("fai", "Faith", 0x70),
    ("hum", "Humanity", 0x84),
    ("res", "Resistance", 0x88),
)
# Within each output block, in INPUTS order. The Resistance weight sits
# past one zero padding word, which no patch may touch.
WITHIN = (0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x24)
BLOCK_STRIDE = 0x28
FACTOR_RVA_BASE = 0x1A2B6A0
FACTOR_OFFSET_BASE = 0x1A29AA0
MIN_FACTOR, MAX_FACTOR = 0.0, 10.0

_COMMON = (0.9,) * 8
_DEFAULTS = (
    (*_COMMON, 1.8),
    (0.85,) * 6 + (2.2, 0.85, 0.85),
    (0.85,) * 8 + (2.2,),
    (1.0,) * 9,
)
DEFAULTS = {key: {name: value for (name, _, _), value in zip(INPUTS, row)}
            for (key, _), row in zip(OUTPUTS, _DEFAULTS)}

ROW_IDS = {key: 101 + index for index, (key, _) in enumerate(OUTPUTS)}
# Equipment-screen label art per stat and per defense row, shared with
# every other tab through /api/label (icons.py): the detail weights
# read as the stats they cost, the list rows as the defenses they grow.
FIELD_ICONS = {"vit": "vit", "att": "att", "end": "end", "str": "str",
               "dex": "dex", "int": "int", "fai": "faith",
               "hum": "humanity", "res": "res"}
ROW_ICONS = {"physical": "physicalDef", "magic": "magicDef",
             "flame": "fireDef", "lightning": "lightningDef"}

ROW_HELP = ("How {label} grows when you level up. Each stat adds its value "
            "per point, and humanity above 99 counts as 99. "
            "Save and Apply to use your values.")
FIELD_HELP = ("What each point of {stat} adds to {label}. "
              "The original value is {vanilla:g}. 0 removes the gain.")


def project_defaults() -> dict:
    """Vanilla gains: a fresh mod changes no defense growth."""
    return deepcopy(DEFAULTS)


def validate(value) -> dict:
    """Canonical level-up gains: every defense maps every input to a factor."""
    if type(value) is not dict or set(value) != {key for key, _ in OUTPUTS}:
        raise ValueError("Unsupported level-up gains")
    names = {name for name, _, _ in INPUTS}
    result = {}
    for key, _ in OUTPUTS:
        row = value[key]
        if type(row) is not dict or set(row) != names:
            raise ValueError("Unsupported level-up gains")
        result[key] = {name: factor(row[name]) for name, _, _ in INPUTS}
    return result


def factor(value) -> float:
    """One weight: a finite factor from 0 (no gain) to 10."""
    if type(value) not in (int, float) or not MIN_FACTOR <= value <= MAX_FACTOR:
        raise ValueError(f"Enter a factor from {MIN_FACTOR:g} to {MAX_FACTOR:g}")
    if not math.isfinite(value):
        raise ValueError(f"Enter a factor from {MIN_FACTOR:g} to {MAX_FACTOR:g}")
    return float(value)


def edit(rules, output: str, name: str, value) -> dict:
    """The rules with one factor replaced, validated."""
    validated = validate(rules)
    if output not in validated or name not in validated[output]:
        raise ValueError("This level-up gain is not editable")
    validated[output][name] = factor(value)
    return validated


def rva_of(output: int, index: int) -> int:
    """The executable address of one weight, by output and input position."""
    return FACTOR_RVA_BASE + output * BLOCK_STRIDE + WITHIN[index]


def vanilla_of(output: int, index: int) -> float:
    """The game's own weight for one output and input position."""
    return _DEFAULTS[output][index]


def vanilla_bytes(output: int, index: int) -> bytes:
    """The four bytes the supported build holds for one weight."""
    return struct.pack("<f", vanilla_of(output, index))


def spec_for_values(rules) -> dict:
    """A native patch description for the changed weights, no executable read.

    A tweak mod's script builds its native description from the reader's
    values with this; the loader still checks every original at startup.
    """
    validated = validate(rules)
    hooks = []
    for output, (key, _) in enumerate(OUTPUTS):
        for index, (name, _, _) in enumerate(INPUTS):
            value = validated[key][name]
            if value == vanilla_of(output, index):
                continue
            hooks.append({"rva": rva_of(output, index),
                          "original": vanilla_bytes(output, index).hex(),
                          "bytes": struct.pack("<f", value).hex()})
    return {"version": 1, "islands": [], "hooks": hooks}


def patch_spec(original: bytes, rules) -> dict:
    """Export edited rules for the shared native composer, without writing files.

    The original must be the supported vanilla build, and every hooked
    weight's bytes must match the table: a wrong build fails here, never
    in the game. Unchanged weights emit no hooks and are never read.
    """
    from . import stamina_patch as native
    native._pristine(original)
    validated = validate(rules)
    length = len(original)
    for output, (key, _) in enumerate(OUTPUTS):
        for index, (name, _, _) in enumerate(INPUTS):
            if validated[key][name] == vanilla_of(output, index):
                continue
            offset = FACTOR_OFFSET_BASE + rva_of(output, index) - FACTOR_RVA_BASE
            expected = vanilla_bytes(output, index)
            if offset + 4 > length or original[offset:offset + 4] != expected:
                raise ValueError(f"The level-up gain at {rva_of(output, index):X} "
                                 "does not match this build")
    return spec_for_values(validated)


def row(output: str, config, *, read_only=False) -> dict:
    """One defense's detail row: its nine stat weights as bounded numbers."""
    from . import encumbrance
    label = next(title for key, title in OUTPUTS if key == output)
    rules = validate(config["levelupGains"])
    fields = [encumbrance.number(
        name, stat, rules[output][name], MIN_FACTOR, MAX_FACTOR,
        FIELD_HELP.format(stat=stat, label=label.lower(),
                          vanilla=vanilla_of(ROW_IDS[output] - 101, position)),
        group="Gains")
        for position, (name, stat, _) in enumerate(INPUTS)]
    for field in fields:
        field["disabled"] = read_only
        field["icon"] = FIELD_ICONS[field["key"]]
    return {"id": ROW_IDS[output], "table": "NativeRules", "name": label,
            "fields": fields, "help": ROW_HELP.format(label=label.lower())}
