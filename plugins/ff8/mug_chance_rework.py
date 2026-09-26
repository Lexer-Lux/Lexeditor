"""Formulae Rework: Mug % chance = 100 - Mug Difficulty - target SPD + mugger SPD (#408).

Mug Difficulty is 100 minus the enemy's stored Mug rate (0-100, higher is
easier; see formulae_rework.mug_difficulty_from_rate), so the chance is
`rate - target SPD + mugger SPD`, rolled as random 0..99 below it. A stored
rate of 0 stays immune, as in vanilla.

Against FF8_EN.exe SHA-256 064d466b...9570, getMugObjectIdAndQuantity
(004867C0) loads the rate into EDI (0 already jumps to the failure path),
then at 004867EA rolls random 0..255 and succeeds when the roll is at most
rate + mugger SPD / 2. The hook replaces that roll and comparison and
rejoins the native code at the success (0048680A) or failure (004868A7)
path. ESI is the target index; the mugger's SPD is the fourth argument.
"""

from __future__ import annotations

DEFAULT_MUG_CHANCE_REWORK = False

HOOK = 0x004867EA
HOOK_ORIGINAL = bytes.fromhex("E8 31 88 00 00")  # call 0048F020 (random)
RANDOM = 0x0048F020
SUCCESS = 0x0048680A
FAILURE = 0x004868A7
TARGET_SPD = 0x01D27BD1  # + target index x 0xD0

CAVE = 0x027AB200

ASSEMBLY = f"""
    call {RANDOM:#x}
    movzx eax, al
    xor edx, edx
    mov ecx, 100
    div ecx
    push edx
    mov eax, edi
    add eax, dword ptr [esp + 0x20]
    lea ecx, [esi + esi*2]
    lea ecx, [esi + ecx*4]
    shl ecx, 4
    movzx ecx, byte ptr [ecx + {TARGET_SPD:#x}]
    sub eax, ecx
    pop edx
    cmp edx, eax
    jl mugged
    push {FAILURE:#x}
    ret
mugged:
    push {SUCCESS:#x}
    ret
"""

# Assembled at CAVE from ASSEMBLY; tests/ff8/test_ff8_mug_chance_rework.py
# re-assembles it (keystone) and runs it under unicorn.
CODE = bytes.fromhex(
    "E8 1B 3E CE FD 0F B6 C0 31 D2 B9 64 00 00 00 F7"
    "F1 52 89 F8 03 44 24 20 8D 0C 76 8D 0C 8E C1 E1"
    "04 0F B6 89 D1 7B D2 01 29 C8 5A 39 C2 7C 06 68"
    "A7 68 48 00 C3 68 0A 68 48 00 C3"
)


def _assemble() -> bytes:
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    return bytes(ks.asm(ASSEMBLY, CAVE)[0])


def build_hext(enabled: bool) -> str:
    """The patch, or nothing: vanilla Mug chance when the rework is off."""
    if not isinstance(enabled, bool):
        raise ValueError("Mug Chance Rework must be true or false")
    if not enabled:
        return ""
    jump = b"\xE9" + (CAVE - (HOOK + 5)).to_bytes(4, "little", signed=True)
    return "\n".join((
        "# Formulae Rework: Mug % = stored rate - target SPD + mugger SPD (rate 0 stays immune).",
        f"{CAVE:X}:{len(CODE):X}",
        f"{CAVE:X} = {CODE.hex(' ').upper()}",
        f"{HOOK:X} = {jump.hex(' ').upper()}",
        "",
    ))


def verified_hooks() -> list[tuple[int, bytes]]:
    return [(HOOK, HOOK_ORIGINAL)]
