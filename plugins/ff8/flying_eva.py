"""Flying EVA: subtract its penalty from the bounded physical hit chance."""
CAVE = 0x0279EF00

def build_payload(bonus: int) -> bytes:
    if isinstance(bonus, bool) or not isinstance(bonus, int) or not 0 <= bonus <= 100:
        raise ValueError('Flying EVA Bonus must be a whole number from 0 to 100')
    code = bytearray(bytes.fromhex('8A 8D D2 7B D2 01'))
    branches = []
    def branch(op):
        code.extend(bytes((op, 0))); branches.append(len(code)-1)
    code.extend(bytes.fromhex('81 FD 70 02 00 00')); branch(0x72)
    code.extend(bytes.fromhex('8B 95 10 7B D2 01 85 D2')); branch(0x74)
    code.extend(bytes.fromhex('8B 12 F6 82 F7 00 00 00 02')); branch(0x74)
    # 0048B661 tests weapon flag bit 0; 0048B670 sets battle bit 0x1000.
    # 0x0100 is a separate character-kernel flag, not the equipped weapon.
    code.extend(bytes.fromhex('F7 86 8C 7B D2 01 00 10 00 00')); branch(0x74)
    code.extend(bytes.fromhex('F7 86 18 7B D2 01 00 20 00 00')); branch(0x75)
    # EAX is attacker LUCK/2 - target LUCK; ECX is target EVA. No globals change.
    code.extend(bytes.fromhex('2B C1 0F B6 15 38 A2 D2 01 03 C2 83 F8 64 7E 05 B8 64 00 00 00'))
    code.extend(bytes((0x83, 0xE8, bonus)))
    def jump(target):
        code.extend(b'\xE9'+(target-(CAVE+len(code)+5)).to_bytes(4,'little',signed=True))
    jump(0x00492F0B)
    vanilla = len(code)
    jump(0x00492EFB)
    for offset in branches:
        code[offset] = vanilla-(offset+1)
    return bytes(code)

# Physical Attack (kernel attack type 1) and Squall's gunblade (type 10) do not
# use the routine above: FF8's damage switch at 004922E0 sends only types 34
# and 36 to 00492E10. Type 1 asks 00492B00 whether a 255 hit rate lands
# outright, then rolls in 00492BA0; the gunblade handler 0048F480 never rolls.
# These caves give all three the same penalty. A helper decides whether it
# applies: an enemy target with intrinsic Float, a melee attacker (battle bit
# 0x1000, set at 0048B670 from the weapon's melee flag), and no Float on the
# attacker. Assembled at PHYSICAL_CAVE by tests/verify_ff8_flying_physical.py,
# which also checks these bytes against a fresh assembly.
PHYSICAL_CAVE = 0x027A2880
PHYSICAL_BONUS_OFFSETS = (159, 266)
PHYSICAL_TEMPLATE = bytes.fromhex(
    '81 FA 70 02 00 00 72 36 51 8B 8A 10 7B D2 01 85'
    'C9 74 2A 8B 09 F6 81 F7 00 00 00 02 74 1F F7 80'
    '8C 7B D2 01 00 10 00 00 74 13 F7 80 18 7B D2 01'
    '00 20 00 00 75 07 59 B8 01 00 00 00 C3 59 31 C0'
    'C3 80 3D 38 A2 D2 01 FF 75 1A 52 8B 44 24 08 69'
    'C0 D0 00 00 00 E8 A6 FF FF FF 5A 85 C0 75 05 E9'
    '3E 02 CF FD E9 36 02 CF FD 8A 91 D2 7B D2 01 50'
    '52 89 CA 8B 44 24 0C 69 C0 D0 00 00 00 E8 7E FF'
    'FF FF 85 C0 5A 58 74 1D 29 D0 0F B6 0D 38 A2 D2'
    '01 01 C8 83 F8 64 7E 05 B8 64 00 00 00 83 E8 00'
    'E9 D1 02 CF FD E9 BC 02 CF FD 8D 54 6D 00 88 0D'
    '07 8E D2 01 50 52 51 69 D5 D0 00 00 00 8B 44 24'
    '14 69 C0 D0 00 00 00 E8 34 FF FF FF 85 C0 74 61'
    '8B 44 24 14 69 C0 D0 00 00 00 0F B6 80 D2 7B D2'
    '01 D1 E8 0F B6 8A D3 7B D2 01 29 C8 0F B6 8A D2'
    '7B D2 01 29 C8 0F B6 0D 38 A2 D2 01 01 C8 83 F8'
    '64 7E 05 B8 64 00 00 00 83 E8 00 79 02 31 C0 69'
    'C0 FF 00 00 00 99 B9 64 00 00 00 F7 F9 50 E8 7D'
    'C6 CE FD 25 FF 00 00 00 5A 85 D2 74 0C 39 C2 72'
    '08 59 5A 58 E9 77 CB CE FD 59 5A 58 31 C0 5D C3'
)
# site: (replacement, original bytes)
PHYSICAL_HOOKS = {
    0x00492B16: ("E9 A6 FD 30 02 90 90 90 90", "80 3D 38 A2 D2 01 FF 74 03"),
    0x00492BE0: ("E9 04 FD 30 02 90", "8A 91 D2 7B D2 01"),
    0x0048F526: ("E9 FF 33 31 02 90 90 90 90 90", "8D 54 6D 00 88 0D 07 8E D2 01"),
}


def build_physical_payload(bonus: int) -> bytes:
    build_payload(bonus)  # the same validation
    code = bytearray(PHYSICAL_TEMPLATE)
    for offset in PHYSICAL_BONUS_OFFSETS:
        code[offset] = bonus
    return bytes(code)
