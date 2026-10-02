"""Read-only player weapon/action values for DS1 detail consumers.

No menu hooks, executable bytes, game writes or guessed R1/animation mapping.
A behavior variation proves a PARAM association, not that an animation invokes
the behavior. Consumers must identify the actual action before labelling it R1,
R2, one-handed or two-handed.

The existing DS1 PARAM definitions supply the read-only field layouts below.
ReinforceParamWeapon: Paramdex blob 7e73be04d3084dffca987e65d849bdf0f61f2028.
The supported Remastered executable's poise calculation at RVA 0x2DAB20
confirms separate weapon-scaled and fixed-attack modes, NOT their sum.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from types import MappingProxyType
from typing import Mapping


class DetailsError(ValueError):
    """An input cannot safely supply weapon detail values."""


@dataclass(frozen=True)
class _Layout:
    param_type: str
    row_size: int
    version: int
    fields: tuple[tuple[str, str, int], ...]


# These are a read-only projection, not new editable parameter definitions.
_LAYOUTS = {
    "EquipParamWeapon": _Layout("EQUIP_PARAM_WEAPON_ST", 272, 1, (
        ("behaviorVariationId", "i", 0),
        ("saWeaponDamage", "H", 0xCE),
        ("reinforceTypeId", "h", 0xD6),
    )),
    "BehaviorParam_PC": _Layout("BEHAVIOR_PARAM_ST", 32, 2, (
        ("variationId", "i", 0),
        ("behaviorJudgeId", "i", 4),
        ("refType", "B", 9),
        ("refId", "i", 12),
        ("stamina", "i", 20),
    )),
    "AtkParam_Pc": _Layout("ATK_PARAM_ST", 128, 1, (
        ("atkSuperArmorCorrection", "H", 0x4E),
        ("atkSuperArmor", "H", 0x5E),
    )),
    "ReinforceParamWeapon": _Layout("REINFORCE_PARAM_WEAPON_ST", 96, 1, (
        ("saWeaponAtkRate", "f", 0x14),
    )),
}
TABLE_NAMES = tuple(_LAYOUTS)


def _id(value: int, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 0x7FFFFFFF:
        raise DetailsError(f"{label} must be a nonnegative signed 32-bit integer")
    return value


def _f32(value: float, label: str) -> float:
    if type(value) not in (int, float) or value < 0:
        raise DetailsError(f"{label} must be a finite nonnegative number")
    try:
        if not math.isfinite(value):
            raise DetailsError(f"{label} must be a finite nonnegative number")
        result = struct.unpack("<f", struct.pack("<f", value))[0]
    except (OverflowError, struct.error) as error:
        raise DetailsError(f"{label} exceeds a 32-bit float") from error
    if not math.isfinite(result):
        raise DetailsError(f"{label} exceeds a 32-bit float")
    return result


def weapon_poise_damage(base: int, reinforcement_rate: float,
                        attack_correction: int, event_multiplier: float = 1.0) -> float:
    """Match the weapon-scaled native float32 operations, before victim effects.

    The event multiplier is an explicit caller input, not inferred from PARAMs.
    The fixed-attack path uses AtkParam.atkSuperArmor instead; it is never added.
    """
    if type(base) is not int or not 0 <= base <= 65535:
        raise DetailsError("Base poise damage must be an unsigned 16-bit integer")
    if type(attack_correction) is not int or not 0 <= attack_correction <= 65535:
        raise DetailsError("Poise correction must be an unsigned 16-bit integer")
    rate = _f32(reinforcement_rate, "Reinforcement multiplier")
    event = _f32(event_multiplier, "Event multiplier")
    scaled = _f32(_f32(base, "Base poise damage") * rate, "Reinforced poise damage")
    correction = _f32(attack_correction * _f32(0.01, "Percent scale"), "Poise correction")
    scaled = _f32(scaled * event, "Event-scaled poise damage")
    return _f32(scaled * correction, "Poise damage")


def _read_param(table: str, source: bytes) -> dict[int, dict]:
    # Reuse the existing PARAM locator. Do not add player tables to the required
    # ItemDocument.TABLES: older projects without them must keep working.
    from plugins.ds3.formats import ParamView

    layout = _LAYOUTS[table]
    if len(source) < 48 or source[44:48] != b"\0\x02\0\0":
        raise DetailsError(f"{table}: unsupported PARAM header")
    param = ParamView(source)
    if (param.big_endian or param.param_type != layout.param_type
            or param.header_version != layout.version):
        raise DetailsError(f"{table}: unsupported PARAM type or version")
    directory_end = 48 + len(param.rows) * 12
    if not directory_end <= param.strings_offset <= len(source):
        raise DetailsError(f"{table}: invalid strings boundary")
    offsets = sorted(row.data_offset for row in param.rows)
    if offsets and (offsets[0] < directory_end
                    or offsets[-1] + layout.row_size > param.strings_offset
                    or any(b - a != layout.row_size for a, b in zip(offsets, offsets[1:]))):
        raise DetailsError(f"{table}: invalid or overlapping row boundaries")
    result = {}
    for row in param.rows:
        if row.row_id in result:
            raise DetailsError(f"{table}: duplicate row ID {row.row_id}")
        result[row.row_id] = {
            name: struct.unpack_from("<" + code, source, row.data_offset + offset)[0]
            for name, code, offset in layout.fields
        }
    return result


class WeaponDetails:
    """Immutable, read-only snapshot of the supplied PARAMs.

    This intentionally reports action records rather than inventing one stamina
    cost for an entire weapon. Missing/different references remain unresolved,
    never silently become zero or fall back to an NPC attack with the same ID.
    """

    def __init__(self, params: Mapping[str, bytes]):
        missing = set(TABLE_NAMES) - params.keys()
        if missing:
            raise DetailsError("Missing detail tables: " + ", ".join(sorted(missing)))
        self._tables = MappingProxyType({
            table: MappingProxyType({
                row_id: MappingProxyType(values)
                for row_id, values in _read_param(table, bytes(params[table])).items()
            }) for table in TABLE_NAMES
        })
        by_variation = {}
        for row_id, row in self._tables["BehaviorParam_PC"].items():
            by_variation.setdefault(row["variationId"], []).append(row_id)
        self._behaviors = {key: tuple(sorted(ids)) for key, ids in by_variation.items()}

    @classmethod
    def from_archive(cls, source: bytes) -> WeaponDetails:
        """Inspect the exact supplied mod/vanilla archive without writing it."""
        from .formats import inflate, members
        plain = inflate(bytes(source))
        index = members(plain)
        return cls({
            table: plain[index[table + ".param"].offset:
                         index[table + ".param"].offset + index[table + ".param"].size]
            for table in TABLE_NAMES if table + ".param" in index
        })

    @classmethod
    def from_document(cls, document) -> WeaponDetails:
        """Include pending edits by snapshotting document.plain, not disk."""
        plain = bytes(document.plain)
        index = document.members
        return cls({
            table: plain[index[table + ".param"].offset:
                         index[table + ".param"].offset + index[table + ".param"].size]
            for table in TABLE_NAMES if table + ".param" in index
        })

    def _weapon(self, weapon_id: int):
        _id(weapon_id, "Weapon ID")
        # The inspected native weapon lookup (0x532B20) separates the final
        # two decimal digits as upgrade level before fetching the weapon row.
        row_id, level = divmod(weapon_id, 100)
        row_id *= 100
        row = self._tables["EquipParamWeapon"].get(row_id)
        if row is None:
            raise DetailsError(f"Missing weapon row {row_id} for item {weapon_id}")
        reinforcement_id = row["reinforceTypeId"] + level
        reinforcement = (self._tables["ReinforceParamWeapon"].get(reinforcement_id)
                         if reinforcement_id >= 0 else None)
        # The native poise routine uses 1.0 when reinforcement lookup fails.
        rate = 1.0 if reinforcement is None else reinforcement["saWeaponAtkRate"]
        return row_id, row, reinforcement_id, rate, reinforcement is None

    def weapon(self, weapon_id: int) -> dict:
        row_id, row, reinforcement_id, rate, fallback = self._weapon(weapon_id)
        return {
            "weaponId": weapon_id, "weaponRowId": row_id,
            "behaviorVariationId": row["behaviorVariationId"],
            "basePoiseDamage": row["saWeaponDamage"],
            "reinforcementId": reinforcement_id,
            "reinforcementRate": _f32(rate, "Reinforcement multiplier"),
            "reinforcementFallback": fallback,
            "behaviorIds": list(self._behaviors.get(row["behaviorVariationId"], ())),
            "scope": "Parameter associations; animation invocation and live effects are not inferred.",
        }

    def action(self, weapon_id: int, behavior_id: int, *,
               event_multiplier: float = 1.0, poise_mode: str = "weapon") -> dict:
        """Read one explicitly chosen behavior.

        poise_mode is supplied by the caller from the attack context. The
        native routine has distinct weapon/fixed paths; PARAM fields alone
        cannot select the runtime path. Defaults describe an ordinary
        weapon-scaled direct hit, not all attacks or a complete animation.
        """
        _id(behavior_id, "Behavior ID")
        event = _f32(event_multiplier, "Event multiplier")
        if poise_mode not in ("weapon", "fixed"):
            raise DetailsError("Poise mode must be 'weapon' or 'fixed'")
        _, weapon, _, rate, _ = self._weapon(weapon_id)
        behavior = self._tables["BehaviorParam_PC"].get(behavior_id)
        if behavior is None:
            raise DetailsError(f"Missing player behavior {behavior_id}")
        if behavior["variationId"] != weapon["behaviorVariationId"]:
            raise DetailsError("Behavior is not associated with this weapon variation")
        stamina = behavior["stamina"]
        result = {
            "weaponId": weapon_id, "behaviorId": behavior_id,
            "behaviorJudgeId": behavior["behaviorJudgeId"],
            "referenceType": behavior["refType"], "referenceId": behavior["refId"],
            "staminaCost": stamina if stamina >= 0 else None,
            "poiseDamage": None, "poiseMode": poise_mode,
            "eventMultiplier": event,
            "issues": [] if stamina >= 0 else ["Negative stamina cost is unsupported."],
            "scope": "Per behavior/hit, before live effects; not a combo total.",
        }
        if behavior["refType"] != 0:
            result["issues"].append("Projectile/effect references require their own attack context.")
            return result
        attack = (self._tables["AtkParam_Pc"].get(behavior["refId"])
                  if behavior["refId"] >= 0 else None)
        if attack is None:
            result["issues"].append("Referenced player attack is missing.")
            return result
        if poise_mode == "fixed":
            result["poiseDamage"] = float(attack["atkSuperArmor"])
        else:
            result["poiseDamage"] = weapon_poise_damage(
                weapon["saWeaponDamage"], rate,
                attack["atkSuperArmorCorrection"], event)
        return result
