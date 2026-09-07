"""Executable-backed evidence for the FF8 Reptile ATB runtime seams.

Requires a user-supplied supported Steam English FF8_EN.exe. The executable is
never downloaded, copied into the repository, or uploaded by this verifier.
"""
from pathlib import Path
import argparse
import hashlib
import struct

EXPECTED = '064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
BASE = 0x400000
DAMAGE_CALLS = (0x4850FA, 0x4851F1, 0x48EA93, 0x48F3CB, 0x48F44C)
DAMAGE_UPDATE_CALLS = (0x485104, 0x485203, 0x48EA99, 0x48F3D5, 0x48F456)
ATTACK_HIT_COUNT_1 = 0x1D280C1


def at(exe: bytes, address: int, size: int) -> bytes:
    start = address - BASE
    return exe[start:start + size]


def call_target(exe: bytes, address: int) -> int:
    data = at(exe, address, 5)
    assert len(data) == 5 and data[0] == 0xE8, (hex(address), data.hex())
    return address + 5 + struct.unpack('<i', data[1:])[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    args = parser.parse_args()
    exe = args.exe.read_bytes()
    digest = hashlib.sha256(exe).hexdigest()
    assert digest == EXPECTED, f'Unsupported FF8_EN.exe sha256: {digest}'

    # Battle setup loads one scene.out record at a stable call site. The native
    # runtime resets cumulative modifiers immediately after this call.
    assert call_target(exe, 0x47D539) == 0x48D0E0

    # Native battle actors use a D0-byte stride. The ATB loop has already
    # calculated its integer increment in EDX at 4843CF; these six bytes add it
    # to Current ATB. Speed was read separately from actor +AD just beforehand.
    assert at(exe, 0x4843CF, 6) == bytes.fromhex('8B 0E 03 D1 89 16')
    assert at(exe, 0x4843A9, 6) == bytes.fromhex('8A 8E AD 00 00 00')
    assert at(exe, 0x484460, 7) == bytes.fromhex('81 C6 D0 00 00 00 47')

    # Every production Battle_applyDamage call is wrapped. Each path then calls
    # Battle_UpdateDamage, which reads ATTACK_HIT_COUNT_1, increments it, and
    # stores it back. Standard action setup explicitly resets the byte to zero.
    # This provides an action-native multi-hit boundary with no frame heuristic.
    for damage, update in zip(DAMAGE_CALLS, DAMAGE_UPDATE_CALLS):
        assert call_target(exe, damage) == 0x48FE20, hex(damage)
        assert call_target(exe, update) == 0x48EF80, hex(update)
    assert at(exe, 0x48EF80, 6) == bytes.fromhex('8A 0D C1 80 D2 01')
    assert at(exe, 0x48EF90, 5) == bytes.fromhex('FE C1 8D 04 40')
    assert at(exe, 0x48EF95, 6) == b'\x88\x0D' + struct.pack('<I', ATTACK_HIT_COUNT_1)
    assert at(exe, 0x4851E4, 7) == bytes.fromhex('C6 05 C1 80 D2 01 00')
    assert at(exe, 0x48FE2A, 10) == bytes.fromhex('8D 0C 40 57 8D 14 88 C1 E2 04')

    # Kernel Magic's element byte is record offset 14. Native copies that byte
    # directly into HIT_ELEMENT (1D2A239), which is therefore the resolved
    # element source consumed after Battle_applyDamage.
    assert at(exe, 0x48FFEC, 11) == bytes.fromhex('8A 87 2E 7D CF 01 A2 39 A2 D2 01')

    # scene.out enemy IDs begin at record +38 (1D28814). Battle initialization
    # copies slot N's ID into the corresponding runtime actor, proving target
    # slots 3..10 map to scene enemy slots 0..7. Lexeditor's monster schema uses
    # com_id = entity_id - 0x10, so no private actor field is needed.
    assert at(exe, 0x47DA79, 17) == bytes.fromhex(
        '8A 90 14 88 D2 01 8D 04 40 D1 E0 88 96 CB 7B D2 01')

    print('Reptile ATB native seam: battle reset, D0 ATB increment, damage/update pairs, native hit counter, HIT_ELEMENT and scene enemy identity passed')


if __name__ == '__main__':
    main()
