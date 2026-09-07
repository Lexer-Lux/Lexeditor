"""Verify that the packaged PE32 FFNx driver contains Modern Controls #330.

This is deliberately an artifact test: source-only presence is insufficient for
native features. It verifies the x86 image architecture plus the executable seam
and native state addresses consumed by the compiled battle-camera hook.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import struct

ADDRESSES = {
    'battle update call site': 0x00500988,
    'native updateBattleCamera': 0x00504060,
    'active camera sequence': 0x01D99A34,
    'camera action flags': 0x01D97718,
    'camera handoff blend': 0x01D9771E,
    'live camera position': 0x00B8B7F0,
    'idle camera position': 0x00B8B800,
    'idle camera look-at': 0x00B8B808,
}
STRINGS = (
    b'unsupported battle-camera call site',
    b'analog camera update installed (world=%u battle=%u)',
)


def run(driver: Path) -> None:
    import pefile
    pe = pefile.PE(str(driver), fast_load=False)
    assert pe.FILE_HEADER.Machine == 0x14C, 'Modern Controls must ship in the x86 FFNx driver'
    image = pe.get_memory_mapped_image()
    for label, address in ADDRESSES.items():
        encoded = struct.pack('<I', address)
        assert encoded in image, f'Shipped driver does not reference {label} ({address:#x})'
    for marker in STRINGS:
        assert marker in image, f'Shipped driver is missing Modern Controls diagnostic: {marker!r}'
    print('PASS: shipped PE32 driver contains the #330 hook site, native camera ownership/pose addresses, and battle-camera diagnostics.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path, required=True)
    args = parser.parse_args()
    run(args.driver)
