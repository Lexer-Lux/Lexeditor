"""Formulae Rework: melee damage = STR x weapon STR bonus x (power x 5%), less VIT.

Lexer's mod doc ("Final Fantasy VIII Mod (FF8)"): attacker STR x weapon STR
bonus x (attack power x 5%), then the target's VIT reduces it by 1% per
point, capped at 75%. Lexer's rule for enemies (#31): they have no weapon, so
their STR bonus counts as 1 and the attack's own power is the power.

Against FF8_EN.exe SHA-256 064d466b...9570, two routines compute melee
damage and both are replaced:

- Damage_ComputePhysicalCore (00492C40) for normal physical hits. At 00492C8F
  EDI is the attacker, EBP the attack power and EBX the target's VIT (already
  zero when the target ignores it); the vanilla result reaches 00492D01 in
  EAX with ESI reloaded to the target.
- The gunblade handler (0048F480) for Squall's attacks. At 0048F552 the
  attacker is [esp+0x14], the power [esp+0x1C], EBX the target's VIT and EBP
  the target. The trigger bonus stays native: the result is multiplied by
  (2 + trigger value / 20) / 2, the same factor vanilla applies, and resumes
  at 0048F5EC.

The party member's STR is the battle STR (+0xBD). The game has already added
the weapon's STR bonus to it when the stat was computed (00496440). The
weapon comes from the character block (01CFE0F0 + character x 0x98, weapon
at +1; Laguna, Kiros and Ward use 01CFE760..62 in the dream party, as the
stat routine does) and its STR bonus from the loaded weapon table (01CF7400
+ weapon x 12, byte +8). The formula has no random spread; everything after
it (the damage cap, element and sign handling) stays native.
"""

from __future__ import annotations

DEFAULT_MELEE_DAMAGE_REWORK = False

CORE_HOOK = 0x00492C8F
CORE_HOOK_ORIGINAL = bytes.fromhex("E8 8C C3 FF FF")  # call 0048F020 (random)
CORE_RESUME = 0x00492D01  # push eax: the result goes to the damage apply call
GUNBLADE_HOOK = 0x0048F552
GUNBLADE_HOOK_ORIGINAL = bytes.fromhex("E8 C9 FA FF FF")  # call 0048F020 (random)
GUNBLADE_RESUME = 0x0048F5EC
TRIGGER_VALUE = 0x01D28D94  # signed word; vanilla uses (2 + value / 20) / 2

PARTY_CHARACTER = 0x01CFE74C  # + party slot: character block index
CHARACTER_BLOCK = 0x01CFE0F0  # + character x 0x98; +0 id, +1 weapon
DREAM_FLAG = 0x01CFE97A  # bit 1: Laguna's party uses the dream weapons
DREAM_WEAPON = 0x01CFE760  # + (id - 8) for Laguna, Kiros and Ward
WEAPON_STR_BONUS = 0x01CF7408  # + weapon x 12
ATTACKER_STR = 0x01D27BCD  # + participant x 0xD0
ENEMY_STR_BONUS = 1
CAP = 75

CAVE = 0x027AB400

ASSEMBLY = f"""
core:
    push ebx
    push ebp
    push edi
    call melee
    mov esi, dword ptr [esp + 0x18]
    push {CORE_RESUME:#x}
    ret
gunblade:
    mov esi, dword ptr [esp + 0x14]
    mov edi, dword ptr [esp + 0x1c]
    push ebx
    push edi
    push esi
    call melee
    mov ecx, eax
    movsx eax, word ptr [{TRIGGER_VALUE:#x}]
    cdq
    mov ebx, 20
    idiv ebx
    add eax, 2
    imul eax, ecx
    cdq
    sub eax, edx
    sar eax, 1
    push {GUNBLADE_RESUME:#x}
    ret
melee:
    mov eax, dword ptr [esp + 4]
    cmp eax, 3
    jae enemy
    movzx ecx, byte ptr [eax + {PARTY_CHARACTER:#x}]
    imul ecx, ecx, 0x98
    movzx edx, byte ptr [ecx + {CHARACTER_BLOCK + 1:#x}]
    test byte ptr [{DREAM_FLAG:#x}], 1
    je weapon
    movzx ecx, byte ptr [ecx + {CHARACTER_BLOCK:#x}]
    sub ecx, 8
    cmp ecx, 2
    ja weapon
    movzx edx, byte ptr [ecx + {DREAM_WEAPON:#x}]
weapon:
    lea edx, [edx + edx*2]
    movzx ecx, byte ptr [edx*4 + {WEAPON_STR_BONUS:#x}]
    jmp bonus
enemy:
    mov ecx, {ENEMY_STR_BONUS}
bonus:
    mov eax, dword ptr [esp + 4]
    lea edx, [eax + eax*2]
    lea edx, [eax + edx*4]
    shl edx, 4
    movzx eax, byte ptr [edx + {ATTACKER_STR:#x}]
    imul eax, ecx
    imul eax, dword ptr [esp + 8]
    imul eax, eax, 5
    xor edx, edx
    mov ecx, 100
    div ecx
    mov ecx, dword ptr [esp + 12]
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
    ret 12
"""

