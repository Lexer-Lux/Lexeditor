"""Prevent edited standard-stat growth from wrapping a negative base into a stat byte.

Only STR, VIT, MAG and SPR bases are floored. Junctions, permanent bonuses and ability boosts
are added afterward by the unchanged native code.
"""
HOOK = 0x004966C3
# After Max Spell's junction normalization range; neither patch overwrites the other.
ORIGINAL = bytes.fromhex('03 EE 03 D5 03 D7')
CAVE = 0x027A2800
ZERO_HOOK = 0x00496651
ZERO_ORIGINAL = bytes.fromhex('8B 74 24 1C 33 C9')
ZERO_CAVE = 0x027A2840
ZERO_COEFFICIENTS = (0, 1, 0, 1)

def zero_payload():
    # Explicit zero-growth coefficients. Skip the quadratic base only;
    # restore the weapon bonus register and continue junction normalization.
    code = bytearray(bytes.fromhex('81 3F 00 01 00 01 75 0B 31 F6 8B 7C 24 14'))
    code.extend(b'\xE9'+(0x4966A4-(ZERO_CAVE+len(code)+5)).to_bytes(4,'little',signed=True))
    code.extend(ZERO_ORIGINAL)
    code.extend(b'\xE9'+(ZERO_HOOK+6-(ZERO_CAVE+len(code)+5)).to_bytes(4,'little',signed=True))
    return bytes(code)


def build_payload():
    code = bytearray()
    # At this point +24 is stat ID (STR..SPR=1..4). ESI is signed base.
    code.extend(bytes.fromhex('83 7C 24 24 01 72 0D 83 7C 24 24 04 77 06 85 F6 79 02 31 F6'))
    code.extend(ORIGINAL)
    code.extend(b'\xE9'+(HOOK+len(ORIGINAL)-(CAVE+len(code)+5)).to_bytes(4,'little',signed=True))
    return bytes(code)

def build_hext():
    jump=b'\xE9'+(CAVE-(HOOK+5)).to_bytes(4,'little',signed=True)+b'\x90'
    payload=build_payload()
    return '\n'.join(('# Floor edited STR/VIT/MAG/SPR bases at zero before adding bonuses.',f'{CAVE:X}:{len(payload):X}',f'{HOOK:X} = {jump.hex(" ").upper()}',f'{CAVE:X} = {payload.hex(" ").upper()}',f'{ZERO_CAVE:X}:{len(zero_payload()):X}',f'{ZERO_HOOK:X} = '+(b'\xE9'+(ZERO_CAVE-ZERO_HOOK-5).to_bytes(4,'little',signed=True)+b'\x90').hex(' ').upper(),f'{ZERO_CAVE:X} = {zero_payload().hex(" ").upper()}',''))
