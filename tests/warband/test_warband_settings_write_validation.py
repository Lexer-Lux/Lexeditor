"""Settings batches preserve INI formatting and reject invalid line edits."""
import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.warband import server


ORIGINAL = b'\xEF\xBB\xBF[General]\r\n; enabled=999\nenabled = 1  ; keep\r\n\nempty = \nname\t=\tVanilla\t# keep\rbare = old'
GOOD = dict(line=2, value='0')
EXPECTED = ORIGINAL.replace(b'enabled = 1  ; keep', b'enabled = 0  ; keep')


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}


@pytest.fixture
def settings(tmp_path, monkeypatch):
    path = tmp_path / 'settings.ini'
    path.write_bytes(ORIGINAL)
    monkeypatch.setattr(server, 'SETTINGS', path)
    return tmp_path, path


BAD = [dict(line=value, value='Bad') for value in (False, True, .5, float('inf'), float('nan'), '1.5', None, -1, 99)] + [
    dict(line=5, value=value) for value in (None, False, 1, [], {}, 'new\nkey=1', 'new\rkey=1', 'bad\x00', 'bad;comment', 'bad#comment')] + [
    None, [], False, dict(line=2, value='duplicate'), dict(line=0, value='section'),
    dict(line=1, value='comment'), dict(line=3, value='blank'), dict(line=5, value='New', key='retarget')]


@pytest.mark.parametrize('later', BAD)
def test_invalid_later_edit_preserves_settings_and_backup(settings, later):
    root, path = settings
    for existing in (False, True):
        if existing:
            assert server.save_settings([GOOD])['saved'] == 1
        before = snapshot(root)
        with pytest.raises(ValueError):
            server.save_settings([GOOD, later])
        assert snapshot(root) == before


@pytest.mark.parametrize('edits', [None, False, {}, (), 'text', 1])
def test_invalid_collection_rejects(settings, edits):
    root, _ = settings
    before = snapshot(root)
    with pytest.raises(ValueError, match='array'):
        server.save_settings(edits)
    assert snapshot(root) == before


def test_valid_mixed_line_endings_comments_bom_and_original_backup(settings):
    root, path = settings
    result = server.save_settings([GOOD, dict(line=4, value='set'), dict(line=5, value='New'), dict(line=6, value='Last')])
    expected = EXPECTED.replace(b'empty = \n', b'empty = set\n').replace(b'Vanilla\t# keep', b'New\t# keep').replace(b'bare = old', b'bare = Last')
    assert path.read_bytes() == expected
    assert result['saved'] == 4
    backup = path.with_suffix('.ini.lexeditor.bak')
    assert backup.read_bytes() == ORIGINAL
    rows = {row['line']: row['value'] for row in server.settings_rows()}
    assert rows[2] == '0' and rows[4] == 'set' and rows[5] == 'New' and rows[6] == 'Last'
    server.save_settings([dict(line=2, value='2')])
    assert path.read_bytes() == expected.replace(b'enabled = 0', b'enabled = 2')
    assert backup.read_bytes() == ORIGINAL
    assert len(snapshot(root)) == 2


def test_empty_batch_and_invalid_encoding_do_not_write(settings):
    root, path = settings
    before = snapshot(root)
    assert server.save_settings([])['saved'] == 0
    assert snapshot(root) == before
    path.write_bytes(ORIGINAL + b'\xFF')
    before = snapshot(root)
    with pytest.raises(ValueError):
        server.save_settings([GOOD])
    assert snapshot(root) == before


def test_failed_atomic_replace_retains_settings_and_cleans_temporary_file(settings, monkeypatch):
    root, path = settings
    server.save_settings([GOOD])
    before = snapshot(root)
    def fail(*_args):
        raise OSError('authored replacement failure')
    monkeypatch.setattr(server.os, 'replace', fail)
    with pytest.raises(OSError, match='authored replacement failure'):
        server.save_settings([dict(line=2, value='2')])
    assert snapshot(root) == before
    assert path.read_bytes() == EXPECTED


def test_real_http_rejection_valid_reload_and_backup_retention(settings, monkeypatch):
    root, path = settings
    monkeypatch.delenv('LEXEDITOR_MOD_READ_ONLY', raising=False)
    http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{http.server_port}/api/'
    def request(edits):
        return Request(base + 'settings/save', data=json.dumps(dict(edits=edits)).encode(), headers={'Content-Type': 'application/json'})
    try:
        for existing in (False, True):
            if existing:
                with urlopen(request([GOOD]), timeout=5) as response:
                    assert json.load(response)['saved'] == 1
                assert path.read_bytes() == EXPECTED
                with urlopen(base + 'settings', timeout=5) as response:
                    assert next(row for row in json.load(response)['rows'] if row['line'] == 2)['value'] == '0'
            for edits in (None, [GOOD, dict(line=.5, value='Bad')], [GOOD, dict(line=5, value=False)], [GOOD, dict(line=5, value='bad\nkey=1')], [GOOD, GOOD]):
                before = snapshot(root)
                with pytest.raises(HTTPError) as failure:
                    urlopen(request(edits), timeout=5)
                assert failure.value.code == 400
                failure.value.close()
                assert snapshot(root) == before
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()
