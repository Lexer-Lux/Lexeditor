"""Artifact-level verifier for the compiled FF8 Reptile ATB runtime."""
from __future__ import annotations
import argparse
from pathlib import Path
import struct

ADDRESSES = {
    'scene-load reset call': 0x0047D539,
    'ATB increment seam': 0x004843CF,
    'Battle_applyDamage': 0x0048FE20,
    'HIT_ELEMENT': 0x01D2A239,
    'scene enemy identities': 0x01D287DC,
}
EXPORTS = {
    b'lexeditor_ff8_reptile_atb_increment',
    b'lexeditor_ff8_reptile_atb_contract_version',
}


def run(driver: Path) -> None:
    import pefile
    pe = pefile.PE(str(driver), fast_load=False)
    assert pe.FILE_HEADER.Machine == 0x14C, 'Reptile ATB must ship in the x86 FFNx driver'
    image = pe.get_memory_mapped_image()
    for label, address in ADDRESSES.items():
        assert struct.pack('<I', address) in image, f'Shipped driver does not reference {label} ({address:#x})'
    assert b'Reptile ATB: cumulative Ice 0.92 / Fire 1.08 enemy speed runtime installed.' in image
    names = {symbol.name for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols if symbol.name}
    missing = EXPORTS - names
    assert not missing, f'Shipped driver lacks Reptile ATB exports: {sorted(missing)}'
    print('PASS: shipped PE32 driver contains the #323 reset/damage/ATB seams, element/scene addresses, diagnostics and runtime exports.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path, required=True)
    args = parser.parse_args()
    run(args.driver)
