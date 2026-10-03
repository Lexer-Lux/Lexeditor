"""Cache-size rejection preserves settings and generated previews over real HTTP."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from playwright.sync_api import sync_playwright, expect

from plugins.rdr2 import model_preview as preview, server
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def cache(tmp_path, monkeypatch):
    for name, path in {
        'PREVIEW_DATA_ROOT': tmp_path,
        'CACHE_ROOT': tmp_path / 'model-previews',
        'SETTINGS_FILE': tmp_path / 'settings.json',
        'MANIFEST_FILE': tmp_path / 'model-previews/manifest.json',
        'ASSET_INDEX_FILE': tmp_path / 'model-previews/asset-index.json',
    }.items():
        monkeypatch.setattr(preview, name, path)
    monkeypatch.delenv('LEXEDITOR_MOD_READ_ONLY', raising=False)
    preview.CACHE_ROOT.mkdir()
    key = 'a' * 64
    preview._entry_path(key).write_bytes(b'authored geometry')
    assets = preview._entry_assets_path(key)
    assets.mkdir()
    (assets / 'texture.bin').write_bytes(b'authored texture')
    preview._save_manifest({'entries': {key: {'size': 33, 'accessed': 1}}})
    return tmp_path


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('payload', [None, [], {}, {'cacheSizeMb': 128, 'extra': 1}] + [
    {'cacheSizeMb': v} for v in [True, False, None, [], {}, '', '128.5', 128.5,
                               float('nan'), float('inf'), 127, 10241, 10**100]
])
def test_rejected_size_does_not_write_or_evict(cache, existing, payload):
    if existing:
        preview.SETTINGS_FILE.write_text('{"cacheSizeMb": 256}')
    before = snapshot(cache)
    with pytest.raises(ValueError):
        preview.save_preview_settings(payload)
    assert snapshot(cache) == before


@pytest.fixture
def service(cache):
    http = server.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    try:
        yield f'http://127.0.0.1:{http.server_port}'
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


def test_actual_http_rejects_then_saves_bounds(cache, service):
    before = snapshot(cache)
    request = Request(service + '/api/model-preview/settings',
                      data=json.dumps({'cacheSizeMb': 128.5}).encode(),
                      headers={'Content-Type': 'application/json'})
    with pytest.raises(HTTPError) as failure:
        urlopen(request, timeout=5)
    assert failure.value.code == 400
    assert 'integer' in json.load(failure.value)['error']
    assert snapshot(cache) == before
    for value in [128, 10240]:
        request.data = json.dumps({'cacheSizeMb': value}).encode()
        with urlopen(request, timeout=5) as response:
            assert json.load(response)['cacheSizeMb'] == value
        assert json.loads(preview.SETTINGS_FILE.read_text()) == {'cacheSizeMb': value}
        with urlopen(service + '/api/model-preview/settings', timeout=5) as response:
            assert json.load(response)['cacheSizeMb'] == value
    for path, data in before.items():
        assert (cache / path).read_bytes() == data


def test_rdr2_shared_read_only_guard_refuses_save(cache, service, monkeypatch):
    monkeypatch.setenv('LEXEDITOR_MOD_READ_ONLY', '1')
    monkeypatch.setenv('LEXEDITOR_NO_MOD', '1')
    before = snapshot(cache)
    request = Request(service + '/api/save', data=b'{}',
                      headers={'Content-Type': 'application/json'})
    with pytest.raises(HTTPError) as failure:
        urlopen(request, timeout=5)
    assert failure.value.code == 403
    assert 'Create a mod' in json.load(failure.value)['error']
    assert snapshot(cache) == before


def test_cache_dialog_rejects_raw_drafts_before_request(cache, service):
    source = (ROOT / 'plugins/rdr2/items.js').read_text(encoding='utf-8')
    dialog = source[source.index('async function showLexeditorSettings(){'):
                    source.index('async function createModelRenderer(')]
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1100, 'height': 800})
            page.route(service + '/', lambda route: route.fulfill(body='<main></main>', content_type='text/html'))
            page.goto(service + '/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.add_script_tag(content='''
                const el=LexeditorUI.el,fieldHelp=LexeditorUI.infoHelp;
                const state={modelPreviewLoads:{}};
                const formatFileSize=n=>String(n)+' bytes';
                async function api(path,options){const r=await fetch(path,options),data=await r.json();
                  if(!r.ok)throw new Error(data.error);return data;}
            ''' + dialog)
            page.evaluate('showLexeditorSettings()')
            size = page.get_by_role('spinbutton', name='Model preview cache size in MB')
            posts = []
            page.on('request', lambda request: posts.append(request.post_data) if request.method == 'POST' else None)
            before = snapshot(cache)
            for raw in ['128.5', '127', '10241', '']:
                size.fill(raw)
                assert size.input_value() == raw
                page.get_by_role('button', name='Save 1 unsaved setting change', exact=True).click()
                expect(page.locator('.lex-important-dialog')).to_be_visible()
                assert not posts
                assert snapshot(cache) == before
                assert size.input_value() == raw
                page.locator('.lex-important-dialog').get_by_role('button', name='Close', exact=True).click()
            size.fill('128')
            page.get_by_role('button', name='Save 1 unsaved setting change', exact=True).click()
            expect(page.locator('.lex-dialog-status')).to_have_text('Cache settings saved.')
            assert len(posts) == 1
            assert json.loads(preview.SETTINGS_FILE.read_text()) == {'cacheSizeMb': 128}
            page.evaluate('showLexeditorSettings()')
            expect(size).to_have_value('128')
            for path, data in before.items():
                assert (cache / path).read_bytes() == data
        finally:
            browser.close()
