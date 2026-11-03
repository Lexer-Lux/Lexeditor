"""Field dialogue validates identities and text before any map is written."""
import json
import struct
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import field_data, field_dialogue, kernel_text, paths
from plugins.ff8.server import create_server


def dialogue(text='Original'):
    first = kernel_text.encode(text) + b'\0'
    last = kernel_text.encode('Other')
    return struct.pack('<3I', 12, 12, 12 + len(first)) + first + last


@pytest.fixture
def files(tmp_path, monkeypatch):
    source = tmp_path / 'vanilla'
    source.mkdir()
    output = tmp_path / 'mod'
    for key in ('one', 'two'):
        (source / f'{key}.msd').write_bytes(dialogue())
    monkeypatch.setattr(paths, 'DIRECT_ROOT', output)
    monkeypatch.setattr(field_data, '_map_row', lambda key: dict(name=key, group='authored'))
    def current(key, dataset):
        candidate = output / field_data.DIRECT_SUBDIR / 'authored' / key / f'{key}.msd'
        return candidate if dataset == 'current' and candidate.exists() else source / f'{key}.msd'
    monkeypatch.setattr(field_data, '_dialogue_source_path', current)
    return tmp_path, source, output


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def edit(map_name='one', **changes):
    return dict(type='dialogue', map=map_name, line=1, text='Changed longer') | changes


@pytest.mark.parametrize('value', [False, True, .5, float('inf'), float('nan'), '1.5'])
def test_field_dialogue_codec_rejects_noninteger_ids(value):
    with pytest.raises(ValueError, match='integer'):
        field_dialogue.apply_edits(dialogue(), [dict(id=value, text='Changed')])


@pytest.mark.parametrize('value', [False, .5, float('inf'), '1.5'])
def test_field_dialogue_service_rejects_later_map_identity_without_writes(files, value):
    root, _, output = files
    before = snapshot(root)
    with pytest.raises(ValueError, match='integer'):
        field_data.save([edit(), edit('two', line=value)])
    assert snapshot(root) == before
    assert not output.exists()


@pytest.mark.parametrize('value', [None, True, 1, {}, []])
def test_field_dialogue_codec_requires_text(value):
    with pytest.raises(ValueError, match='string'):
        field_dialogue.apply_edits(dialogue(), [dict(id=1, text=value)])


@pytest.mark.parametrize('value', [None, True, 1, {}, []])
def test_field_dialogue_service_does_not_stringify_values(files, value):
    root, _, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError, match='string'):
        field_data.save([edit(), edit('two', text=value)])
    assert snapshot(root) == before


@pytest.mark.parametrize('batch', [
    [edit(), edit('two', line=3)], [edit(), edit('two', line=-1)],
    [edit(), edit()], [edit(), edit('two', text='\U0010FFFF')],
    [edit(), edit('two', rawText='01')],
])
def test_field_dialogue_rejection_preserves_existing_outputs(files, batch):
    root, _, _ = files
    field_data.save([edit()])
    before = snapshot(root)
    with pytest.raises(ValueError):
        field_data.save(batch)
    assert snapshot(root) == before


def assert_reload(source):
    raw = field_data._dialogue_source_path('one', 'current').read_bytes()
    assert raw == dialogue('Changed longer')
    rows = field_dialogue.read(raw)['lines']
    assert [row['text'] for row in rows] == ['', 'Changed longer', 'Other']
    assert [row['terminated'] for row in rows] == [False, True, False]
    assert rows[2]['rawText'] == kernel_text.encode('Other').hex()
    for key in ('one', 'two'):
        assert (source / f'{key}.msd').read_bytes() == dialogue()
    assert field_data._dialogue_source_path('two', 'current').read_bytes() == dialogue()


def test_field_dialogue_valid_save_keeps_empty_and_unterminated_lines(files):
    _, source, _ = files
    assert field_data.save([edit()]) == dict(saved=1, maps=1)
    assert_reload(source)
    assert field_data.save([edit()])['saved'] == 0


def test_field_dialogue_http_rejects_invalid_id_and_nontext_then_reloads(files):
    root, source, _ = files
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/field/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        for bad in [edit('two', line=1.5), edit('two', text=None)]:
            before = snapshot(root)
            with pytest.raises(HTTPError) as failure:
                urlopen(request([edit(), bad]), timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(root) == before
        with urlopen(request([edit()]), timeout=5) as response:
            assert json.load(response)['saved'] == 1
        assert_reload(source)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
