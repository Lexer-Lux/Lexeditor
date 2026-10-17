"""General field scripts and card pushes validate batches before deployment."""
import json
import struct
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import field_data, field_scripts, paths
from plugins.ff8.server import create_server


SYM = b'Entity\nEntity::card\nEntity::idle\n'


def script_file(updated=False):
    # Two methods, with the second method's position flag retained.
    words = [0x05000000] + [0x07000000 | value for value in range(1, 8)] + [0x13A]
    if updated:
        words[1] = 0x07FFFFFF
        words.append(0)  # NOP before RET
    words.append(6)
    second = [0x05000001, 0, 6]
    positions = [1, 0, 0x8000 | len(words), len(words) + len(second)]
    return struct.pack('<BBBBHH', 0, 0, 0, 1, 10, 16) + struct.pack('<4H', *positions) + struct.pack(f'<{len(words) + len(second)}I', *words, *second)


def source_text():
    return 'LBL 0\n' + '\n'.join(f'PSHN_L {value}' for value in range(1, 8)) + '\nCARDGAME\nNOP\nRET'


@pytest.fixture
def files(tmp_path, monkeypatch):
    source = tmp_path / 'vanilla'
    source.mkdir()
    output = tmp_path / 'mod'
    for key in ('one', 'two'):
        (source / f'{key}.jsm').write_bytes(script_file())
        (source / f'{key}.sym').write_bytes(SYM)
    monkeypatch.setattr(paths, 'DIRECT_ROOT', output)
    monkeypatch.setattr(field_data, '_map_row', lambda key: dict(name=key, group='authored'))
    def current(key, dataset):
        candidate = output / field_data.DIRECT_SUBDIR / 'authored' / key / f'{key}.jsm'
        return (candidate if dataset == 'current' and candidate.exists() else source / f'{key}.jsm'), source / f'{key}.sym'
    monkeypatch.setattr(field_data, '_source_paths', current)
    return tmp_path, source, output


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def edit(kind, map_name='one', **changes):
    values = (dict(type='script', method=0, source=source_text()) if kind == 'script' else
              dict(type='card', player=0, param=0, value=0xFFFFFF))
    return dict(map=map_name, **values) | changes


@pytest.mark.parametrize('value', [False, True, .5, float('inf'), float('nan'), '1.5'])
def test_field_script_codec_rejects_noninteger_method(value):
    with pytest.raises(ValueError, match='integer'):
        field_scripts.rebuild(script_file(), SYM, [dict(id=value, source=source_text())])


@pytest.mark.parametrize('value', [None, True, 1, {}, []])
def test_field_script_codec_requires_source_text(value):
    with pytest.raises(ValueError, match='string'):
        field_scripts.rebuild(script_file(), SYM, [dict(id=0, source=value)])


def test_field_script_codec_rejects_protected_metadata():
    with pytest.raises(ValueError, match='unsupported field'):
        field_scripts.rebuild(script_file(), SYM, [dict(id=0, source=source_text(), labelId=1)])


@pytest.mark.parametrize('kind,field', [('script', 'method'), ('card', 'player'), ('card', 'param'), ('card', 'value')])
@pytest.mark.parametrize('value', [False, .5, float('inf'), '1.5'])
def test_field_script_service_rejects_later_map_before_any_writes(files, kind, field, value):
    root, _, output = files
    before = snapshot(root)
    with pytest.raises(ValueError, match='integer'):
        field_data.save([edit('script'), edit(kind, 'two', **{field: value})])
    assert snapshot(root) == before
    assert not output.exists()


@pytest.mark.parametrize('value', [None, True, 1, {}, []])
def test_field_script_service_does_not_stringify_source(files, value):
    root, _, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError, match='string'):
        field_data.save([edit('card'), edit('script', 'two', source=value)])
    assert snapshot(root) == before


@pytest.mark.parametrize('batch', [
    [edit('card', value=-1)], [edit('card', value=0x1000000)],
    [edit('card', player=1)], [edit('card', param=7)],
    [edit('card', param=4)], [edit('card', param=5)],
    [edit('card'), edit('card')], [edit('script'), edit('script')],
    [edit('script', method=2)], [edit('script', source=source_text().replace('LBL 0', 'LBL 1'))],
    [edit('script', source=source_text() + '\nNOT_AN_OPCODE')],
    [edit('script', labelId=1)], [edit('card', opcode=0)],
])
def test_field_script_bounds_protected_values_and_duplicates_preserve_outputs(files, batch):
    root, _, _ = files
    field_data.save([edit('script'), edit('card')])
    before = snapshot(root)
    with pytest.raises(ValueError):
        field_data.save(batch)
    assert snapshot(root) == before


def test_field_script_locked_method_retains_source(files):
    root, source, _ = files
    raw = bytearray(script_file())
    # An unsupported opcode in method 1 stays locked.
    raw[-8:-4] = struct.pack('<I', 0xFFFF)
    (source / 'two.jsm').write_bytes(raw)
    before = snapshot(root)
    with pytest.raises(ValueError, match='unsupported instruction'):
        field_data.save([edit('card'), edit('script', 'two', method=1, source='LBL 1\nRET')])
    assert snapshot(root) == before


def test_field_card_unsupported_push_retains_source(files):
    root, source, _ = files
    raw = bytearray(script_file())
    raw[20:24] = struct.pack('<I', 0)  # NOP cannot stand in for an editable push.
    (source / 'two.jsm').write_bytes(raw)
    before = snapshot(root)
    with pytest.raises(ValueError, match='not a supported'):
        field_data.save([edit('script'), edit('card', 'two')])
    assert snapshot(root) == before


def assert_reload(source):
    raw = field_data._source_paths('one', 'current')[0].read_bytes()
    assert raw == script_file(updated=True)
    parsed = field_scripts.read(raw, SYM)
    original = field_scripts.read(script_file(), SYM)
    assert parsed['methods'][1]['raw'] == original['methods'][1]['raw']
    assert parsed['methods'][1]['flagged'] is True
    # Source syntax interprets the same 24-bit payload as signed, unlike the
    # card reader's stored-word view. This checks encoding, not game semantics.
    assert parsed['methods'][0]['source'] == source_text().replace('PSHN_L 1\n', 'PSHN_L -1\n', 1)
    players = field_data._parse_card_players(raw, SYM)
    assert len(players) == 1 and players[0]['params'][0]['value'] == 0xFFFFFF
    assert [param['value'] for param in players[0]['params'][1:]] == list(range(2, 8))
    assert [param['opcode'] for param in players[0]['params']] == [7] * 7
    for key in ('one', 'two'):
        assert (source / f'{key}.jsm').read_bytes() == script_file()
        assert (source / f'{key}.sym').read_bytes() == SYM


def test_field_script_and_card_valid_combined_save_reloads(files):
    _, source, _ = files
    assert field_data.save([edit('script'), edit('card')]) == dict(saved=2, maps=1)
    assert_reload(source)


def test_field_script_http_rejects_bad_ids_source_and_values_then_reloads(files):
    root, source, _ = files
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/field/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        for bad in [edit('script', 'two', method=.5), edit('script', 'two', source=None), edit('card', 'two', value=1.5)]:
            before = snapshot(root)
            with pytest.raises(HTTPError) as failure:
                urlopen(request([edit('card'), bad]), timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(root) == before
        with urlopen(request([edit('script'), edit('card')]), timeout=5) as response:
            assert json.load(response)['saved'] == 2
        assert_reload(source)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
