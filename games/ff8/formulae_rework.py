"""Single source of truth for FF8's Formulae Rework.

A formula is not considered implemented merely because the editor can describe
or preview it.  ``runtime`` names the guarded component that owns the native
change; ``status`` stays ``incomplete`` until that component exists and is
wired into the Formulae Rework toggle.
"""
from __future__ import annotations

from copy import deepcopy

STATUS_IMPLEMENTED = "implemented"
STATUS_INCOMPLETE = "incomplete"

FORMULAE = (
    {
        "id": "melee_damage",
        "name": "Melee damage",
        "status": STATUS_INCOMPLETE,
        "runtime": None,
        "replacement": (
            "DAMAGE = (attacker STR + weapon STR bonus) × weapon power, "
            "then a % reduction from the target's VIT"
        ),
        "vanilla": (
            "STR = min(255, attacker STR + weapon STR bonus); DAMAGE = "
            "floor(POWER × floor((265 − VIT) × (STR + floor(STR² / 16)) / 256) / 16) "
            "× RANDOM / 256; RANDOM = 240..272"
        ),
        "blocker": (
            "Native replacement is not installed yet. The exact reduction/clamp rule "
            "must be fixed before patching Damage_ComputePhysicalCore at 0x492C40."
        ),
    },
    {
        "id": "magic_damage",
        "name": "Magic damage",
        "status": STATUS_INCOMPLETE,
        "runtime": None,
        "replacement": (
            "DAMAGE = spell power × attacker MAG, then a % reduction from the target's SPR"
        ),
        "vanilla": (
            "Damage_ComputeMagicAndGF at 0x491AD0: BASE = trunc((265 − target SPR) × "
            "(spell power + caster MAG) / 4); SCALED = trunc(spell power × BASE / 256); "
            "ROLLED = trunc(random[240..272] × SCALED / 256), followed by vanilla "
            "caster/Shell/Defend, elemental, sign and damage-cap handling."
        ),
        "blocker": (
            "Native replacement is not installed yet. The rework must preserve the proven "
            "post-formula Shell/Defend/element/sign behavior while replacing only base damage."
        ),
    },
    {
        "id": "status_infliction",
        "name": "Status infliction",
        "status": STATUS_INCOMPLETE,
        "runtime": None,
        "replacement": (
            "CHANCE % = spell power + attacker MAG − target SPR, then the vanilla "
            "status-defence rules"
        ),
        "vanilla": (
            "Battle_ApplyStatusWithResistRoll at 0x48F9F0: CHANCE = status accuracy + "
            "trunc(attacker stat / 4) − trunc(target stat / 4) − target status resistance; "
            "physical branches use STR/VIT and magical/GF branches use MAG/SPR, followed by "
            "the native immunity, 255, 250..254 and random-roll rules."
        ),
        "blocker": (
            "Native replacement is not installed yet. The patch must change the magical "
            "chance term without changing the native resistance/immunity special cases."
        ),
    },
    {
        "id": "spell_healing",
        "name": "Spell healing",
        "status": STATUS_IMPLEMENTED,
        "runtime": "healing_rework",
        "replacement": "HEALING = spell power × attacker MAG; Shell still halves the result",
        "vanilla": (
            "Damage_ComputeCurativeMagic at 0x493280: HALF = trunc((spell power + caster MAG) / 2); "
            "HEALING = trunc(spell power × random[240..272] × HALF / 256); Shell halves it, "
            "and Zombie reverses the restorative sign later."
        ),
        "blocker": "",
    },
    {
        "id": "physical_accuracy",
        "name": "Physical accuracy",
        "status": STATUS_IMPLEMENTED,
        "runtime": "luck_accuracy",
        "replacement": (
            "EFFECTIVE = hit rate + attacker LUCK − target EVA − target LUCK; "
            "the native 0..255 hit roll remains unchanged"
        ),
        "vanilla": (
            "EFFECTIVE = hit rate + floor(attacker LUCK / 2) − target EVA − target LUCK; "
            "the native 0..255 hit roll then resolves the attack."
        ),
        "blocker": "",
    },
    {
        "id": "mug_chance",
        "name": "Mug chance",
        "status": STATUS_INCOMPLETE,
        "runtime": None,
        "replacement": (
            "Mug % chance = 100% − target Mug Difficulty − target SPD + mugger SPD"
        ),
        "vanilla": (
            "getMugObjectIdAndQuantity: target Mug rate 0 never succeeds; otherwise Mug succeeds "
            "when random[0..255] ≤ target Mug rate + floor(mugger SPD / 2)."
        ),
        "blocker": (
            "Native replacement is not installed yet. FF8 stores a target Mug rate byte, not a "
            "named Mug Difficulty value; the Difficulty↔stored-rate contract must be made explicit "
            "before changing the native Mug comparison."
        ),
    },
)

