"""Localization validation and install preparation precede output writes."""
import json
import threading
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_rdr2_item_creation_validation import isolated, fixture, BASE
from test_rdr2_catalog_numeric_validation import snapshot
from plugins.rdr2 import server as s


BAD = [None, False, {}, '', (), [None], [{}], [{'key': 'VALID'}],
       [{'key': 'VALID', 'value': 'x', 'opaque': 1}]]
for bad in [None, True, 3, [], {}, '', 'BAD KEY', '0x123']:
    BAD.append([{'key': bad, 'value': 'x'}])
for bad in [None, True, 3, [], {}, 'bad\x00text', '\ud800']:
    BAD.append([{'key': 'VALID', 'value': bad}])
BAD.extend([[{'key': 'VALID', 'value': 'a'}, {'key': ' VALID ', 'value': 'b'}],
            [{'key': '0xABCDEF12', 'value': 'a'}, {'key': '0xabcdef12', 'value': 'b'}]])


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('existing_output', [False, True])
def test_rejected_later_edit_preserves_output_and_install(isolated, bad, existing_output):
    root, _ = isolated
    path = s.ds_dir('mine') / s.LOCALIZATION_FILE
    if existing_output:
        path.write_bytes(b'\xef\xbb\xbf[LEXEDITOR OVERRIDES]\r\nOLD = Keep\r\n')
    (s.ds_dir('mine') / 'install.xml').write_text('<Install><Resources/></Install>')
    before = snapshot(root)
    edits = [{'key': 'FIRST', 'value': 'Changed'}, *bad] if isinstance(bad, list) else bad
    with pytest.raises(ValueError):
        s.save_localization(edits)
    assert snapshot(root) == before


@pytest.mark.parametrize('content', ['<Install/>', '<invalid'])
def test_item_creation_preflights_invalid_install_before_catalog_and_metadata(isolated, content):
    root, _ = isolated
    cached_root = s.load_file(s.CATALOG_FILE)['root']
    cached = ET.tostring(cached_root)
    (s.ds_dir('mine') / 'install.xml').write_text(content)
    before = snapshot(root)
    with pytest.raises(ValueError):
        s.create_catalog_item(BASE)
    assert snapshot(root) == before
    assert ET.tostring(cached_root) == cached


@pytest.mark.parametrize('payload', [b'\xff invalid', b'BAD KEY = Keep\n', b'OLD = bad\x00text\n'])
def test_existing_invalid_localization_rejects_before_creation_or_save(isolated, payload):
    root, _ = isolated
    (s.ds_dir('mine') / s.LOCALIZATION_FILE).write_bytes(payload)
    before = snapshot(root)
    cached = ET.tostring(s.load_file(s.CATALOG_FILE)['root'])
    for save in [lambda: s.save_localization([{'key': 'FIRST', 'value': 'Changed'}]),
                 lambda: s.create_catalog_item(BASE)]:
        with pytest.raises(ValueError):
            save()
        assert snapshot(root) == before
        assert ET.tostring(s.load_file(s.CATALOG_FILE)['root']) == cached


def test_empty_batch_is_noop_without_loading_baseline(isolated):
    root, _ = isolated
    s.VANILLA_LOCALIZATION_FILE.unlink()
    before = snapshot(root)
    assert s.save_localization([]) == 0
    assert snapshot(root) == before


def test_real_http_rejects_later_edit_and_valid_unicode_reload_removes_baseline_override(isolated):
    root, _ = isolated
    s.VANILLA_LOCALIZATION_FILE.write_text(json.dumps({'BASELINE': 'Shipped'}))
    path = s.ds_dir('mine') / s.LOCALIZATION_FILE
    path.write_text('[LEXEDITOR OVERRIDES]\nBASELINE = Changed\nOLD = Keep\n')
    install = s.ds_dir('mine') / 'install.xml'
    install.write_text('<Install><Resources><Resource><Opaque>keep</Opaque></Resource></Resources></Install>')
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def request(edits):
        return Request(f'http://127.0.0.1:{http.server_port}/api/localization/save',
                       data=json.dumps({'edits': edits}).encode(), headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request([{'key': 'FIRST', 'value': 'Changed'}, {'key': 'BAD KEY', 'value': 'x'}]), timeout=5)
        assert failure.value.code == 400
        assert snapshot(root) == before
        edits = [{'key': 'BASELINE', 'value': 'Shipped'}, {'key': 'FIRST', 'value': 'Café 🐎\r\nLine'}]
        with urlopen(request(edits), timeout=5) as response:
            assert json.load(response)['saved'] == 2
        assert s.parse_gxt2(path) == {'FIRST': 'Café 🐎  Line', 'OLD': 'Keep'}
        tree = ET.parse(install)
        assert tree.findtext('.//DataFile') == s.LOCALIZATION_FILE
        assert tree.findtext('.//Opaque') == 'keep'
        stable = snapshot(root)
        assert s.save_localization(edits) == 2
        assert snapshot(root) == stable
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
