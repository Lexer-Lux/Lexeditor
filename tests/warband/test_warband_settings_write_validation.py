"""Settings batches preserve INI formatting and reject invalid line edits."""
import json
import hashlib
import os
from pathlib import Path
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.warband import server


ORIGINAL = b'\xEF\xBB\xBF[General]\r\n; enabled=999\nenabled = 1  ; keep\r\n\nempty = \nname\t=\tVanilla\t# keep\rbare = old'
GOOD = dict(line=2, value='0')
EXPECTED = ORIGINAL.replace(b'enabled = 1  ; keep', b'enabled = 0  ; keep')


def save_current(edits):
    return server.save_settings(edits, hashlib.sha256(server.SETTINGS.read_bytes()).hexdigest())


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
            assert save_current([GOOD])['saved'] == 1
        before = snapshot(root)
        with pytest.raises(ValueError):
            save_current([GOOD, later])
        assert snapshot(root) == before


@pytest.mark.parametrize('edits', [None, False, {}, (), 'text', 1])
def test_invalid_collection_rejects(settings, edits):
    root, _ = settings
    before = snapshot(root)
    with pytest.raises(ValueError, match='array'):
        save_current(edits)
    assert snapshot(root) == before


def test_valid_mixed_line_endings_comments_bom_and_original_backup(settings):
    root, path = settings
    result = save_current([GOOD, dict(line=4, value='set'), dict(line=5, value='New'), dict(line=6, value='Last')])
    expected = EXPECTED.replace(b'empty = \n', b'empty = set\n').replace(b'Vanilla\t# keep', b'New\t# keep').replace(b'bare = old', b'bare = Last')
    assert path.read_bytes() == expected
    assert result['saved'] == 4
    backup = path.with_suffix('.ini.lexeditor.bak')
    assert backup.read_bytes() == ORIGINAL
    rows = {row['line']: row['value'] for row in server.settings_rows()}
    assert rows[2] == '0' and rows[4] == 'set' and rows[5] == 'New' and rows[6] == 'Last'
    save_current([dict(line=2, value='2')])
    assert path.read_bytes() == expected.replace(b'enabled = 0', b'enabled = 2')
    assert backup.read_bytes() == ORIGINAL
    assert len(snapshot(root)) == 2


def test_empty_batch_and_invalid_encoding_do_not_write(settings):
    root, path = settings
    before = snapshot(root)
    assert save_current([])['saved'] == 0
    assert snapshot(root) == before
    path.write_bytes(ORIGINAL + b'\xFF')
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_current([GOOD])
    assert snapshot(root) == before


def test_external_line_insert_rejects_stale_save_before_backup(settings):
    root, path = settings
    loaded = server.settings_data()
    assert loaded['sha256'] == hashlib.sha256(ORIGINAL).hexdigest()
    assert loaded['rows'][0]['section'] == 'General'
    path.write_bytes(b'; external insertion\n' + ORIGINAL)
    before = snapshot(root)
    with pytest.raises(RuntimeError, match='changed since'):
        server.save_settings([GOOD], loaded['sha256'])
    assert snapshot(root) == before
    loaded = server.settings_data()
    target = next(row for row in loaded['rows'] if row['key'] == 'enabled')
    assert target['line'] == 3
    assert server.save_settings([dict(line=target['line'], value='0')], loaded['sha256'])['saved'] == 1
    assert path.read_bytes() == b'; external insertion\n' + EXPECTED


def test_missing_checksum_and_existing_backup_stale_save_reject(settings):
    root, path = settings
    original_sha = server.settings_data()['sha256']
    save_current([GOOD])
    before = snapshot(root)
    with pytest.raises(RuntimeError, match='changed since'):
        server.save_settings([dict(line=2, value='2')], original_sha)
    assert snapshot(root) == before
    with pytest.raises(ValueError, match='checksum'):
        server.save_settings([GOOD], None)
    assert snapshot(root) == before