_IDS = tuple(row["id"] for row in FORMULAE)
if len(_IDS) != len(set(_IDS)):
    raise RuntimeError("Formulae Rework formula IDs must be unique")
if any(row["status"] not in {STATUS_IMPLEMENTED, STATUS_INCOMPLETE} for row in FORMULAE):
    raise RuntimeError("Formulae Rework contains an invalid implementation status")
if any((row["status"] == STATUS_IMPLEMENTED) != bool(row["runtime"]) for row in FORMULAE):
    raise RuntimeError("Implemented Formulae Rework rows must name a runtime component")


def rows() -> list[dict]:
    """Return a JSON-safe copy for the editor/UI."""
    return deepcopy(list(FORMULAE))


def implemented_ids() -> tuple[str, ...]:
    return tuple(row["id"] for row in FORMULAE if row["status"] == STATUS_IMPLEMENTED)


def incomplete_ids() -> tuple[str, ...]:
    return tuple(row["id"] for row in FORMULAE if row["status"] == STATUS_INCOMPLETE)


def available() -> bool:
    """The owning toggle is selectable only when every advertised change is real."""
    return all(row["status"] == STATUS_IMPLEMENTED for row in FORMULAE)


def bounded_percent(value, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number from 0 to 100")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a number from 0 to 100") from error
    if not 0 <= result <= 100:
        raise ValueError(f"{label} must be from 0 to 100")
    return result


def bounded_stat(value, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a whole number from 0 to 255")
    result = int(value)
    if str(value).strip() not in {str(result), f"{result}.0"} or not 0 <= result <= 255:
        raise ValueError(f"{label} must be a whole number from 0 to 255")
    return result


def healing_amount(spell_power: int, caster_mag: int, *, shell: bool = False) -> int:
    """Mirror the implemented replacement arithmetic before Zombie/sign handling."""
    power = bounded_stat(spell_power, "Spell power")
    mag = bounded_stat(caster_mag, "Caster MAG")
    amount = power * mag
    return amount // 2 if shell else amount


def physical_accuracy_effective(hit_rate: int, attacker_luck: int,
                                target_eva: int, target_luck: int) -> int:
    """Mirror the Formulae Rework's implemented full-LUCK accuracy input."""
    hit = bounded_stat(hit_rate, "Hit rate")
    luck = bounded_stat(attacker_luck, "Attacker LUCK")
    eva = bounded_stat(target_eva, "Target EVA")
    target_luck = bounded_stat(target_luck, "Target LUCK")
    return max(0, min(100, hit + luck - eva - target_luck))


def mug_chance_percent(target_mug_difficulty: float, target_spd: int,
                       mugger_spd: int) -> float:
    """Mirror the requested Mug formula for previews/tests; runtime is still incomplete."""
    difficulty = bounded_percent(target_mug_difficulty, "Target Mug Difficulty")
    target = bounded_stat(target_spd, "Target SPD")
    mugger = bounded_stat(mugger_spd, "Mugger SPD")
    return max(0.0, min(100.0, 100.0 - difficulty - target + mugger))
