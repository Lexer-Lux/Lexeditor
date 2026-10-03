"""Authored World files exercise rejected batches and valid byte-preserving saves."""
from copy import deepcopy
import base64
import json
import struct
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import world_map, world_textures


def world_fixture():
    sections = [bytes(4) for _ in range(world_map.SECTION_COUNT)]
    sections[0] = bytes(4) + struct.pack('<BBH', 1, 2, 0) + bytes(4)
    sections[1] = bytes(world_map.REGION_COUNT)
    sections[3] = struct.pack('<16H', *range(1, 17)) + bytes(4)
    sections[world_map.FIELD_RETURN_SECTION] = struct.pack('<iihh', 10, 20, 30, 0x1234) + bytes(4)
    sky = bytearray([0xA5] * world_map.SKY_RECORD_SIZE)
    struct.pack_into('<iii', sky, 0, 100, 200, 300)
    sections[world_map.SKY_SECTION] = struct.pack('<II', 8, 0) + sky
    sections[world_map.DRAW_SECTION] = bytes(world_map.DRAW_HEADER_SIZE) + bytes([1, 2, 3, 0xA5]) * world_map.DRAW_POINT_COUNT
    cursor = world_map.SECTION_COUNT * 4
    pointers = []
    for section in sections:
        pointers.append(cursor)
        cursor += len(section)
    return struct.pack(f'<{world_map.SECTION_COUNT}I', *pointers) + b''.join(sections)


def rail_fixture():
    raw = bytearray([0xA5] * world_map.RAIL_BLOCK_SIZE)
    struct.pack_into('<BBHII', raw, 0, 2, 0xA5, 0x1234, 0, 1)
    for index in range(2):
        struct.pack_into('<iiii', raw, 12 + index * 16, 10, 20, 30, 0x12345678)
    return bytes(raw)


def texture_fixture():
    slot = bytearray([0xA5] * world_textures.SLOT_SIZE)
    struct.pack_into('<II', slot, 0, 0x10, 9)
    struct.pack_into('<IHHHH', slot, 8, 1036, 0, 0, 256, 2)
    struct.pack_into('<IHHHH', slot, 1044, 65548, 0, 0, 128, 256)
    return bytes(slot) * world_textures.TEXTURE_COUNT


@pytest.fixture
def files(tmp_path, monkeypatch):
    wmset = tmp_path / world_map.DIRECT_RELATIVE
    rail = tmp_path / world_map.RAIL_DIRECT_RELATIVE
    wmset.parent.mkdir(parents=True)
    wmset.write_bytes(world_fixture())
    rail.write_bytes(rail_fixture())
    texture = tmp_path / world_textures.DIRECT_RELATIVE
    texture.write_bytes(texture_fixture())
    monkeypatch.setattr(world_map, 'source_path', lambda dataset: wmset)
    monkeypatch.setattr(world_map, 'rail_source_path', lambda dataset: rail)
    monkeypatch.setattr(world_map.paths, 'DIRECT_ROOT', tmp_path)
    monkeypatch.setattr(world_textures, 'source_path', lambda dataset: texture)
    return tmp_path, wmset, rail


def edits():
    sky = {**world_map.parse(world_fixture())['skyColors'][0], 'x': 101}
    track = world_map.parse_rail(rail_fixture())['tracks'][0]
    track['points'][0]['x'] = 11
    texture = bytearray(texture_fixture()[:world_textures.SLOT_SIZE])
    texture[1056] = 7
    used = world_textures._tim_layout(texture)['used']
    return {
        'region': {'kind': 'region', 'id': 0, 'regionId': 7},
        'helper': {'kind': 'helper', 'id': 0, 'regionId': 1, 'groundId': 2, 'encounterGroup': 1},
        'group': {'kind': 'group', 'id': 0, 'encounters': list(range(2, 10))},
        'drawPoint': {'kind': 'drawPoint', 'id': 0, 'x': 4, 'y': 5, 'subId': 6},
        'fieldReturn': {'kind': 'fieldReturn', 'id': 0, 'x': 11, 'y': 31, 'z': 21},
        'skyColor': sky,
        'railTrack': track,
        'worldTexture': {'kind': 'worldTexture', 'id': 0,
                         'timBase64': base64.b64encode(texture[:used]).decode('ascii')},
    }


