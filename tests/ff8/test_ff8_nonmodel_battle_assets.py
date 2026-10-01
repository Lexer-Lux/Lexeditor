import struct

import pytest

from plugins.ff8 import assets


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
