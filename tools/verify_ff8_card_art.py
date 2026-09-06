"""Card-preview decoder/route regressions; synthetic data by default.

Optional --exe validates all 110 previews from a local supported game. No
assets, executable bytes, or generated pictures are written by this test.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import os
from pathlib import Path
import struct
import sys
import tempfile
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8 import card_art, server


def atlas() -> bytes:
    """Different palette/position values catch row/column and CLUT mistakes."""
    clut_size = 12 + 256 * 56 * 2
    image_header = card_art.TIM_OFFSET + 8 + clut_size
    image_size = 12 + 1792 * 256
    data = bytearray(image_header + image_size)
    struct.pack_into('<IIIHHHH', data, card_art.TIM_OFFSET, 0x10, 9, clut_size, 0, 0, 256, 56)
    for card in range(110):
        color = (card % 31 + 1) | ((card // 31 + 1) << 5) | (15 << 10)
        struct.pack_into('<H', data, card_art.TIM_OFFSET + 20 + (card * 128 + 1) * 2, color)
        x = (card // 8 * 2 + card % 2) * 64
        y = card % 8 // 2 * 64
        data[image_header + 12 + y * 1792 + x] = 1
    struct.pack_into('<IHHHH', data, image_header, image_size, 0, 0, 896, 256)
    return bytes(data)


def run(exe: Path | None = None) -> None:
    data = atlas()
    # Only the private executable signature check is stubbed for this fixture.
    with patch.object(card_art.executable_text, '_validate_executable'):
        palette, pixels = card_art._read_atlas(data)
        for card in range(110):
            image = Image.open(BytesIO(card_art._render_card(card, palette, pixels)))
            assert image.size == (64, 64) and image.mode == 'RGBA'
            assert image.getpixel((0, 0)) == palette[card * 128 + 1]
            assert image.getpixel((1, 0)) == (0, 0, 0, 0)
        for invalid in [True, -1, 110, 255, '1', None]:
            try:
                card_art._render_card(invalid, palette, pixels)
            except ValueError:
                pass
            else:
                raise AssertionError(f'Accepted invalid card {invalid!r}')
        for truncated in [b'', data[:card_art.TIM_OFFSET + 20], data[:-1]]:
            try:
                card_art._read_atlas(truncated)
            except (ValueError, struct.error):
                pass
            else:
                raise AssertionError('Accepted truncated atlas')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'FF8_EN.exe'
            target.write_bytes(data)
            card_art._cached_cards.cache_clear()
            first = card_art.png_bytes(0, root)
            assert card_art.png_bytes(0, root) == first
            assert card_art._cached_cards.cache_info().hits == 1
            stamp = target.stat()
            os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
            assert card_art.png_bytes(0, root) == first
            assert card_art._cached_cards.cache_info().misses == 2
    # A production call must still reject unverified executable offsets.
    try:
        card_art._read_atlas(data)
    except ValueError:
        pass
    else:
        raise AssertionError('Executable signature validation was skipped')
    card_art._cached_cards.cache_clear()
    print('PASS: all 110 atlas/CLUT positions, transparency, bounds, signature checks and cache invalidation')

    handler = object.__new__(server.Handler)
    delivered = []
    handler.binary_response = lambda content, kind: delivered.append((content, kind))
    handler.json_response = lambda content, status=200: delivered.append((content, status))
    with patch.object(server.card_art, 'png_bytes', return_value=b'PNG fixture') as read:
        handler.path = '/assets/cards/109.png'
        handler.do_GET()
        read.assert_called_once_with(109)
        assert delivered.pop() == (b'PNG fixture', 'image/png')
    for value in ['-1', '110', '255', 'abc']:
        handler.path = f'/assets/cards/{value}.png'
        handler.do_GET()
        assert delivered.pop()[1] == 400
    print('PASS: production card-preview route and invalid-ID responses')

    if exe:
        palette, pixels = card_art._read_atlas(exe.read_bytes())
        previews = [card_art._render_card(i, palette, pixels) for i in range(110)]
        assert len(set(previews)) == 110
        assert all(Image.open(BytesIO(image)).size == (64, 64) for image in previews)
        print('PASS: all 110 distinct previews decode from the supplied supported executable')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path)
    run(parser.parse_args().exe)
