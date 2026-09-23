"""Guarded FF8 Drop Chance / Rare Item slot weighting tweak.

The supported 2013 Steam English executable contains two independent item-slot
rollers: Battle_RollDropItem at 0x486650 and Battle_RollMugItem at 0x4867C0.
Both contain the same six cumulative thresholds. Rather than hard-code guessed
instruction offsets, this module finds the immediate operands inside those two
bounded functions in the already SHA-verified local executable and patches only
those operands.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IMAGE_BASE = 0x400000
DROP_START, DROP_END = 0x486650, 0x4867C0
MUG_START, MUG_END = 0x4867C0, 0x4868C0

VANILLA_NORMAL_WEIGHTS = (178, 51, 15, 12)
VANILLA_RARE_WEIGHTS = (128, 114, 14, 0)
TWEAK_NORMAL_WEIGHTS = (137, 68, 34, 17)
TWEAK_RARE_WEIGHTS = (94, 70, 53, 39)

VANILLA_NORMAL_THRESHOLDS = (178, 229, 244)
VANILLA_RARE_THRESHOLDS = (128, 242, 261)
TWEAK_NORMAL_THRESHOLDS = (137, 205, 239)
TWEAK_RARE_THRESHOLDS = (94, 164, 217)

_THRESHOLD_REPLACEMENTS = dict(zip(
    VANILLA_NORMAL_THRESHOLDS + VANILLA_RARE_THRESHOLDS,
    TWEAK_NORMAL_THRESHOLDS + TWEAK_RARE_THRESHOLDS,
))


@dataclass(frozen=True)
class ThresholdPatch:
    function: str
    address: int
    original: int
    replacement: int


def _cmp_imm32_at(blob: bytes, immediate_offset: int) -> bool:
    """Return whether an immediate is the operand of CMP r/m32,imm32."""
    if immediate_offset >= 1 and blob[immediate_offset - 1] == 0x3D:
        return True
    for opcode_offset in range(max(0, immediate_offset - 8), immediate_offset):
        if blob[opcode_offset] != 0x81 or opcode_offset + 1 >= len(blob):
            continue
        modrm = blob[opcode_offset + 1]
        if ((modrm >> 3) & 7) != 7:
            continue
        mod, rm = modrm >> 6, modrm & 7
        cursor = opcode_offset + 2
        if mod != 3 and rm == 4:
            if cursor >= len(blob):
                continue
            sib = blob[cursor]
            cursor += 1
            if mod == 0 and (sib & 7) == 5:
                cursor += 4
        if mod == 0 and rm == 5:
            cursor += 4
        elif mod == 1:
            cursor += 1
        elif mod == 2:
            cursor += 4
        if cursor == immediate_offset:
            return True
    return False


def _discover_function(blob: bytes, start: int, end: int, name: str) -> list[ThresholdPatch]:
    if end <= start or len(blob) != end - start:
        raise ValueError(f"Invalid {name} function extent")
    result: list[ThresholdPatch] = []
    for original, replacement in _THRESHOLD_REPLACEMENTS.items():
        needle = int(original).to_bytes(4, "little")
        matches = []
        cursor = 0
        while True:
            found = blob.find(needle, cursor)
            if found < 0:
                break
            if _cmp_imm32_at(blob, found):
                matches.append(found)
            cursor = found + 1
        if len(matches) != 1:
            raise ValueError(
                f"Unsupported {name} selector: expected one CMP immediate {original}, "
                f"found {len(matches)}"
            )
        result.append(ThresholdPatch(
            function=name,
            address=start + matches[0],
            original=original,
            replacement=replacement,
        ))
    addresses = [patch.address for patch in result]
    if len(addresses) != len(set(addresses)):
        raise ValueError(f"Unsupported {name} selector: threshold operands overlap")
    return result


def discover(stream) -> tuple[ThresholdPatch, ...]:
    """Find and validate every threshold operand in the verified executable."""
    patches: list[ThresholdPatch] = []
    for name, start, end in (
        ("Battle_RollDropItem", DROP_START, DROP_END),
        ("Battle_RollMugItem", MUG_START, MUG_END),
    ):
        stream.seek(start - IMAGE_BASE)
        blob = stream.read(end - start)
        patches.extend(_discover_function(blob, start, end, name))
    if len(patches) != 12:
        raise ValueError("Unsupported FF8 Drop Chance selector layout")
    return tuple(patches)


def discover_path(executable: Path) -> tuple[ThresholdPatch, ...]:
    with Path(executable).open("rb") as stream:
        return discover(stream)


def verify_executable(stream) -> None:
    discover(stream)


def _thresholds(enabled: bool, rare_item: bool) -> tuple[int, int, int]:
    if enabled:
        return TWEAK_RARE_THRESHOLDS if rare_item else TWEAK_NORMAL_THRESHOLDS
    return VANILLA_RARE_THRESHOLDS if rare_item else VANILLA_NORMAL_THRESHOLDS


def select_slot(roll: int, *, enabled: bool, rare_item: bool) -> int:
    """Deterministic mirror of the native 0..255 slot selector."""
    if isinstance(roll, bool) or not isinstance(roll, int) or not 0 <= roll <= 255:
        raise ValueError("Drop/Mug slot roll must be a whole number from 0 to 255")
    first, second, third = _thresholds(bool(enabled), bool(rare_item))
    if roll < first:
        return 0
    if roll < second:
        return 1
    if roll < third:
        return 2
    return 3


def weights(enabled: bool, rare_item: bool) -> tuple[int, int, int, int]:
    if enabled:
        return TWEAK_RARE_WEIGHTS if rare_item else TWEAK_NORMAL_WEIGHTS
    return VANILLA_RARE_WEIGHTS if rare_item else VANILLA_NORMAL_WEIGHTS


def metadata() -> dict:
    def rows(values):
        return [
            {"slot": slot, "weight": weight, "denominator": 256,
             "percent": weight * 100.0 / 256.0}
            for slot, weight in enumerate(values)
        ]
    return {
        "normal": rows(TWEAK_NORMAL_WEIGHTS),
        "rareItem": rows(TWEAK_RARE_WEIGHTS),
        "vanillaNormal": rows(VANILLA_NORMAL_WEIGHTS),
        "vanillaRareItem": rows(VANILLA_RARE_WEIGHTS),
    }


def build_hext(enabled: bool, plan: tuple[ThresholdPatch, ...] | None = None) -> str:
    if not isinstance(enabled, bool):
        raise ValueError("Drop Chance must be true or false")
    if not enabled:
        return ""
    if plan is None or len(plan) != 12:
        raise ValueError("Drop Chance requires a verified local selector plan")
    expected = {
        (name, original)
        for name in ("Battle_RollDropItem", "Battle_RollMugItem")
        for original in _THRESHOLD_REPLACEMENTS
    }
    actual = {(patch.function, patch.original) for patch in plan}
    if actual != expected:
        raise ValueError("Drop Chance selector plan is incomplete or duplicated")
    lines = [
        "# Drop Chance: shared regular-drop and Mug slot weighting.",
        "# Normal 137/68/34/17; Rare Item 94/70/53/39 (all totals 256).",
    ]
    for patch in sorted(plan, key=lambda item: item.address):
        replacement = patch.replacement.to_bytes(4, "little").hex(" ").upper()
        lines.append(f"{patch.address:X} = {replacement}")
    return "\n".join(lines + [""])