# Assembled at CAVE from ASSEMBLY; tests/ff8/test_ff8_melee_damage_rework.py
# re-assembles it (keystone) and runs it under unicorn.
CODE = bytes.fromhex(
    "53 55 57 E8 3C 00 00 00 8B 74 24 18 68 01 2D 49"
    "00 C3 8B 74 24 14 8B 7C 24 1C 53 57 56 E8 22 00"
    "00 00 89 C1 0F BF 05 94 8D D2 01 99 BB 14 00 00"
    "00 F7 FB 83 C0 02 0F AF C1 99 29 D0 D1 F8 68 EC"
    "F5 48 00 C3 8B 44 24 04 83 F8 03 73 40 0F B6 88"
    "4C E7 CF 01 69 C9 98 00 00 00 0F B6 91 F1 E0 CF"
    "01 F6 05 7A E9 CF 01 01 74 16 0F B6 89 F0 E0 CF"
    "01 83 E9 08 83 F9 02 77 07 0F B6 91 60 E7 CF 01"
    "8D 14 52 0F B6 0C 95 08 74 CF 01 EB 05 B9 01 00"
    "00 00 8B 44 24 04 8D 14 40 8D 14 90 C1 E2 04 0F"
    "B6 82 CD 7B D2 01 0F AF C1 0F AF 44 24 08 6B C0"
    "05 31 D2 B9 64 00 00 00 F7 F1 8B 4C 24 0C 83 F9"
    "4B 76 05 B9 4B 00 00 00 BA 64 00 00 00 29 CA 0F"
    "AF C2 31 D2 B9 64 00 00 00 F7 F1 C2 0C 00"
)
ENTRY = {
    "core": 0x027ab400,
    "gunblade": 0x027ab412,
}


def _assemble() -> tuple[bytes, dict[str, int]]:
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    code = bytes(ks.asm(ASSEMBLY, CAVE)[0])
    entry = {}
    for name in ("core", "gunblade"):
        # A stub `melee` label keeps the earlier `call melee` resolvable; a
        # rel32 call is five bytes wherever the label lands.
        probe = ASSEMBLY.split(f"\n{name}:")[0] + f"\n{name}:\n nop\nmelee:\n nop"
        entry[name] = CAVE + len(ks.asm(probe, CAVE)[0]) - 2
    return code, entry


def _jump(site: int, target: int) -> bytes:
    return b"\xE9" + (target - (site + 5)).to_bytes(4, "little", signed=True)


def gunblade_damage(melee: int, trigger_value: int) -> int:
    """The native trigger factor applied to the reworked melee damage."""
    factor = int(trigger_value / 20) + 2
    return int(melee * factor / 2)


def build_hext(enabled: bool) -> str:
    """The patch, or nothing: vanilla melee damage when the rework is off."""
    if not isinstance(enabled, bool):
        raise ValueError("Melee Damage Rework must be true or false")
    if not enabled:
        return ""
    return "\n".join((
        "# Formulae Rework: melee = STR x weapon STR bonus (1 for enemies) x power x 5%, less 1% per VIT (max 75%).",
        f"{CAVE:X}:{len(CODE):X}",
        f"{CAVE:X} = {CODE.hex(' ').upper()}",
        f"{CORE_HOOK:X} = {_jump(CORE_HOOK, ENTRY['core']).hex(' ').upper()}",
        f"{GUNBLADE_HOOK:X} = {_jump(GUNBLADE_HOOK, ENTRY['gunblade']).hex(' ').upper()}",
        "",
    ))


def verified_hooks() -> list[tuple[int, bytes]]:
    return [(CORE_HOOK, CORE_HOOK_ORIGINAL), (GUNBLADE_HOOK, GUNBLADE_HOOK_ORIGINAL)]
