"""Walkmesh and entrance saves reject malformed values before batch writes."""
import json
import struct
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import field_data, field_walkmesh, paths
from plugins.ff8.server import create_server
from test_ff8_field_camera_movie import _inf676


def mesh():
    vertices = b''.join(struct.pack('<4h', index * 3 + 1, index * 3 + 2,
                                   index * 3 + 3, 100 + index) for index in range(6))
    return struct.pack('<I', 2) + vertices + struct.pack('<6h', -1, 1, -1, 0, -1, 0) + b'\x34\x12'


def entrances():
    raw = bytearray(_inf676())
    raw[10:16] = b'OPAQUE'
    raw[120:132] = b'UNKNOWNBYTES'
    return bytes(raw)


@pytest.fixture
def files(tmp_path, monkeypatch):
    source = tmp_path / 'vanilla'
    source.mkdir()
    output = tmp_path / 'mod'
    for key in ('one', 'two'):
        (source / f'{key}.id').write_bytes(mesh())
        (source / f'{key}.inf').write_bytes(entrances())
    monkeypatch.setattr(paths, 'DIRECT_ROOT', output)
    monkeypatch.setattr(field_data, '_map_row', lambda key: dict(name=key, group='authored'))
    def current(extension):
        def locate(key, dataset):
            candidate = output / field_data.DIRECT_SUBDIR / 'authored' / key / f'{key}.{extension}'
            return candidate if dataset == 'current' and candidate.exists() else source / f'{key}.{extension}'
        return locate
    monkeypatch.setattr(field_data, '_walkmesh_source_path', current('id'))
    monkeypatch.setattr(field_data, '_inf_source_path', current('inf'))
    return tmp_path, source, output


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def edit(kind):
    return (dict(type='walkmesh', map='one', triangle=1, vertex=2, x=-32768, y=32767, z=0, adjacent=-1)
            if kind == 'walkmesh' else
            dict(type='entrance', map='one', kind='cameraRange', slot=7, field='right', value=32767))


def entrance_edits():
    return [edit('entrance')] + [dict(type='entrance', map='one', **values) for values in [
        dict(kind='misc', field='control', value=255), dict(kind='misc', field='pvp', value=65535),
        dict(kind='misc', field='focus', value=-32768),
        dict(kind='screenRange', slot=1, field='left', value=-32768),
        dict(kind='gateway', slot=0, field='fieldId', value=32767),
        dict(kind='gateway', slot=0, field='exitA', axis='x', value=-32768),
        dict(kind='trigger', slot=0, field='doorId', value=255),
        dict(kind='trigger', slot=0, field='lineB', axis='y', value=32767),
    ]]


@pytest.mark.parametrize('index', range(1, 9))
@pytest.mark.parametrize('value', [False, .5, float('inf'), '1.5'])
def test_entrance_value_validation_covers_header_ranges_gateways_and_triggers(files, index, value):
    root, _, _ = files
    before = snapshot(root)
    bad = entrance_edits()[index]
    bad['value'] = value
    with pytest.raises(ValueError, match='integer'):
        field_data.save([edit('walkmesh'), bad])
    assert snapshot(root) == before


@pytest.mark.parametrize('kind,field', [
    ('walkmesh', 'triangle'), ('walkmesh', 'vertex'), ('walkmesh', 'x'),
    ('walkmesh', 'y'), ('walkmesh', 'z'), ('walkmesh', 'adjacent'),
    ('entrance', 'slot'), ('entrance', 'value'),
])
@pytest.mark.parametrize('value', [False, True, .5, float('inf'), float('nan'), '1.5'])
def test_geometry_codecs_reject_nonintegers(kind, field, value):
    bad = edit(kind)
    bad[field] = value
    with pytest.raises(ValueError, match='integer'):
        if kind == 'walkmesh':
            field_walkmesh.apply_edits(mesh(), [{k: v for k, v in bad.items() if k not in {'type', 'map'}}])
        else:
            field_data._edit_inf_bytes(entrances(), [bad])


@pytest.mark.parametrize('kind,field', [
    ('walkmesh', 'triangle'), ('walkmesh', 'vertex'), ('walkmesh', 'x'),
    ('walkmesh', 'y'), ('walkmesh', 'z'), ('walkmesh', 'adjacent'),
    ('entrance', 'slot'), ('entrance', 'value'),
])
@pytest.mark.parametrize('value', [False, .5, float('inf'), '1.5'])
def test_geometry_service_rejects_later_map_before_writes(files, kind, field, value):
    root, _, output = files
    before = snapshot(root)
    bad = edit(kind)
    bad.update(map='two', **{field: value})
    with pytest.raises(ValueError, match='integer'):
        field_data.save([edit('entrance' if kind == 'walkmesh' else 'walkmesh'), bad])
    assert snapshot(root) == before
    assert not output.exists()


