"""Full-LUCK accuracy for the supported FF8 2013 Steam English executable.

The physical hit check computes its accuracy input as

    eax = (attacker LUCK / 2) - target LUCK
    eax = eax - target EVA + global modifier
    if eax < 0: eax = 0
    edi = eax * 255 / 100                 ; scaled to a 0-255 roll
    if edi == 0 or edi < random & 0xFF: -> miss (0x004930CB)

The halving is a single `shr eax, 1` at LUCK_HALVE. Replacing it with two
NOPs feeds the attacker's whole LUCK into the same subtraction, which is the
requested change and touches nothing else in the chain: the clamp, the /100
scaling, the roll and both exits are left exactly as the game wrote them.

Verified against FF8_EN.exe SHA-256
064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570 by
disassembly; the miss exit at 0x004930CB sets bit 4 of 0x01D27ADE and returns
zero, and the hit exit at 0x00492F83 sets 0x01D28E07 to one.
"""

from __future__ import annotations


DEFAULT_FULL_LUCK_ACCURACY = False

LUCK_HALVE = 0x00492EEF
LUCK_HALVE_ORIGINAL = bytes.fromhex("D1 E8")   # shr eax, 1
LUCK_HALVE_PATCHED = bytes.fromhex("90 90")    # nop; nop


def build_hext(enabled: bool) -> str:
    if not isinstance(enabled, bool):
        raise ValueError("Full LUCK Accuracy must be true or false")
    if not enabled:
        return ""
    return "\n".join((
        "# Full LUCK Accuracy: the attacker contributes LUCK, not LUCK / 2.",
        f"{LUCK_HALVE:X} = {LUCK_HALVE_PATCHED.hex(' ').upper()}",
        "",
    ))