def test_failed_atomic_replace_retains_settings_and_cleans_temporary_file(settings, monkeypatch):
    root, path = settings
    save_current([GOOD])
    before = snapshot(root)
    def fail(*_args):
        raise OSError('authored replacement failure')
    monkeypatch.setattr(server.os, 'replace', fail)
    with pytest.raises(OSError, match='authored replacement failure'):
        save_current([dict(line=2, value='2')])
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
        return Request(base + 'settings/save', data=json.dumps(dict(edits=edits, sha256=hashlib.sha256(path.read_bytes()).hexdigest())).encode(), headers={'Content-Type': 'application/json'})
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
        with urlopen(base + 'settings', timeout=5) as response:
            loaded_sha = json.load(response)['sha256']
        path.write_bytes(b'; external insertion\n' + path.read_bytes())
        before = snapshot(root)
        for body in (dict(edits=[GOOD], sha256=loaded_sha), dict(edits=[GOOD])):
            stale = Request(base + 'settings/save', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            with pytest.raises(HTTPError) as failure:
                urlopen(stale, timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(root) == before
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def test_production_settings_save_callers_send_loaded_checksum_and_retain_stale_draft(settings, monkeypatch):
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlparse

    root, path = settings
    monkeypatch.delenv('LEXEDITOR_MOD_READ_ONLY', raising=False)
    http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    fixtures = {
        '/api/dashboard': dict(paths={}, problems=[]),
        '/api/items': dict(rows=[], choices={}),
        '/api/troops': dict(rows=[], items=[], factions=[], types={}, flags={}),
        '/api/upgrades': dict(rows=[]), '/api/modules': dict(modules=[]),
        '/api/datamap': dict(rows=[]), '/api/warband-font': dict(available=False),
        '/api/build/start': dict(started=True),
        '/api/build/status': dict(cursor=1, lines=['Build verified: authored fixture'], running=False, returnCode=0),
    }
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                for caller in ('saveSettings', 'saveAll'):
                    path.write_bytes(ORIGINAL)
                    page = browser.new_page(viewport={'width': 1400, 'height': 900})
                    sent = []
                    def api_route(route):
                        url = urlparse(route.request.url).path
                        if url == '/api/settings/save':
                            sent.append(json.loads(route.request.post_data))
                            route.continue_()
                        elif url == '/api/settings':
                            route.continue_()
                        else:
                            route.fulfill(json=fixtures.get(url, {}))
                    page.route('**/api/**', api_route)
                    page.goto(f'http://127.0.0.1:{http.server_port}/')
                    page.wait_for_function('()=>typeof state!=="undefined"&&!state.booting&&state.settings?.sha256')
                    page.wait_for_function('()=>!document.documentElement.classList.contains("lex-loading-live")')
                    page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                    page.evaluate('()=>{navigate("tweaks");state.selectedSetting="2";renderSettings()}')
                    page.locator('.lex-detail-panel input').fill('0')
                    loaded_sha = page.evaluate('state.settings.sha256')
                    assert page.evaluate('state.settingEdits[2]') == '0'
                    path.write_bytes(b'; external insertion\n' + ORIGINAL)
                    before = snapshot(root)
                    message = page.evaluate('async caller=>{try{await window[caller]();return "saved"}catch(error){return error.message}}', caller)
                    if caller == 'saveSettings':
                        assert 'changed since' in message
                    else:
                        assert page.evaluate('state.status') == 'Save failed'
                        page.get_by_text('Settings changed since they were opened; reload before saving', exact=True).wait_for(state='visible')
                        capture = Path(os.environ['TEMP']) / 'lexeditor-dev' / 'rendered' / 'warband-stale-settings.png'
                        capture.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(capture))
                        page.get_by_role('button', name='Confirm and Close', exact=True).click()
                    assert snapshot(root) == before
                    assert sent[-1]['sha256'] == loaded_sha
                    assert page.evaluate('state.settingEdits[2]') == '0'
                    # Explicitly reload, then edit the same key at its new line.
                    page.evaluate('async()=>{state.settings=await api("/api/settings");state.settingEdits={};state.selectedSetting="3";renderSettings()}')
                    fresh_sha = page.evaluate('state.settings.sha256')
                    assert fresh_sha != loaded_sha
                    page.locator('.lex-detail-panel input').fill('0')
                    message = page.evaluate('async caller=>{try{await window[caller]();return "saved"}catch(error){return error.message}}', caller)
                    assert message == 'saved', message
                    assert sent[-1]['sha256'] == fresh_sha
                    assert path.read_bytes() == b'; external insertion\n' + EXPECTED
                    assert page.evaluate('Object.keys(state.settingEdits).length') == 0
                    assert page.evaluate('state.settings.sha256') == hashlib.sha256(path.read_bytes()).hexdigest()
                    page.close()
            finally:
                browser.close()
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()
