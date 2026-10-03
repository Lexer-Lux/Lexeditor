"""Asset validation must not delete replacements or partially apply batches."""
import base64
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import assets, paths
from plugins.ff8.server import create_server
from test_ff8_asset_tabs import dat_bytes


def encoded(data):
    return base64.b64encode(data).decode()


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture(params=['sfx', 'models'])
def files(tmp_path, monkeypatch, request):
    family = request.param
    source = tmp_path / 'vanilla' / 'battle'
    source.mkdir(parents=True)
    original = dat_bytes([64] * 11)
    for name in ('c0m001.dat', 'c0m002.dat'):
        (source / name).write_bytes(original)
    project = tmp_path / 'mod'
    monkeypatch.setattr(paths, 'PROJECT_ROOT', project)
    monkeypatch.setattr(paths, 'DIRECT_ROOT', project / 'direct')
    monkeypatch.setattr(paths, 'BASELINE_ROOT', tmp_path / 'vanilla')
    monkeypatch.setattr(assets, '_sfx_entries', lambda: [{}, {}])
    monkeypatch.setattr(assets, '_battle_archive_index', lambda: [])
    if family == 'sfx':
        save = assets.save_sfx
        first = dict(id=0, ext='ogg', audioBase64=encoded(b'OggSreplacement'))
        second = first | dict(id=1)
        revert = dict(id=0, revert=True)
        destination = project / 'sfx' / '0.ogg'
        expected = b'OggSreplacement'
    else:
        save = assets.save_models
        expected = dat_bytes([65] * 11)
        first = dict(file='c0m001.dat', datBase64=encoded(expected))
        second = first | dict(file='c0m002.dat')
        revert = dict(file='c0m001.dat', revert=True)
        destination = project / 'direct' / 'battle' / 'c0m001.dat'
    return tmp_path, project, family, save, first, second, revert, destination, expected


@pytest.mark.parametrize('mode', ['missing', 'base64', 'magic', 'bounds', 'revert', 'duplicate', 'object', 'size'])
@pytest.mark.parametrize('first_revert', [False, True])
def test_asset_invalid_later_entry_preserves_new_and_existing_outputs(files, monkeypatch, mode, first_revert):
    root, project, family, save, first, second, revert, destination, expected = files
    payload = 'audioBase64' if family == 'sfx' else 'datBase64'
    bad = second.copy()
    if mode == 'missing':
        bad.pop(payload)
    elif mode == 'base64':
        bad[payload] = '!invalid!'
    elif mode == 'magic':
        bad[payload] = encoded(b'junk')
    elif mode == 'bounds':
        bad.update(id=99) if family == 'sfx' else bad.update(file='../escape.dat')
    elif mode == 'revert':
        bad['revert'] = 1
    elif mode == 'duplicate':
        bad = first.copy()
    elif mode == 'object':
        bad = None
    else:
        monkeypatch.setattr(assets, 'MAX_SFX_BYTES' if family == 'sfx' else 'MAX_MODEL_BYTES', len(expected))
        bad[payload] = encoded(expected + b'X')
    before = snapshot(root)
    with pytest.raises(ValueError):
        save([revert if first_revert else first, bad])
    assert snapshot(root) == before
    assert not project.exists()
    save([first])
    before = snapshot(root)
    with pytest.raises(ValueError):
        save([revert if first_revert else first, bad])
    assert snapshot(root) == before


def test_asset_valid_batch_and_revert_leave_vanilla_untouched(files):
    root, _, _, save, first, second, revert, destination, expected = files
    vanilla = snapshot(root / 'vanilla')
    assert save([first, second]) == dict(saved=2)
    assert destination.read_bytes() == expected
    assert save([revert]) == dict(saved=1)
    assert not destination.exists()
    assert snapshot(root / 'vanilla') == vanilla


def test_asset_failed_replace_preserves_prior_files_and_cleans_temporary(files, monkeypatch):
    root, _, family, save, first, _, _, destination, _ = files
    save([first])
    if family == 'sfx':
        destination.with_suffix('.wav').write_bytes(b'previous alternate')
    before = snapshot(root)
    def fail(*args):
        raise OSError('Authored replacement failure')
    monkeypatch.setattr(assets.os, 'replace', fail)
    with pytest.raises(OSError, match='Authored'):
        save([first])
    assert snapshot(root) == before


def test_sfx_valid_format_change_and_revert_keep_sidecars(files):
    root, project, family, save, first, _, revert, destination, _ = files
    if family != 'sfx':
        pytest.skip('Alternate audio formats apply only to SFX')
    save([first])
    backup = destination.with_suffix('.bak')
    temporary = destination.with_suffix('.tmp')
    backup.write_bytes(b'backup')
    temporary.write_bytes(b'temporary')
    save([first | dict(ext='flac', audioBase64=encoded(b'fLaCchanged'))])
    assert not destination.exists()
    assert destination.with_suffix('.flac').read_bytes() == b'fLaCchanged'
    save([revert])
    assert snapshot(project / 'sfx') == {'0.bak': b'backup', '0.tmp': b'temporary'}


def test_asset_http_invalid_batch_preserves_existing_replacement(files):
    root, _, family, save, first, second, revert, destination, expected = files
    save([first])
    before = snapshot(root)
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/{family}/save'
        payload = 'audioBase64' if family == 'sfx' else 'datBase64'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        with pytest.raises(HTTPError) as failure:
            urlopen(request([revert, second | {payload: '!invalid!'}]), timeout=5)
        assert failure.value.code == 400
        failure.value.close()
        assert snapshot(root) == before
        with urlopen(request([first, second]), timeout=5) as response:
            assert json.load(response)['saved'] == 2
        assert destination.read_bytes() == expected
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
