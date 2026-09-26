"""Single source of truth for FF8's Formulae Rework.

A formula is not considered implemented merely because the editor can describe
or preview it.  ``runtime`` names the guarded component that owns the native
change; ``status`` stays ``incomplete`` until that component exists and is
wired into the Formulae Rework toggle.
"""
from __future__ import annotations

from copy import deepcopy

from core.bounded import decimal

STATUS_IMPLEMENTED = "implemented"
STATUS_INCOMPLETE = "incomplete"

FORMULAE = (
    {
        "id": "melee_damage",
        "name": "Melee damage",
        "status": STATUS_INCOMPLETE,
        "runtime": None,
        "replacement": (
            "DAMAGE = attacker STR × weapon STR bonus × (attack power × 5%), then the "
            "target's VIT reduces it by 1% per point, capped at 75%"
        ),
        "vanilla": (
            "STR = min(255, attacker STR + weapon STR bonus); DAMAGE = "
            "floor(POWER × floor((265 − VIT) × (STR + floor(STR² / 16)) / 256) / 16) "
            "× RANDOM / 256; RANDOM = 240..272"
        ),
        "blocker": (
            "Native replacement is not installed yet (Damage_ComputePhysicalCore at 0x492C40)."
        ),
    },
    {
        "id": "magic_damage",
        "name": "Magic damage",
        "status": STATUS_IMPLEMENTED,
        "runtime": "magic_damage_rework",
        "replacement": (
            "DAMAGE = spell power × attacker MAG, then the target's SPR reduces it by 1% "
            "per point, capped at 75%"
        ),
        "vanilla": (
            "Damage_ComputeMagicAndGF at 0x491AD0: BASE = trunc((265 − target SPR) × "
            "(spell power + caster MAG) / 4); SCALED = trunc(spell power × BASE / 256); "
            "ROLLED = trunc(random[240..272] × SCALED / 256), followed by vanilla "
            "caster/Shell/Defend, elemental, sign and damage-cap handling."
        ),
        "blocker": "",
    },
    {
        "id": "status_infliction",
        "name": "Status infliction",
        "status": STATUS_INCOMPLETE,
        "runtime": None,
        "replacement": (
            "CHANCE % = status accuracy − target status resistance + caster SPR − target SPR "
            "(1% per point instead of vanilla's 0.25% MAG/SPR terms), then the vanilla "
            "immunity rules. The 50% base chance for status spells is a spell-data change "
            "(status accuracy), not part of this formula."
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
        "replacement": "HEALING = spell power × caster SPR; Shell still halves the result",
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
        "id": "status_attack",
        "name": "Status attack (ST-Atk junction)",
        "status": STATUS_INCOMPLETE,
        "runtime": None,
        "replacement": (
            "CHANCE % = junctioned status attack % − target status defence − target VIT "
            "+ attacker VIT (1% per point)"
        ),
        "vanilla": (
            "CHANCE = junctioned status attack − target status defence + attacker STR / 4 "
            "− target VIT / 4."
        ),
        "blocker": "Native replacement is not installed yet; the physical status branch of "
                   "Battle_ApplyStatusWithResistRoll (0x48F9F0) is not yet patched.",
    },
    {
        "id": "elemental_attack",
        "name": "Elemental attack damage",
        "status": STATUS_INCOMPLETE,
        "runtime": None,
        "replacement": "Not specified yet: the mod doc says only \"Redo elemental attack dmg formula too.\"",
        "vanilla": "Vanilla elemental attack and elemental defence scaling.",
        "blocker": "Waiting on Lexer for the replacement rule.",
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
            "Native replacement is not installed yet. The Difficulty-stored-rate contract is "
            "explicit in mug_difficulty_from_rate (stored rate 0 stays immune); only the native "
            "Mug comparison patch remains."
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


def blocker() -> str:
    """Why the owning toggle cannot be selected yet, naming what is missing.

    The toggle is one switch for every change, so it can only be honest when all
    six are real. This says which of them are still preview-only, so a reader
    who cannot turn it on is not left guessing.
    """
    missing = ", ".join(row["name"] for row in FORMULAE if row["status"] != STATUS_IMPLEMENTED)
    done = ", ".join(row["name"] for row in FORMULAE if row["status"] == STATUS_IMPLEMENTED)
    return (f"Not available yet: {missing} still need a guarded game patch. "
            f"{done} are implemented and previewed on this page, but a preview does not "
            "change the game, and one switch for all of them cannot be half on.")


def bounded_percent(value, label: str) -> float:
    return decimal(value, label, 0, 100)


def bounded_stat(value, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a whole number from 0 to 255")
    result = int(value)
    if str(value).strip() not in {str(result), f"{result}.0"} or not 0 <= result <= 255:
        raise ValueError(f"{label} must be a whole number from 0 to 255")
    return result


def healing_amount(spell_power: int, caster_spr: int, *, shell: bool = False) -> int:
    """Mirror the implemented replacement arithmetic before Zombie/sign handling."""
    power = bounded_stat(spell_power, "Spell power")
    spr = bounded_stat(caster_spr, "Caster SPR")
    amount = power * spr
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


def mug_difficulty_from_rate(mug_rate: float) -> float:
    """Map the stored Mug rate byte (0-100, higher is easier) to Mug Difficulty.

    Difficulty runs the other way (higher is harder), so Difficulty = 100 - rate.
    """
    rate = bounded_percent(mug_rate, "Mug rate")
    return 100.0 - rate

def mug_stored_success_chance(mug_rate: float, target_spd: int,
                              mugger_spd: int) -> float:
    """Apply the requested Mug formula to a stored rate byte.

    A stored rate of 0 keeps vanilla immunity (never succeeds) instead of
    following the raw formula into positive chances.
    """
    rate = bounded_percent(mug_rate, "Mug rate")
    if rate <= 0:
        return 0.0
    return mug_chance_percent(100.0 - rate, target_spd, mugger_spd)


MITIGATION_CAP = 75  # VIT and SPR reduce damage by 1% per point, at most 75%


def mitigated(damage: int, defence: int) -> int:
    """Apply the 1%-per-point defence reduction, capped at 75%."""
    return damage * (100 - min(MITIGATION_CAP, defence)) // 100


def melee_damage(attacker_str: int, weapon_str_bonus: int, attack_power: int,
                 target_vit: int) -> int:
    """STR x weapon STR bonus x (attack power x 5%), less 1% per target VIT (cap 75%)."""
    strength = bounded_stat(attacker_str, "Attacker STR")
    bonus = bounded_stat(weapon_str_bonus, "Weapon STR bonus")
    power = bounded_stat(attack_power, "Attack power")
    vit = bounded_stat(target_vit, "Target VIT")
    return mitigated(strength * bonus * power * 5 // 100, vit)


def magic_damage(spell_power: int, attacker_mag: int, target_spr: int) -> int:
    """Spell power x MAG, less 1% per target SPR (cap 75%)."""
    power = bounded_stat(spell_power, "Spell power")
    mag = bounded_stat(attacker_mag, "Attacker MAG")
    spr = bounded_stat(target_spr, "Target SPR")
    return mitigated(power * mag, spr)


def status_infliction_chance(status_accuracy: int, target_resistance: int,
                             caster_spr: int, target_spr: int) -> int:
    """Status accuracy - resistance + caster SPR - target SPR, as a 0..100 chance.

    The native immunity rules (resistance at or above the accuracy, and the
    254/255 always-hit values) stay native and are not mirrored here.
    """
    accuracy = bounded_stat(status_accuracy, "Status accuracy")
    resistance = bounded_stat(target_resistance, "Target status resistance")
    caster = bounded_stat(caster_spr, "Caster SPR")
    target = bounded_stat(target_spr, "Target SPR")
    return max(0, min(100, accuracy - resistance + caster - target))


def status_attack_chance(status_attack: int, target_defence: int,
                         attacker_vit: int, target_vit: int) -> int:
    """Junctioned ST-Atk % - status defence + attacker VIT - target VIT, 0..100."""
    attack = bounded_stat(status_attack, "Status attack")
    defence = bounded_stat(target_defence, "Target status defence")
    attacker = bounded_stat(attacker_vit, "Attacker VIT")
    target = bounded_stat(target_vit, "Target VIT")
    return max(0, min(100, attack - defence + attacker - target))
