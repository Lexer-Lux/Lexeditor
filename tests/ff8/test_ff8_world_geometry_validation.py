"""Terrain saves reject invalid batches before replacing the source file."""
import struct

import pytest

from plugins.ff8 import world_geometry
from test_ff8_world_mesh import terrain_segment


@pytest.fixture
def terrain_file(tmp_path, monkeypatch):
    path = tmp_path / world_geometry.DIRECT_RELATIVE
    path.parent.mkdir(parents=True)
    path.write_bytes(terrain_segment() * world_geometry.BASE_SEGMENT_COUNT)
    monkeypatch.setattr(world_geometry, 'source_path', lambda dataset: path)
    monkeypatch.setattr(world_geometry.paths, 'DIRECT_ROOT', tmp_path)
    return path


@pytest.mark.parametrize('field', ['id', 'groupId'])
@pytest.mark.parametrize('value', [True, False, .5, float('inf'), float('nan'), -1, '1.5'])
def test_rejected_batch_preserves_terrain(terrain_file, field, value):
    original = terrain_file.read_bytes()
    before = sorted(path.relative_to(terrain_file.parent) for path in terrain_file.parent.iterdir())
    edits = [{'id': 0, 'groupId': 99}, {'id': 1, 'groupId': 77, field: value}]
    with pytest.raises(ValueError):
        world_geometry.save(edits)
    assert terrain_file.read_bytes() == original
    assert sorted(path.relative_to(terrain_file.parent) for path in terrain_file.parent.iterdir()) == before


def test_valid_terrain_save_reloads_and_preserves_unknown_bytes(terrain_file):
    original = terrain_file.read_bytes()
    result = world_geometry.save([{'id': '1', 'groupId': 0xFFFFFFFF}])
    saved = terrain_file.read_bytes()
    offset = world_geometry.SEGMENT_SIZE
    assert result == {'saved': 1, 'file': str(terrain_file)}
    assert world_geometry.parse(saved)['segments'][1]['groupId'] == 0xFFFFFFFF
    assert struct.unpack_from('<I', saved, offset)[0] == 0xFFFFFFFF
    assert saved[:offset] == original[:offset]
    assert saved[offset + 4:] == original[offset + 4:]


@pytest.mark.parametrize('edit', [
    {'id': world_geometry.BASE_SEGMENT_COUNT, 'groupId': 7},
    {'id': 1, 'groupId': 0x100000000},
])
def test_out_of_range_terrain_save_preserves_source(terrain_file, edit):
    original = terrain_file.read_bytes()
    with pytest.raises(ValueError):
        world_geometry.save([{'id': 0, 'groupId': 99}, edit])
    assert terrain_file.read_bytes() == original
