from types import SimpleNamespace
from io import BytesIO
import struct
import pytest
from PIL import Image

from plugins.ff8.effect_preview import material_state
from plugins.ff8 import effect_preview


def test_texture_preview_uses_selected_palette_and_rejects_invalid_bank(monkeypatch):
    texture_data = bytearray(56)
    struct.pack_into('<I', texture_data, 20, 48)
    struct.pack_into('<I', texture_data, 48, 4)
    texture_data[52:54] = bytes((1, 2))
    palette_data = bytearray(52 + 1024)
    struct.pack_into('<I', palette_data, 8, 48)
    struct.pack_into('<I', palette_data, 48, 4)
    struct.pack_into('<H', palette_data, 54, 31)
    struct.pack_into('<H', palette_data, 56, 31 << 5)
    struct.pack_into('<H', palette_data, 52 + 512 + 2, 31 << 10)
    description = {'textures': [{'id': 0, 'slot': 3, 'rect': (0, 0, 1, 1), 'depth': 8}],
                   'cluts': [{'id': 0, 'slot': 1, 'rect': (0, 0, 256, 2)}]}
    monkeypatch.setattr(effect_preview, '_texture_sources', lambda *args: (3, {3: texture_data, 1: palette_data}, description))
    options = effect_preview.texture_options('mag200_b.03', 'current')['rows'][0]
    assert options['palette'] == '0:0'
    assert len(options['palettes']) == 2
    first = Image.open(BytesIO(effect_preview.texture_png('mag200_b.03', 'current', 0, '0:0')))
    assert [first.getpixel((x, 0)) for x in range(2)] == [(255, 0, 0, 255), (0, 255, 0, 255)]
    second = Image.open(BytesIO(effect_preview.texture_png('mag200_b.03', 'current', 0, '0:1')))
    assert second.getpixel((0, 0)) == (0, 0, 255, 255)
    with pytest.raises(ValueError, match='outside'):
        effect_preview.texture_png('mag200_b.03', 'current', 0, '0:2')
    with pytest.raises(ValueError, match='Unknown summon texture'):
        effect_preview.texture_png('mag200_b.03', 'current', 1, '0:0')


def test_material_state_uses_first_mesh_appearance():
    bone = SimpleNamespace(props=[(2, 'tex_op', (0x52, 0x52, (0,))),
                                  (3, 'mesh', 8),
                                  (9, 'tex_op', (0x92, 0x92, (99, 100)))])
    description = {'textures': [{'rect': (384, 256, 64, 128), 'depth': 8}],
                   'cluts': [{'rect': (320, 224, 256, 1)}]}
    assert material_state(SimpleNamespace(bones=[bone]), 8, description) == (3, 150, 14356)
    assert material_state(SimpleNamespace(bones=[bone]), 9, description) is None
