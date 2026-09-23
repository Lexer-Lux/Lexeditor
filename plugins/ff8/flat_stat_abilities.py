"""FF8 flat character-stat ability patch and lossless text migration."""

from __future__ import annotations

from pathlib import Path

from . import formats, kernel_text


DEFAULT_FLAT_STAT_ABILITIES = False

# FF8_EN.exe 2013 Steam EN. 004962C0 totals equipped character-stat
# abilities. The native caller then treats that total as a percentage.
STAT_BONUS_BASE = 0x004962CE
STAT_BONUS_BASE_ORIGINAL = bytes.fromhex("BF 64 00 00 00")
STAT_BONUS_BASE_FLAT = bytes.fromhex("31 FF 90 90 90")

# Seven stats use the same base * coefficient / 100 sequence. Evasion and Hit
# use the same arithmetic with stack cleanup inside the displaced range.
STANDARD_APPLY_SITES = (
    0x00495A06, 0x00495A64, 0x00495AA9, 0x00495AEE,
    0x00495B33, 0x00495B78, 0x00495BBD,
)
STANDARD_APPLY_ORIGINAL = bytes.fromhex(
    "0F AF C8 B8 1F 85 EB 51 F7 E9 C1 FA 05 8B CA C1 E9 1F 03 D1"
)
STANDARD_APPLY_FLAT = bytes.fromhex("01 C1 89 CA") + b"\x90" * 16
EVA_APPLY_SITE = 0x00495BF4
HIT_APPLY_SITE = 0x00495C37
EVA_APPLY_ORIGINAL = bytes.fromhex(
    "B8 1F 85 EB 51 0F AF CA F7 E9 C1 FA 05 8B C2 83 C4 04 C1 E8 1F 03 D0"
)
HIT_APPLY_ORIGINAL = bytes.fromhex(
    "B8 1F 85 EB 51 0F AF CA F7 E9 C1 FA 05 8B C2 83 C4 08 C1 E8 1F 03 D0"
)
EVA_APPLY_FLAT = bytes.fromhex("01 D1 89 CA 83 C4 04") + b"\x90" * 16
HIT_APPLY_FLAT = bytes.fromhex("01 D1 89 CA 83 C4 08") + b"\x90" * 16

TEXT_SECTION = 44
_VANILLA_NAMES = (
    "HP+20%", "HP+40%", "HP+80%", "Str+20%", "Str+40%", "Str+60%",
    "Vit+20%", "Vit+40%", "Vit+60%", "Mag+20%", "Mag+40%", "Mag+60%",
    "Spr+20%", "Spr+40%", "Spr+60%", "Spd+20%", "Spd+40%", "Eva+30%",
    "Luck+50%",
)
_VANILLA_DESCRIPTIONS = (
    "{Raises} HP by 20%", "{Raises} HP by 40%", "{Raises} HP by 80%",
    "{Raises} Str by 20%", "{Raises} Str by 40%", "{Raises} Str by 60%",
    "{Raises} Vit by 20%", "{Raises} Vit by 40%", "{Raises} Vit by 60%",
    "{Raises} Magic damage by 20%", "{Raises} Magic damage by 40%",
    "{Raises} Magic damage by 60%", "{Raises} Spr by 20%",
    "{Raises} Spr by 40%", "{Raises} Spr by 60%", "{Raises} Spd by 20%",
    "{Raises} Spd by 40%", "{Raises} Eva by 30%", "{Raises} Luck by 50%",
)
_TO_FLAT = {
    **{value: value[:-1] for value in _VANILLA_NAMES},
    **{value: value[:-1] + " points" for value in _VANILLA_DESCRIPTIONS},
}
_TO_VANILLA = {value: key for key, value in _TO_FLAT.items()}


def build_hext(enabled: bool) -> str:
    if not isinstance(enabled, bool):
        raise ValueError("Flat +Stat Abilities must be true or false")
    if not enabled:
        return ""
    rows = [
        "# Flat +Stat Abilities: ability values are fixed stat points, not percentages.",
        f"{STAT_BONUS_BASE:X} = {STAT_BONUS_BASE_FLAT.hex(' ').upper()}",
    ]
    for address in STANDARD_APPLY_SITES:
        rows.append(f"{address:X} = {STANDARD_APPLY_FLAT.hex(' ').upper()}")
    rows.extend((
        f"{EVA_APPLY_SITE:X} = {EVA_APPLY_FLAT.hex(' ').upper()}",
        f"{HIT_APPLY_SITE:X} = {HIT_APPLY_FLAT.hex(' ').upper()}",
        "",
    ))
    return "\n".join(rows)


def verify_executable(stream) -> None:
    checks = [(STAT_BONUS_BASE, STAT_BONUS_BASE_ORIGINAL)]
    checks.extend((address, STANDARD_APPLY_ORIGINAL) for address in STANDARD_APPLY_SITES)
    checks.extend(((EVA_APPLY_SITE, EVA_APPLY_ORIGINAL), (HIT_APPLY_SITE, HIT_APPLY_ORIGINAL)))
    for address, expected in checks:
        stream.seek(address - 0x400000)
        if stream.read(len(expected)) != expected:
            raise RuntimeError("The installed FF8 flat-stat ability bytes do not match the verified build")


def _flat_text(value: str) -> str:
    return _TO_FLAT.get(value, value)


def _vanilla_text(value: str) -> str:
    return _TO_VANILLA.get(value, value)


def transformed_kernel(project_root: Path, baseline_root: Path, enabled: bool) -> tuple[Path, bytes, int]:
    """Return a safe text-only kernel transform without replacing custom text."""
    target = Path(project_root) / "direct" / "kernel.bin"
    source = target if target.is_file() else Path(baseline_root) / "main" / "kernel.bin"
    raw = source.read_bytes()
    rows = kernel_text.rows(raw, formats.SECTIONS)["rows"]
    edits = []
    transform = _flat_text if enabled else _vanilla_text
    for row in rows:
        if int(row["sectionId"]) != TEXT_SECTION:
            continue
        value = str(row["value"])
        replacement = transform(value)
        if replacement != value or (
            int(row["slot"]) == 0 and value in (*_VANILLA_NAMES, *_TO_VANILLA)
        ):
            edits.append({
                "sectionId": TEXT_SECTION,
                "recordId": int(row["recordId"]),
                "slot": int(row["slot"]),
                "value": replacement,
            })
    rebuilt, changed = kernel_text.apply_edits(raw, formats.SECTIONS, edits)
    return target, rebuilt, changed
