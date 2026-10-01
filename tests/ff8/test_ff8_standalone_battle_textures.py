import base64
import struct
from io import BytesIO

from PIL import Image

import pytest

from plugins.ff8 import assets


def image():
    palette = struct.pack('<IHHHH', 44, 0, 0, 16, 1) + struct.pack('<16H', *range(16))
    pixels = struct.pack('<IHHHH', 14, 0, 0, 1, 1) + b'\x12\x34'
    return struct.pack('<II', 16, 8) + palette + pixels


def test_complete_image_required():
    assert assets._standalone_texture_info(image())['tims'][0]['width'] == 4
    assert assets._standalone_texture_info(image() + b'extra') is None
    assert assets._standalone_texture_info(image()[:-1]) is None


def test_palette_rows_keep_their_stride():
    rows = [([31] * 256 + [31744] * 16), ([992] * 256 + [31744] * 16)]
    palette = struct.pack('<I4H', 12 + 272 * 2 * 2, 320, 224, 272, 2)
    palette += struct.pack('<544H', *(rows[0] + rows[1]))
    data = struct.pack('<II', 16, 9) + palette + struct.pack('<I4H', 14, 0, 0, 1, 1) + b'\x00\xff'
    assert assets._tim_layout(data)['paletteCount'] == 2
    for index, expected in enumerate(((255, 0, 0, 255), (0, 255, 0, 255))):
        rendered = Image.open(BytesIO(assets.tim_png_bytes(data, palette=index)))
        assert rendered.getpixel((0, 0)) == rendered.getpixel((1, 0)) == expected
    with pytest.raises(ValueError, match='Palette ID'):
        assets.tim_png_bytes(data, palette=2)


def test_texture_pack_requires_complete_bounded_images(monkeypatch):
    first = image()
    second = bytearray(first)
    second[-2:] = b'\x65\x87'
    data = first + second
    info = assets._battle_file_info('mag139_h.02', data)
    assert info['kind'] == 'texture'
    assert [tim['offset'] for tim in info['tims']] == [0, len(first)]
    assert assets._standalone_texture_info(data) is None
    for invalid in (data[:-1], data + b'junk', first * 129):
        assert assets._texture_pack_info(invalid) is None
    monkeypatch.setattr(assets, 'ensure_character_models', lambda: None)
    monkeypatch.setattr(assets, '_model_bytes', lambda *args: (data, None))
    assert assets.texture_png_bytes('battle/mag139_h.02#1') == assets.tim_png_bytes(bytes(second))
    assert assets.texture_png_bytes('battle/mag139_h.02#0') != assets.texture_png_bytes('battle/mag139_h.02#1')
    for index in (-1, 2):
        with pytest.raises(ValueError, match='index'):
            assets.texture_png_bytes(f'battle/mag139_h.02#{index}')


def test_unknown_container_exposes_only_complete_texture_sections(monkeypatch):
    texture = image()
    data = struct.pack('<4I', 2, 16, 16 + len(texture), 20 + len(texture)) + texture + b'data'
    info = assets._battle_file_info('b0wave.dat', data)
    assert info['kind'] == 'unmapped'
    assert [section['name'] for section in info['sections']] == ['Texture', 'Section 2']
    assert len(info['tims']) == 1 and info['tims'][0]['offset'] == 16
    monkeypatch.setattr(assets, 'ensure_character_models', lambda: None)
    monkeypatch.setattr(assets, '_model_bytes', lambda *args: (data, None))
    assert assets.texture_png_bytes('battle/b0wave.dat#0').startswith(b'\x89PNG')
    with pytest.raises(ValueError, match='index'):
        assets.texture_png_bytes('battle/b0wave.dat#1')


def test_texture_preview_and_index_validation(monkeypatch):
    monkeypatch.setattr(assets, 'ensure_character_models', lambda: None)
    monkeypatch.setattr(assets, '_model_bytes', lambda *args: (image(), None))
    assert assets.texture_png_bytes('battle/mag046_b.1t0#0').startswith(b'\x89PNG')
    with pytest.raises(ValueError, match='index'):
        assets.texture_png_bytes('battle/mag046_b.1t0#1')
    with pytest.raises(ValueError):
        assets.texture_png_bytes('battle/../mag046_b.1t0#0')


@pytest.mark.parametrize('count', [1, 3])
def test_replace_texture_preserves_format_and_reverts(monkeypatch, tmp_path, count):
    data = image() * count
    monkeypatch.setattr(assets.paths, 'DIRECT_ROOT', tmp_path)
    monkeypatch.setattr(assets, '_battle_path', lambda *args: tmp_path / 'absent')
    monkeypatch.setattr(assets, '_battle_archive_index', lambda: [{'file': 'mag046_b.1t0'}])
    monkeypatch.setattr(assets, '_model_bytes', lambda *args: (data, None))
    edit = {'file': 'mag046_b.1t0', 'datBase64': base64.b64encode(data).decode()}
    assets.save_models([edit])
    target = tmp_path / 'battle' / edit['file']
    assert target.read_bytes() == data
    with pytest.raises(ValueError, match='TIM image'):
        assets.save_models([{**edit, 'datBase64': base64.b64encode(b'invalid').decode()}])
    assert target.read_bytes() == data
    assets.save_models([{'file': edit['file'], 'revert': True}])
    assert not target.exists()
