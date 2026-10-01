import struct

import pytest

from plugins.ff8 import assets


def container(blocks):
    offsets = [8 + 4 * len(blocks)]
    for block in blocks:
        offsets.append(offsets[-1] + len(block))
    return struct.pack(f'<{len(offsets) + 1}I', len(blocks), *offsets) + b''.join(blocks)


def test_shared_resources_preserve_texture_offset(monkeypatch):
    # Complete 16-bit TIM, so the PNG check needs no palette fixture.
    texture = struct.pack('<III4H2H', 16, 2, 16, 0, 0, 2, 1, 31, 992)
    font = struct.pack('<II', 8, 12) + bytes(4) + texture
    data = container([texture, font, b'AKAO' + bytes(60)])
    info = assets._battle_file_info('b0wave.dat', data)
    assert info['kind'] == 'battle-data'
    assert [section['name'] for section in info['sections']] == ['Battle effect textures', 'Battle font', 'Sound data']
    assert info['tims'][0]['offset'] == 20
    monkeypatch.setattr(assets, 'ensure_character_models', lambda: None)
    monkeypatch.setattr(assets, '_model_bytes', lambda *args: (data, None))
    assert assets.texture_png_bytes('battle/b0wave.dat#0') == assets.tim_png_bytes(texture)
    invalid = bytearray(data)
    struct.pack_into('<I', invalid, 20 + len(texture) + 4, len(font))
    assert assets._battle_file_info('b0wave.dat', invalid)['kind'] == 'unmapped'


def test_victory_nested_sections_are_bounded():
    fanfare = container([b'AKAO' + bytes(12), b'AKAO' + bytes(12)])
    camera = struct.pack('<4H', 2, 8, 12, 16) + bytes(8)
    blocks = [fanfare, camera] + [container([bytes(4)] * count) for count in (3, 3, 3, 2, 3, 2)]
    data = container(blocks)
    info = assets._battle_file_info('r0win.dat', data)
    assert info['kind'] == 'battle-data'
    assert info['counts'] is None and not info['tims']
    assert [section['index'] for section in info['sections']] == list(range(1, 21))
    assert info['sections'][4]['name'] == 'Rinoa: body animation'
    assert info['sections'][-1]['name'] == 'Kiros: animation sequence'
    for offset in (info['sections'][4]['offset'] - 12, 40 + len(fanfare) + 6):
        invalid = bytearray(data)
        struct.pack_into('<H', invalid, offset, 65535)
        assert assets._battle_file_info('r0win.dat', invalid)['kind'] == 'unmapped'


@pytest.mark.parametrize('signature,offset', [(b'AKAO', 0), (b'SCOT', 4)])
def test_sound_container_needs_a_complete_payload(signature, offset, monkeypatch, tmp_path):
    data = bytearray(80)
    data[offset:offset + 4] = signature
    struct.pack_into('<I', data, 16, 16)
    struct.pack_into('<I', data, 24, 64)
    info = assets._battle_file_info('mag076_b.02', bytes(data))
    assert info['kind'] == 'sound-data'
    assert info['counts'] is None and info['tims'] == []
    assert info['sections'][1] == {'index': 2, 'name': 'Sound data', 'offset': 64, 'size': 16}
    for invalid in (data[:32], data[:-1], data + b'junk'):
        assert not assets._battle_file_info('mag076_b.02', bytes(invalid))['parsed']
    target = tmp_path / 'mag005_b.08'
    target.write_bytes(data)
    monkeypatch.setattr(assets, '_battle_path', lambda *args: target)
    row = assets._model_row(target.name, 'vanilla', {target.name: len(data)}, set())
    assert row['modelKind'] == 'sound-data'
    assert row['summonFamily'] is None


def test_formation_file_keeps_its_editor_link(monkeypatch, tmp_path):
    monkeypatch.setattr(assets.paths, 'GAME_ROOT', tmp_path)
    monkeypatch.setattr(assets, '_battle_path', lambda *args: tmp_path / 'absent')
    row = assets._model_row('scene.out', 'vanilla', {'scene.out': 131072}, set())
    assert row['modelKind'] == 'formations'
    assert row['editor'] == 'encounters'
    assert row['counts'] is None
