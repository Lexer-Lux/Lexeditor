"""An unsupported camera must not stop discovery of Triple Triad players."""
import json
from unittest.mock import patch

from plugins.ff8 import field_data, field_camera


def test_card_scan_preserves_unsupported_camera(tmp_path):
    row = {'key': 'group/map', 'group': 'group', 'name': 'map'}
    folder = tmp_path / field_data.BASELINE_SUBDIR / 'group/map'
    folder.mkdir(parents=True)
    (folder / 'map.jsm').write_bytes(b'script')
    (folder / 'map.ca').write_bytes(b'unsupported')
    (folder / '.source.json').write_text(json.dumps({
        'version': field_data.MAP_CACHE_VERSION, 'source': 'fixture',
        'assets': ['jsm', 'ca']}))
    with patch.object(field_data.paths, 'BASELINE_ROOT', tmp_path), \
         patch.object(field_data, '_fingerprint', return_value='fixture'), \
         patch.object(field_data, 'ensure_index', return_value={'rows': [row]}), \
         patch.object(field_data, '_parse_card_players', return_value=[{'id': 1, 'entity': 2, 'script': 3}]), \
         patch.dict(field_data._card_scan, {'keys': None, 'players': [], 'error': None}):
        field_data._card_player_scan()
        assert field_data._card_scan['error'] is None
        assert field_data._card_scan['keys'] == ['group/map']
        assert field_data._card_scan['players'][0]['id'] == 1
    assert (folder / 'map.ca').read_bytes() == b'unsupported'
    import pytest
    with pytest.raises(ValueError, match='Unsupported field camera size'):
        field_camera.read(b'unsupported')
