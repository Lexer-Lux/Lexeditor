"""Formulae Rework: status spells and junctioned status attacks at 1% per point.

Lexer's mod doc ("Final Fantasy VIII Mod (FF8)", AILMENTS):
- Status spells: chance = status accuracy - target resistance + caster SPR -
  target SPR, each point 1% (vanilla: + MAG / 4 - SPR / 4).
- Junctioned status attacks (ST-Atk): chance = status attack - target
  defence + attacker VIT - target VIT, each point 1% (vanilla: + STR / 4 -
  VIT / 4).

Against FF8_EN.exe SHA-256 064d466b...9570, Battle_ApplyStatusWithResistRoll
(0048F9F0) takes the attacker's and target's stat as arguments and computes
`accuracy + attacker / 4 - target / 4 - resistance`, keeping resistance >= 200
immune and accuracy >= 250 always hitting. Its three caller pairs load those
stats right before the call, into registers used for nothing else:

- 0048F88F STR / 0048F897 VIT: the physical ST-Atk path.
- 004916BF STR / 004916C7 VIT and 004916E4 MAG / 004916EE SPR: the shared
  path, physical or magical by attack kind.
- 00492101 MAG / 00492109 SPR: the spell path.

So the rework is six in-place byte edits: drop the two divides by 4, and
read the attacker's VIT instead of STR and SPR instead of MAG. The immunity
and always-hit rules stay native. Stats are 0..255, so the divides' rounding
adjustment for negative values never applies and needs no change.
"""

from __future__ import annotations

DEFAULT_STATUS_CHANCE_REWORK = False

# (site, original bytes, patched bytes, what it does)
PATCHES = (
    (0x0048FA6B, bytes.fromhex("C1 FD 02"), bytes.fromhex("90 90 90"),
     "attacker stat: full points, not / 4"),
    (0x0048FA6E, bytes.fromhex("C1 F8 02"), bytes.fromhex("90 90 90"),
     "target stat: full points, not / 4"),
    (0x0048F88F, bytes.fromhex("8A 91 CD 7B D2 01"), bytes.fromhex("8A 91 CE 7B D2 01"),
     "ST-Atk: attacker VIT instead of STR"),
    (0x004916BF, bytes.fromhex("8A 90 CD 7B D2 01"), bytes.fromhex("8A 90 CE 7B D2 01"),
     "physical status: attacker VIT instead of STR"),
    (0x004916E4, bytes.fromhex("8A 82 CF 7B D2 01"), bytes.fromhex("8A 82 D0 7B D2 01"),
     "magical status: caster SPR instead of MAG"),
    (0x00492101, bytes.fromhex("8A 9A CF 7B D2 01"), bytes.fromhex("8A 9A D0 7B D2 01"),
     "status spell: caster SPR instead of MAG"),
)


def build_hext(enabled: bool) -> str:
    """The patch, or nothing: vanilla status chances when the rework is off."""
    if not isinstance(enabled, bool):
        raise ValueError("Status Chance Rework must be true or false")
    if not enabled:
        return ""
    lines = ["# Formulae Rework: status spells use caster SPR, ST-Atk attacker VIT, 1% per point."]
    for site, _original, patched, what in PATCHES:
        lines.append(f"# {what}")
        lines.append(f"{site:X} = {patched.hex(' ').upper()}")
    return "\n".join(lines + [""])


def verified_hooks() -> list[tuple[int, bytes]]:
    return [(site, original) for site, original, _patched, _what in PATCHES]
