"""Remove FF8's normal 9,999 battle-damage cap for the supported executable."""

from __future__ import annotations


DEFAULT_DAMAGE_LIMIT_REMOVAL = False

# FF8_EN.exe SHA-256:
# 064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570
#
# The final damage clamp at 00491124 derives its upper bound as follows:
#
#   flag = battle_action_flags & 0x08
#   max  = 9999 + (-bool(flag) & 50001)
#
# Thus the engine's existing Break Damage Limit path caps at 60,000. Changing
# `and cl, 8` to `or cl, 8` forces that proven path without changing damage
# calculation, sign handling, special battle handling, or storage width.
DAMAGE_LIMIT_FLAG_OPCODE = 0x0049112B
DAMAGE_LIMIT_FLAG_ORIGINAL = bytes.fromhex("E1")  # 80 E1 08: and cl, 8
DAMAGE_LIMIT_FLAG_PATCHED = bytes.fromhex("C9")   # 80 C9 08: or cl, 8
VANILLA_DAMAGE_LIMIT = 9_999
BREAK_DAMAGE_LIMIT = 60_000


def build_hext(enabled: bool) -> str:
    """Return the focused Hext fragment, or no patch for vanilla behavior."""
    if not isinstance(enabled, bool):
        raise ValueError("Damage Limit Removal must be true or false")
    if not enabled:
        return ""
    return "\n".join((
        "# Damage Limit Removal: use FF8's existing 60,000 damage path globally.",
        f"{DAMAGE_LIMIT_FLAG_OPCODE:X} = {DAMAGE_LIMIT_FLAG_PATCHED.hex(' ').upper()}",
        "",
    ))
