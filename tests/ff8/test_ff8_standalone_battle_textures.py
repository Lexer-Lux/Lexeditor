import base64
import struct

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


def test_texture_preview_and_index_validation(monkeypatch):
    monkeypatch.setattr(assets, 'ensure_character_models', lambda: None)
    monkeypatch.setattr(assets, '_model_bytes', lambda *args: (image(), None))
    assert assets.texture_png_bytes('battle/mag046_b.1t0#0').startswith(b'\x89PNG')
    with pytest.raises(ValueError, match='index'):
        assets.texture_png_bytes('battle/mag046_b.1t0#1')
    with pytest.raises(ValueError):
        assets.texture_png_bytes('battle/../mag046_b.1t0#0')


def test_replace_texture_preserves_format_and_reverts(monkeypatch, tmp_path):
    monkeypatch.setattr(assets.paths, 'DIRECT_ROOT', tmp_path)
    monkeypatch.setattr(assets, '_battle_path', lambda *args: tmp_path / 'absent')
    monkeypatch.setattr(assets, '_battle_archive_index', lambda: [{'file': 'mag046_b.1t0'}])
    monkeypatch.setattr(assets, '_model_bytes', lambda *args: (image(), None))
    edit = {'file': 'mag046_b.1t0', 'datBase64': base64.b64encode(image()).decode()}
    assets.save_models([edit])
    target = tmp_path / 'battle' / edit['file']
    assert target.read_bytes() == image()
    with pytest.raises(ValueError, match='TIM image'):
        assets.save_models([{**edit, 'datBase64': base64.b64encode(b'invalid').decode()}])
    assert target.read_bytes() == image()
    assets.save_models([{'file': edit['file'], 'revert': True}])
    assert not target.exists()
