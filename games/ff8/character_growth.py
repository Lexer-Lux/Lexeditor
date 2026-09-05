"""Prevent edited standard-stat growth from wrapping a negative base into a stat byte.

Only STR, VIT, MAG and SPR bases are floored. Junctions, permanent bonuses and ability boosts
are added afterward by the unchanged native code.
"""
HOOK = 0x004966BB
ORIGINAL = bytes.fromhex('C1 FE 02 C1 E8 1F')
CAVE = 0x027A2800

def build_payload():
    code = bytearray(ORIGINAL)
    # At this point +24 is stat ID (STR..SPR=1..4). ESI is signed base.
    code.extend(bytes.fromhex('83 7C 24 24 01 72 0D 83 7C 24 24 04 77 06 85 F6 79 02 31 F6'))
    code.extend(b'\xE9'+(HOOK+len(ORIGINAL)-(CAVE+len(code)+5)).to_bytes(4,'little',signed=True))
    return bytes(code)

def build_hext():
    jump=b'\xE9'+(CAVE-(HOOK+5)).to_bytes(4,'little',signed=True)+b'\x90'
    payload=build_payload()
    return '\n'.join(('# Floor edited STR/VIT/MAG/SPR bases at zero before adding bonuses.',f'{CAVE:X}:{len(payload):X}',f'{HOOK:X} = {jump.hex(" ").upper()}',f'{CAVE:X} = {payload.hex(" ").upper()}',''))
