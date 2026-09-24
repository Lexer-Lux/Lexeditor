"""Triple Triad's 4-bit texture uses its own cells and palette rows."""
from io import BytesIO
import struct
from unittest.mock import patch

import pytest
from PIL import Image

from plugins.ff8 import card_art


def texture():
    data = bytearray(8 + 3084 + 73740)
    struct.pack_into('<III4H', data, 0, 16, 8, 3084, 0, 0, 48, 32)
    header = 8 + 3084
    struct.pack_into('<I4H', data, header, 73740, 0, 0, 192, 192)
    for x, y, palette in card_art.ELEMENT_CELLS.values():
        struct.pack_into('<HH', data, 20 + (palette * 16 + 1) * 2, 31, 31 << 5)
        data[header + 12 + y * 384 + x // 2] = 0x21
    return data


def test_cells_palette_rows_nibbles_and_transparency():
    with patch.object(card_art, 'ICONS_TIM_OFFSET', 0), patch.object(
            card_art.executable_text, '_validate_executable') as validate:
        data = bytes(texture())
        images = card_art._render_elements(data)
        validate.assert_called_once_with(data)
    assert set(images) == {1, 2, 4, 8, 16, 32, 64, 128}
    for png in images.values():
        image = Image.open(BytesIO(png)).convert('RGBA')
        assert image.size == (16, 16)
        assert image.getpixel((0, 0)) == (255, 0, 0, 255)
        assert image.getpixel((1, 0)) == (0, 255, 0, 255)
        assert image.getpixel((2, 0)) == (0, 0, 0, 0)


def test_wrong_layout_is_rejected():
    data = texture()
    struct.pack_into('<I', data, 4, 9)
    with patch.object(card_art, 'ICONS_TIM_OFFSET', 0), patch.object(
            card_art.executable_text, '_validate_executable'), pytest.raises(ValueError):
        card_art._render_elements(bytes(data))


@pytest.mark.parametrize('value', [True, 0, 3, 256, '1'])
def test_invalid_element_does_not_read_game_files(value):
    with pytest.raises(ValueError):
        card_art.element_png_bytes(value)
