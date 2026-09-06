"""Portable byte-level contracts for the RDR1 owned-horse map icon transform."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.rdr import map_icon_features as icons


def mip_bytes(width: int, height: int, levels: int, block: int) -> int:
    total = 0
    for level in range(levels):
        w = max(1, width >> level)
        h = max(1, height >> level)
        total += max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * block
    return total


def fixture(format_name='DXT5', width=2048, height=2048, levels=10):
    total_virtual = 8 * 1024 * 1024
    decoded = bytearray([0xCD]) * total_virtual
    # 32 x 256 KiB virtual pages. Object-start page = 256 KiB => first page / offset zero.
    flag1 = 32 << 8
    flag2 = (1 << 31) | (6 << 28) | (total_virtual >> 12)
    packed = bytearray(16)
    packed[:4] = b'RSC\x85'
    struct.pack_into('<III', packed, 4, 10, flag1, flag2)

    hash_ptr = 0x100
    list_ptr = 0x110
    texture_ptr = 0x200
    name_ptr = 0x300
    data_ptr = 0x1000
    struct.pack_into('<I', decoded, 0x10, 0x50000000 | hash_ptr)
    struct.pack_into('<HH', decoded, 0x14, 1, 1)
    struct.pack_into('<I', decoded, 0x18, 0x50000000 | list_ptr)
    struct.pack_into('<HH', decoded, 0x1C, 1, 1)
    struct.pack_into('<I', decoded, hash_ptr, 0x12345678)
    struct.pack_into('<I', decoded, list_ptr, 0x50000000 | texture_ptr)
    size = mip_bytes(width, height, levels, 16 if format_name != 'DXT1' else 8)
    struct.pack_into('<I', decoded, texture_ptr + 0x14, size)
    struct.pack_into('<I', decoded, texture_ptr + 0x18, 0x50000000 | name_ptr)
    struct.pack_into('<I', decoded, texture_ptr + 0x1C, 0)
    struct.pack_into('<HH', decoded, texture_ptr + 0x20, width, height)
    decoded[texture_ptr + 0x24:texture_ptr + 0x28] = format_name.encode().ljust(4, b'\0')
    decoded[texture_ptr + 0x28] = 0
    struct.pack_into('<H', decoded, texture_ptr + 0x29, 0)
    decoded[texture_ptr + 0x2B] = levels
    struct.pack_into('<I', decoded, texture_ptr + 0x44, 0)
    struct.pack_into('<I', decoded, texture_ptr + 0x48, 0)
    struct.pack_into('<I', decoded, texture_ptr + 0x4C, 0x50000000 | data_ptr)
    decoded[name_ptr:name_ptr + len(b'allblips.dds\0')] = b'allblips.dds\0'
    decoded[data_ptr:data_ptr + size] = bytes([0x7A]) * size
    return bytes(decoded), bytes(packed), data_ptr, size


def assert_patch(format_name):
    decoded, packed, data_ptr, size = fixture(format_name=format_name)
    rows = icons.parse_texture_dictionary(decoded, packed)
    assert len(rows) == 1
    tex = rows[0]
    assert tex['canonical'] == 'allblips' and tex['width'] == 2048 and tex['height'] == 2048
    assert tex['dataOffset'] == data_ptr and tex['format'] == format_name
    patched, report = icons.patch_owned_horse_sprite(decoded, tex)
    assert report['spriteOrdinal'] == 31 and report['cell'] == {'column': 15, 'row': 1, 'size': 128}
    assert report['changedBlocks'] > 0
    assert any(row['level'] == 5 and row['tile'] == 4 and row['patched'] for row in report['mipLevels'])
    assert any(row['level'] == 6 and row['tile'] == 2 and not row['patched'] for row in report['mipLevels'])
    assert decoded[:data_ptr] == patched[:data_ptr]
    assert decoded[data_ptr + size:] == patched[data_ptr + size:]

    # A neighboring sprite block on level zero must remain byte-identical.
    block = 8 if format_name == 'DXT1' else 16
    blocks_w = 2048 // 4
    # Sprite 30 is immediately left of sprite 31: row 1, col 14.
    neighbor_x = 14 * 128
    neighbor_y = 1 * 128
    pos = data_ptr + ((neighbor_y // 4) * blocks_w + (neighbor_x // 4)) * block
    assert decoded[pos:pos + block] == patched[pos:pos + block]

    # The first block of horse sprite 31 changes.
    horse_x = 15 * 128
    horse_y = 1 * 128
    horse = data_ptr + ((horse_y // 4) * blocks_w + (horse_x // 4)) * block
    # Top-left can be transparent in both synthetic and generated data, so prove
    # at least one block in the sprite differs instead of relying on that corner.
    sprite_blocks = []
    for by in range(32):
        for bx in range(32):
            at = data_ptr + (((horse_y // 4) + by) * blocks_w + (horse_x // 4) + bx) * block
            sprite_blocks.append(decoded[at:at + block] != patched[at:at + block])
    assert any(sprite_blocks)

    # Deterministic output: same installed bytes always generate the same candidate.
    again, report2 = icons.patch_owned_horse_sprite(decoded, tex)
    assert again == patched and report2 == report


def expect_error(label, decoded, packed, wanted):
    try:
        rows = icons.parse_texture_dictionary(decoded, packed)
        icons.patch_owned_horse_sprite(decoded, rows[0])
    except (ValueError, RuntimeError) as error:
        assert wanted in str(error), (label, error)
    else:
        raise AssertionError(f'{label} unexpectedly succeeded')


def main():
    for format_name in ('DXT1', 'DXT3', 'DXT5'):
        assert_patch(format_name)

    wrong, packed, _, _ = fixture(width=1024, height=1024)
    expect_error('wrong dimensions', wrong, packed, 'Expected 2048x2048')
    crnd, packed, _, _ = fixture(format_name='CRND')
    expect_error('crnd refusal', crnd, packed, 'unsupported')

    print('PASS RDR horse icon: allblips-31 only, DXT1/3/5 mips deterministic, neighboring blips preserved, unsafe layouts rejected')


if __name__ == '__main__':
    main()
