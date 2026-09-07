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

    # Every production Battle_applyDamage call is wrapped, while the original
    # 48FE20 function remains intact for the wrapper to call. Its target index
    # is converted with the same D0 actor stride.
    for site in DAMAGE_CALLS:
        assert call_target(exe, site) == 0x48FE20, hex(site)
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

    print('Reptile ATB native seam: battle reset, D0 ATB increment, all damage calls, HIT_ELEMENT and scene enemy identity passed')


if __name__ == '__main__':
    main()
