"""Executable-backed evidence for the FF8 idle battle-camera hook seam.

This verifier needs a user-supplied supported Steam English FF8_EN.exe. It does
not download, copy or upload the executable and is intentionally not a public-CI
requirement.
"""
from pathlib import Path
import argparse
import hashlib
import struct

SUPPORTED_SHA256 = '064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
IMAGE_BASE = 0x400000


def at(exe: bytes, address: int, size: int) -> bytes:
    start = address - IMAGE_BASE
    return exe[start:start+size]


def call_target(exe: bytes, address: int) -> int:
    data = at(exe,address,5)
    assert len(data)==5 and data[0]==0xE8, (hex(address), data.hex())
    return address+5+struct.unpack('<i',data[1:])[0]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe',type=Path,required=True)
    args=parser.parse_args()
    exe=args.exe.read_bytes()
    digest=hashlib.sha256(exe).hexdigest()
    assert digest==SUPPORTED_SHA256, f'Unsupported FF8_EN.exe sha256: {digest}'

    # Main battle loop has one clean no-argument call to updateBattleCamera.
    assert at(exe,0x500988,5)==bytes.fromhex('E8 D3 36 00 00')
    assert call_target(exe,0x500988)==0x504060

    # updateBattleCamera advances sequence bytecode through BS_UpdateCameraSequence.
    assert call_target(exe,0x50406C)==0x509610
    # BS_UpdateCameraSequence owns a nullable current-sequence pointer and writes
    # its returned next pointer back each frame.
    assert at(exe,0x509610,7)==bytes.fromhex('A1 34 9A D9 01 85 C0')
    assert bytes.fromhex('A3 34 9A D9 01') in at(exe,0x509619,0x20)

    # Stable idle after native update is blend==0 plus the exact native
    # meaningful-flags mask (0xFFFFDFFF). The 0x2000 bit is ignored by FF8.
    block=at(exe,0x50407B,0x50)
    assert bytes.fromhex('8B 0D 18 77 D9 01') in block
    assert bytes.fromhex('66 A1 1E 77 D9 01') in block
    assert bytes.fromhex('F7 C1 FF DF FF FF') in block

    # Handoff branch copies default/rest position and look-at into the live
    # registers, then clears the blend. This is why the post-hook can adopt the
    # returned default pose and never retain a stale manual baseline.
    handoff=at(exe,0x504189,0x51)
    for pattern in (
        '8B 15 00 B8 B8 00', # default position x/y -> edx
        'A1 04 B8 B8 00',    # default position z/pad -> eax
        '8B 0D 08 B8 B8 00', # default look-at x/y -> ecx
        '89 15 F0 B7 B8 00', # live position x/y
        'A3 F4 B7 B8 00',    # live position z/pad
        '89 0D F8 B7 B8 00', # live look-at x/y
        '89 15 FC B7 B8 00', # live look-at z/pad
        '66 C7 05 1E 77 D9 01 00 00', # blend=0
    ):
        assert bytes.fromhex(pattern) in handoff, pattern

    # The battle-camera vector math sign-extends x/y/z from offsets +0,+2,+4.
    # The +8 look-at register begins at B8B7F8, so each pose record is 8 bytes
    # (three signed words plus an untouched padding word).
    vector=at(exe,0x503350,0x35)
    assert bytes.fromhex('0F BF 0D F0 B7 B8 00') in vector
    assert bytes.fromhex('0F BF 05 F2 B7 B8 00') in vector
    assert bytes.fromhex('0F BF 15 FA B7 B8 00') in vector
    assert bytes.fromhex('0F BF 05 F8 B7 B8 00') in vector

    print('Battle camera native seam: call, sequence owner, stable-idle gate, default/live handoff and signed int16 XYZ vectors passed')


if __name__=='__main__':
    main()
