"""Executable-backed evidence for the FF8 Modern Controls vehicle seam.

Requires a user-supplied supported Steam English FF8_EN.exe. No executable is
stored or uploaded by this verifier.
"""
from pathlib import Path
import argparse
import hashlib

EXPECTED = '064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
BASE = 0x400000


def at(exe: bytes, address: int, size: int) -> bytes:
    start = address - BASE
    return exe[start:start + size]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    args = parser.parse_args()
    exe = args.exe.read_bytes()
    digest = hashlib.sha256(exe).hexdigest()
    assert digest == EXPECTED, f'Unsupported FF8_EN.exe sha256: {digest}'

    # World_HandleInputs sends Ragnarok (0x32), cars (0x20..0x28 / 0x84), and
    # mobile Garden (0x30) through the same forward/reverse block.
    assert at(exe, 0x557434, 31) == bytes.fromhex(
        '83 F8 32 74 1A 83 F8 20 7C 05 83 F8 28 7E 10 '
        '3D 84 00 00 00 74 09 83 F8 30 0F 85 02 02 00 00')

    # The block reads world_input_states[world_input_frame_parity], then gives
    # Triangle and Square hard full-speed priority over analog rY. Modern
    # Controls snapshots Square, removes those two legacy drive bits, and feeds
    # the same rY consumer from proportional triggers instead.
    assert at(exe, 0x557453, 14) == bytes.fromhex(
        '0F BF 05 BC 09 04 02 8B 1C 85 E8 FD 03 02')
    assert at(exe, 0x557461, 11) == bytes.fromhex(
        'F6 C3 10 74 06 C6 46 0B 81 EB 30')
    assert at(exe, 0x55746C, 11) == bytes.fromhex(
        'F6 C3 80 74 06 C6 46 0B 7F EB 25')
    assert at(exe, 0x557477, 12) == bytes.fromhex(
        '8B 0D A4 09 04 02 83 F9 FF 74 1A 8D')
    # Native dead zone is 45 before converting raw rY to signed movement.
    assert at(exe, 0x557490, 12) == bytes.fromhex(
        '83 F8 2D 7E 07 B2 7F 2A D1 88 56 0B')

    # Input_WritePsxPadButtons copies the low 16-bit game-pad mask active-low
    # into the emulated PSX buffer without reordering bits. This corroborates
    # the engine's remapped PSX layout used by the helper constants.
    assert at(exe, 0x56D99F, 17) == bytes.fromhex(
        'C1 E9 08 F6 D1 88 0A 8B 0D E4 CE 09 02 F6 D0 88 01')

    print('Vehicle drive native seam: supported vehicle dispatch, Triangle/Square priority, world input buffer and rY consumer passed')


if __name__ == '__main__':
    main()
