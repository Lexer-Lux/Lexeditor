"""Background writes validate whole batches and retain opaque tile data."""
import json
import struct
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import field_background, field_data, paths
from plugins.ff8.server import create_server


def pair(variant):
    if variant == 'new':
        tile = struct.pack('<hhHHHBBBBBB', 0, 0, 5, 0xA010, 0xC001, 2, 3, 1, 4, 255, 0)
    else:
        tile = struct.pack('<hhHHHHH', 0, 0, 2, 3, 5, 0xA010, 0xC001)
        if variant == 'old':
            tile += bytes([255, 0])
    second = bytearray(tile)
    struct.pack_into('<h', second, 0, 16)
    terminator = struct.pack('<h', 0x7FFF) + bytes([0xA5]) * (len(tile) - 2)
    size = field_background.NEW_MIM_SIZE if variant == 'new' else field_background.OLD_MIM_SIZE
    return tile + second + terminator, bytes([0x5A]) * size


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture(params=['new', 'old', 'old-short'])
def files(tmp_path, monkeypatch, request):
    variant = request.param
    original, mim = pair(variant)
    source, output = tmp_path / 'vanilla', tmp_path / 'mod'
    source.mkdir()
    for key in ('one', 'two'):
        (source / f'{key}.map').write_bytes(original)
        (source / f'{key}.mim').write_bytes(mim)
    monkeypatch.setattr(paths, 'DIRECT_ROOT', output)
    monkeypatch.setattr(field_data, '_map_row', lambda key: dict(name=key, group='authored'))
    def current(key, dataset):
        candidate = output / field_data.DIRECT_SUBDIR / 'authored' / key / f'{key}.map'
        return (candidate if dataset == 'current' and candidate.exists() else source / f'{key}.map',
                source / f'{key}.mim')
    monkeypatch.setattr(field_data, '_background_source_paths', current)
    return tmp_path, source, output, variant


def edit(map_name='one', **changes):
    return dict(type='background', map=map_name, tile=0, x=1) | changes


@pytest.mark.parametrize('value', [False, True, .5, float('inf'), float('-inf'), float('nan'), '1.5', None])
def test_background_later_invalid_identity_writes_nothing(files, value):
    root, _, output, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError, match='integer'):
        field_data.save([edit(), edit('two', tile=value)])
    assert snapshot(root) == before
    assert not output.exists()
    field_data.save([edit()])
    before = snapshot(root)
    with pytest.raises(ValueError, match='integer'):
        field_data.save([edit(x=2), edit('two', tile=value)])
    assert snapshot(root) == before


@pytest.mark.parametrize('value', [False, .5, float('inf'), float('-inf'), float('nan')])
def test_background_numeric_fields_reject_invalid_scalars(files, value):
    root, _, _, variant = files
    original, mim = pair(variant)
    before = snapshot(root)
    for field in field_background.editable_fields(variant):
        if field == 'draw':
            continue
        with pytest.raises(ValueError, match='integer'):
            field_background.apply_edits(original, mim, [dict(tile=0) | {field: value}])
        with pytest.raises(ValueError, match='integer'):
            field_data.save([edit(), dict(type='background', map='two', tile=0) | {field: value}])
        assert snapshot(root) == before


@pytest.mark.parametrize('changes', [dict(tile=-1), dict(tile=2), dict(draw=1), dict(texture=16),
                                     dict(x=32768), dict(opaque=1)])
def test_background_bounds_and_protected_fields_preserve_existing_output(files, changes):
    root, _, _, _ = files
    field_data.save([edit()])
    before = snapshot(root)
    with pytest.raises(ValueError):
        field_data.save([edit(x=2), edit('two', **changes)])
    assert snapshot(root) == before


def assert_reload(source, variant):
    original, mim = pair(variant)
    expected = bytearray(original)
    struct.pack_into('<h', expected, 0, 1)
    word_offset = 6 if variant == 'new' else 10
    struct.pack_into('<H', expected, word_offset, 0xA003)  # only texture and draw changed
    raw = field_data._background_source_paths('one', 'current')[0].read_bytes()
    assert raw == expected
    row = field_background.read(raw, mim)['tiles'][0]
    assert (row['x'], row['texture'], row['draw']) == (1, 3, False)
    for key in ('one', 'two'):
        assert (source / f'{key}.map').read_bytes() == original
        assert (source / f'{key}.mim').read_bytes() == mim
    assert field_data._background_source_paths('two', 'current')[0].read_bytes() == original


def test_background_valid_save_preserves_packed_words_other_tile_and_terminator(files):
    _, source, _, variant = files
    assert field_data.save([edit(texture=3, draw=False)]) == dict(saved=3, maps=1)
    assert_reload(source, variant)
    assert field_data.save([edit(texture=3, draw=False)])['saved'] == 0


def test_background_http_rejects_later_identity_and_infinite_value_then_reloads(files):
    root, source, _, variant = files
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/field/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        for bad in [edit('two', tile=.5), edit('two', x=float('inf'))]:
            before = snapshot(root)
            with pytest.raises(HTTPError) as failure:
                urlopen(request([edit(), bad]), timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(root) == before
        with urlopen(request([edit(texture=3, draw=False)]), timeout=5) as response:
            assert json.load(response)['saved'] == 3
        assert_reload(source, variant)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