@pytest.mark.parametrize('kind,changes', [
    ('walkmesh', dict(triangle=2)), ('walkmesh', dict(vertex=3)),
    ('walkmesh', dict(x=-32769)), ('walkmesh', dict(y=32768)),
    ('walkmesh', dict(adjacent=-2)), ('walkmesh', dict(adjacent=2)),
    ('walkmesh', dict(reserved=0)), ('walkmesh', dict(trailingUnknown=0)),
    ('entrance', dict(slot=8)), ('entrance', dict(value=-32769)),
    ('entrance', dict(value=32768)), ('entrance', dict(field='unknown')),
])
def test_geometry_bounds_and_protected_fields_preserve_existing_outputs(files, kind, changes):
    root, _, _ = files
    field_data.save([edit('walkmesh'), edit('entrance')])
    before = snapshot(root)
    bad = edit(kind)
    bad.update(changes)
    with pytest.raises(ValueError):
        field_data.save([edit('entrance' if kind == 'walkmesh' else 'walkmesh'), bad])
    assert snapshot(root) == before


@pytest.mark.parametrize('kind', ['walkmesh', 'entrance'])
def test_geometry_duplicate_records_preserve_existing_outputs(files, kind):
    root, _, _ = files
    field_data.save([edit(kind)])
    before = snapshot(root)
    with pytest.raises(ValueError, match='duplicate|repeats'):
        field_data.save([edit(kind), edit(kind)])
    assert snapshot(root) == before


def assert_reload(source):
    expected_mesh = bytearray(mesh())
    struct.pack_into('<3h', expected_mesh, 44, -32768, 32767, 0)
    struct.pack_into('<h', expected_mesh, 62, -1)
    expected_inf = bytearray(entrances())
    struct.pack_into('<h', expected_inf, 80, 32767)
    for offset, fmt, value in [(9, 'B', 255), (16, 'H', 65535), (18, 'h', -32768),
                               (98, 'h', -32768), (118, 'H', 32767), (100, 'h', -32768),
                               (496, 'B', 255), (492, 'h', 32767)]:
        struct.pack_into('<' + fmt, expected_inf, offset, value)
    updated_mesh = field_data._walkmesh_source_path('one', 'current').read_bytes()
    updated_inf = field_data._inf_source_path('one', 'current').read_bytes()
    assert updated_mesh == bytes(expected_mesh)
    assert updated_inf == bytes(expected_inf)
    vertex = field_walkmesh.read(updated_mesh)['triangles'][1]['vertices'][2]
    assert vertex == dict(id=2, x=-32768, y=32767, z=0, adjacent=-1, reserved=105)
    assert field_walkmesh.read(updated_mesh)['trailingUnknown'] == 0x1234
    parsed = field_data._parse_inf(updated_inf)
    assert parsed['cameraRanges'][7]['right'] == 32767
    assert (parsed['header']['control'], parsed['header']['pvp'], parsed['header']['focus']) == (255, 65535, -32768)
    assert parsed['screenRanges'][1]['left'] == -32768
    assert parsed['gateways'][0]['fieldId'] == 32767 and parsed['gateways'][0]['exitA']['x'] == -32768
    assert parsed['triggers'][0]['doorId'] == 255 and parsed['triggers'][0]['lineB']['y'] == 32767
    for key in ('one', 'two'):
        assert (source / f'{key}.id').read_bytes() == mesh()
        assert (source / f'{key}.inf').read_bytes() == entrances()


def test_geometry_valid_save_preserves_unknown_bytes_and_reloads(files):
    _, source, _ = files
    assert field_data.save([edit('walkmesh'), *entrance_edits()]) == dict(saved=13, maps=1)
    assert_reload(source)


def test_geometry_http_rejects_fraction_and_reserved_word_before_other_writes(files):
    root, source, _ = files
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/field/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        for changes in [dict(vertex=2.5), dict(reserved=0)]:
            before = snapshot(root)
            bad = edit('walkmesh')
            bad.update(changes)
            with pytest.raises(HTTPError) as failure:
                urlopen(request([edit('entrance'), bad]), timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(root) == before
        with urlopen(request([edit('walkmesh'), *entrance_edits()]), timeout=5) as response:
            assert json.load(response)['saved'] == 13
        assert_reload(source)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