CASES = [(kind, (key,)) for kind, keys in {
    'region': ['id', 'regionId'], 'helper': ['id', 'regionId', 'groundId', 'encounterGroup'],
    'group': ['id'], 'drawPoint': ['id', 'x', 'y', 'subId'],
    'fieldReturn': ['id', 'x', 'y', 'z'], 'skyColor': ['id', 'x', 'y', 'z'],
    'railTrack': ['id', 'trainStop1', 'trainStop2'],
    'worldTexture': ['id'],
}.items() for key in keys]
CASES += [('group', ('encounters', 0))]
CASES += [('skyColor', (key, 0)) for key, _ in world_map.SKY_COLOR_FIELDS]
CASES += [('railTrack', ('points', 0, key)) for key in ['id', 'x', 'y', 'z']]


def snapshot(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()}


@pytest.mark.parametrize('kind,path', CASES)
@pytest.mark.parametrize('value', [True, False, .5, float('inf'), float('nan'), '1.5'])
def test_invalid_world_batch_preserves_all_files(files, kind, path, value):
    root, _, _ = files
    before = snapshot(root)
    edit = deepcopy(edits()[kind])
    target = edit
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value
    # A valid edit in a different record family must not leak from rejection.
    first = edits()['drawPoint' if kind == 'region' else 'region']
    with pytest.raises(ValueError):
        world_map.save([first, edit])
    assert snapshot(root) == before


def test_world_valid_save_reloads_and_preserves_unknown_bytes(files):
    root, wmset, rail = files
    original = wmset.read_bytes()
    original_rail = rail.read_bytes()
    texture = root / world_textures.DIRECT_RELATIVE
    original_texture = texture.read_bytes()
    batch = list(edits().values())
    result = world_map.save(batch)
    saved = wmset.read_bytes()
    parsed = world_map.parse(saved)
    assert result['saved'] == len(batch)
    assert parsed['regions'][0]['regionId'] == 7
    assert parsed['helpers'][0]['encounterGroup'] == 1
    assert parsed['groups'][0]['encounters'] == list(range(2, 10))
    assert (parsed['drawPoints'][0]['x'], parsed['drawPoints'][0]['y'], parsed['drawPoints'][0]['subId']) == (4, 5, 6)
    assert (parsed['fieldReturns'][0]['x'], parsed['fieldReturns'][0]['y'], parsed['fieldReturns'][0]['z']) == (11, 31, 21)
    assert parsed['fieldReturns'][0]['unknown'] == 0x1234
    assert parsed['skyColors'][0]['x'] == 101
    pointers = world_map._pointers(original)
    changed = set()
    for start, length in [(pointers[1], 1), (pointers[0]+4, 4), (pointers[3], 16),
                          (pointers[world_map.DRAW_SECTION]+world_map.DRAW_HEADER_SIZE, 3),
                          (pointers[world_map.FIELD_RETURN_SECTION], 10),
                          (pointers[world_map.SKY_SECTION]+8, 4)]:
        changed.update(range(start, start+length))
    assert len(saved) == len(original)
    assert all(a == b for index, (a, b) in enumerate(zip(original, saved)) if index not in changed)
    saved_rail = rail.read_bytes()
    assert world_map.parse_rail(saved_rail)['tracks'][0]['points'][0]['x'] == 11
    assert saved_rail[:12] == original_rail[:12]
    assert saved_rail[16:] == original_rail[16:]
    saved_texture = texture.read_bytes()
    assert saved_texture[1056] == 7
    assert saved_texture[:1056] == original_texture[:1056]
    assert saved_texture[1057:] == original_texture[1057:]
    assert world_textures.parse(saved_texture)['textures'][0]['sha256'] != world_textures.parse(original_texture)['textures'][0]['sha256']


@pytest.mark.parametrize('value', [True, False, .5, float('inf'), float('nan'), '1.5', -1, 2])
def test_invalid_texture_palette_does_not_change_data(files, value):
    root, _, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        world_textures.png_bytes(0, palette=value)
    assert snapshot(root) == before


def test_world_http_rejection_and_valid_reload(files):
    from plugins.ff8.server import create_server

    root, wmset, _ = files
    before = snapshot(root)
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{server.server_address[1]}/api/world-map/save'

    def request(batch):
        return Request(url, data=json.dumps({'edits': batch}).encode(),
                       headers={'Content-Type': 'application/json'})

    try:
        for kind in edits():
            bad = deepcopy(edits()[kind])
            bad['id'] = .5
            with pytest.raises(HTTPError) as failure:
                urlopen(request([edits()['region'], bad]), timeout=5)
            assert failure.value.code == 400
            with failure.value as response:
                assert 'integer' in json.load(response)['error']
            assert snapshot(root) == before
        with urlopen(request(list(edits().values())), timeout=5) as response:
            assert json.load(response)['saved'] == len(edits())
        assert world_map.parse(wmset.read_bytes())['regions'][0]['regionId'] == 7
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        assert not worker.is_alive()
