"""Camera/movie edits retain invalid numeric drafts and validate before writes."""
import json
import struct
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import field_camera, field_data, field_movie, paths
from plugins.ff8.server import create_server
from test_ff8_field_camera_movie import _ca, _msk, MovieTests


def authored_camera():
    camera = bytearray(_ca() + _ca(500))
    camera[32:36] = b'KEEP'
    camera[72:76] = b'ALSO'
    camera[38:40] = b'\0\0'
    return bytes(camera)


@pytest.fixture
def files(tmp_path, monkeypatch):
    source = tmp_path / 'vanilla'
    source.mkdir()
    output = tmp_path / 'mod'
    (source / 'one.ca').write_bytes(authored_camera())
    (source / 'one.msk').write_bytes(_msk(MovieTests.FRAME, MovieTests.FRAME))
    monkeypatch.setattr(paths, 'DIRECT_ROOT', output)
    monkeypatch.setattr(field_data, '_map_row', lambda key: dict(name=key, group='authored'))
    def current(extension):
        def locate(key, dataset):
            candidate = output / field_data.DIRECT_SUBDIR / 'authored' / key / f'{key}.{extension}'
            return candidate if dataset == 'current' and candidate.exists() else source / f'{key}.{extension}'
        return locate
    monkeypatch.setattr(field_data, '_camera_source_path', current('ca'))
    monkeypatch.setattr(field_data, '_movie_source_path', current('msk'))
    return tmp_path, source, output


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def edit(kind):
    return (dict(type='camera', map='one', camera=1, field='position', axis='x', value=-2**31)
            if kind == 'camera' else
            dict(type='movie', map='one', frame=1, point=3, axis='z', value=-32768))


@pytest.mark.parametrize('kind,field', [('camera', 'camera'), ('camera', 'value'), ('movie', 'frame'), ('movie', 'point'), ('movie', 'value')])
@pytest.mark.parametrize('value', [False, True, .5, float('inf'), float('nan'), '1.5'])
def test_camera_codecs_reject_malformed_numbers(kind, field, value):
    bad = edit(kind)
    bad[field] = value
    raw = _ca() * 2 if kind == 'camera' else _msk(MovieTests.FRAME, MovieTests.FRAME)
    codec = field_camera if kind == 'camera' else field_movie
    with pytest.raises(ValueError, match='integer'):
        codec.apply_edits(raw, [bad])


@pytest.mark.parametrize('kind,field', [('camera', 'camera'), ('camera', 'value'), ('movie', 'frame'), ('movie', 'point'), ('movie', 'value')])
@pytest.mark.parametrize('value', [False, .5, float('inf'), '1.5'])
def test_camera_service_rejects_later_family_before_writes(files, kind, field, value):
    root, _, output = files
    before = snapshot(root)
    bad = edit(kind)
    bad[field] = value
    with pytest.raises(ValueError, match='integer'):
        field_data.save([edit('movie' if kind == 'camera' else 'camera'), bad])
    assert snapshot(root) == before
    assert not output.exists()


@pytest.mark.parametrize('kind,changes', [
    ('camera', dict(camera=2)), ('camera', dict(value=-2**31-1)), ('camera', dict(value=2**31)),
    ('camera', dict(field='axis0', value=-32769)), ('camera', dict(field='axis0', value=32768)),
    ('camera', dict(field='zoom', value=0)), ('camera', dict(field='zoom', value=65536)),
    ('camera', dict(field='unknown')), ('movie', dict(frame=2)), ('movie', dict(point=4)),
    ('movie', dict(value=-32769)), ('movie', dict(value=32768)), ('movie', dict(axis='unknown')),
])
def test_camera_bounds_protect_existing_outputs(files, kind, changes):
    root, _, _ = files
    field_data.save([edit('camera'), edit('movie')])
    before = snapshot(root)
    bad = edit(kind)
    bad.update(changes)
    with pytest.raises(ValueError):
        field_data.save([edit('movie' if kind == 'camera' else 'camera'), bad])
    assert snapshot(root) == before


def assert_reload(source):
    original_ca = authored_camera()
    expected_ca = bytearray(original_ca)
    struct.pack_into('<i', expected_ca, 60, -2**31)
    expected_ca[38:40] = struct.pack('<H', 400)
    original_msk = _msk(MovieTests.FRAME, MovieTests.FRAME)
    expected_msk = bytearray(original_msk)
    struct.pack_into('<h', expected_msk, 50, -32768)
    ca = field_data._camera_source_path('one', 'current').read_bytes()
    msk = field_data._movie_source_path('one', 'current').read_bytes()
    assert ca == bytes(expected_ca)
    assert msk == bytes(expected_msk)
    assert field_camera.read(ca)['cameras'][1]['position']['x'] == -2**31
    assert field_movie.read(msk)['frames'][1]['points'][3]['z'] == -32768
    assert (source / 'one.ca').read_bytes() == original_ca
    assert (source / 'one.msk').read_bytes() == original_msk


def test_camera_valid_two_file_save_preserves_unedited_data_and_reloads(files):
    _, source, _ = files
    assert field_data.save([edit('camera'), edit('movie')]) == dict(saved=2, maps=1)
    assert_reload(source)


def test_camera_http_rejects_fraction_before_writing_other_family_then_reloads(files):
    root, source, _ = files
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/field/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        before = snapshot(root)
        bad = edit('movie')
        bad['point'] = 3.5
        with pytest.raises(HTTPError) as failure:
            urlopen(request([edit('camera'), bad]), timeout=5)
        assert failure.value.code == 400
        failure.value.close()
        assert snapshot(root) == before
        with urlopen(request([edit('camera'), edit('movie')]), timeout=5) as response:
            assert json.load(response)['saved'] == 2
        assert_reload(source)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
