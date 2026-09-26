"""Formulae Rework: spell damage = spell power x MAG, less 1% per target SPR (cap 75%).

Lexer's mod doc ("Final Fantasy VIII Mod (FF8)", MAGIC DAMAGE): "Now it's just
the product of spell power and magic stat, then your target's SPR reduces
damage by 1% per point, hardcapped to 75%."

Against FF8_EN.exe SHA-256 064d466b...9570:

- Damage_ComputeMagicAndGF (00491AD0) computes the vanilla core at
  00491C62..00491CC1 into ESI: random roll, (265 - SPR) x (power + MAG) / 4,
  x power / 256, x roll / 256. EBX is the caster index, EBP the spell power,
  EDI the target SPR (already zero when the target ignores it).
- Several attack types reach that core, so only real spells are changed: the
  damage switch's Magic case (attack type 2) calls the routine at 00492386.
  That call goes through a wrapper that raises a flag for its duration.
- At 00491C62 the flag decides: raised gives the new formula; lowered runs the
  vanilla random call and continues at 00491C67 unchanged.
- Everything after the core stays native: enemy casters halved, Shell,
  Defend, element, sign and the damage cap.
"""

from __future__ import annotations

from . import formulae_rework

DEFAULT_MAGIC_DAMAGE_REWORK = False

MAGIC_CALL = 0x00492386
MAGIC_CALL_ORIGINAL = bytes.fromhex("E8 45 F7 FF FF")  # call 00491AD0
DAMAGE_ROUTINE = 0x00491AD0
CORE_HOOK = 0x00491C62
CORE_HOOK_ORIGINAL = bytes.fromhex("E8 B9 D3 FF FF")  # call 0048F020 (random)
RANDOM = 0x0048F020
CORE_VANILLA_RESUME = 0x00491C67
CORE_RESULT_RESUME = 0x00491CC4  # after `mov esi, eax; sar esi, 8`
CASTER_MAG = 0x01D27BCF  # + caster index x 0xD0

CAVE = 0x027AB000
FLAG = 0x027AB100
CAP = formulae_rework.MITIGATION_CAP

ASSEMBLY = f"""
magic_call:
    mov byte ptr [{FLAG:#x}], 1
    push dword ptr [esp + 16]
    push dword ptr [esp + 16]
    push dword ptr [esp + 16]
    push dword ptr [esp + 16]
    call {DAMAGE_ROUTINE:#x}
    add esp, 16
    mov byte ptr [{FLAG:#x}], 0
    ret
core:
    cmp byte ptr [{FLAG:#x}], 0
    jne reworked
    call {RANDOM:#x}
    push {CORE_VANILLA_RESUME:#x}
    ret
reworked:
    lea eax, [ebx + ebx*2]
    lea eax, [ebx + eax*4]
    shl eax, 4
    movzx eax, byte ptr [eax + {CASTER_MAG:#x}]
    imul eax, ebp
    mov ecx, edi
    cmp ecx, {CAP}
    jbe capped
    mov ecx, {CAP}
capped:
    mov edx, 100
    sub edx, ecx
    imul eax, edx
    xor edx, edx
    mov ecx, 100
    div ecx
    mov esi, eax
    push {CORE_RESULT_RESUME:#x}
    ret
"""

# Assembled at CAVE from ASSEMBLY; tests/ff8/test_ff8_magic_damage_rework.py
# re-assembles it (keystone) and runs it under unicorn.
CODE = bytes.fromhex(
    "C6 05 00 B1 7A 02 01 FF 74 24 10 FF 74 24 10 FF"
    "74 24 10 FF 74 24 10 E8 B4 6A CE FD 83 C4 10 C6"
    "05 00 B1 7A 02 00 C3 80 3D 00 B1 7A 02 00 75 0B"
    "E8 EB 3F CE FD 68 67 1C 49 00 C3 8D 04 5B 8D 04"
    "83 C1 E0 04 0F B6 80 CF 7B D2 01 0F AF C5 89 F9"
    "83 F9 4B 76 05 B9 4B 00 00 00 BA 64 00 00 00 29"
    "CA 0F AF C2 31 D2 B9 64 00 00 00 F7 F1 89 C6 68"
    "C4 1C 49 00 C3"
)
ENTRY = {
    "magic_call": 0x027ab000,
    "core": 0x027ab027,
}


def _assemble() -> tuple[bytes, dict[str, int]]:
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    code = bytes(ks.asm(ASSEMBLY, CAVE)[0])
    entry = {}
    for name in ("magic_call", "core"):
        probe = ASSEMBLY.split(f"\n{name}:")[0] + f"\n{name}:\n nop"
        entry[name] = CAVE + len(ks.asm(probe, CAVE)[0]) - 1
    return code, entry


def _call(site: int, target: int) -> bytes:
    return b"\xE8" + (target - (site + 5)).to_bytes(4, "little", signed=True)


def _jump(site: int, target: int) -> bytes:
    return b"\xE9" + (target - (site + 5)).to_bytes(4, "little", signed=True)


def build_hext(enabled: bool) -> str:
    """The patch, or nothing: vanilla spell damage when the rework is off."""
    if not isinstance(enabled, bool):
        raise ValueError("Magic Damage Rework must be true or false")
    if not enabled:
        return ""
    return "\n".join((
        "# Formulae Rework: spell damage = spell power x MAG, less 1% per target SPR (max 75%).",
        f"{CAVE:X}:{len(CODE):X}",
        f"{CAVE:X} = {CODE.hex(' ').upper()}",
        f"{FLAG:X}:1",
        f"{FLAG:X} = 00",
        f"{MAGIC_CALL:X} = {_call(MAGIC_CALL, ENTRY['magic_call']).hex(' ').upper()}",
        f"{CORE_HOOK:X} = {_jump(CORE_HOOK, ENTRY['core']).hex(' ').upper()}",
        "",
    ))


def verified_hooks() -> list[tuple[int, bytes]]:
    return [(MAGIC_CALL, MAGIC_CALL_ORIGINAL), (CORE_HOOK, CORE_HOOK_ORIGINAL)]
