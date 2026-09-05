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
    code.extend(bytes.fromhex('F7 86 8C 7B D2 01 00 01 00 00')); branch(0x74)
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
