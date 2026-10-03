"""Catalog, multiple bundle files, radial assignments and backups commit together."""
import copy
import json
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_rdr2_catalog_numeric_validation import fixture, snapshot
from test_rdr2_quick_select_batch_validation import quick
from plugins.rdr2 import server as s

NAMES = [s.CATALOG_FILE, *s.LOOT_FILES[:2], s.QUICK_SELECT_FILE]
CASES = [(False, name) for name in NAMES] + [(True, name) for name in NAMES]
CASES += [(False, name + '.bak') for name in NAMES]


@pytest.fixture
def batch(quick):
    root, _ = quick
    for name in s.LOOT_FILES[:2]:
        path = s.data_file_path(name, 'mine')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'\xef\xbb\xbf<Root><!--preserve--><LootTables><Item key="BUNDLE"><Entries>'
                         b'<Item><Name>OUTPUT</Name><Min value="1"/><Max value="1"/><Opaque value="17"/>'
                         b'</Item></Entries></Item></LootTables></Root>')
        s.load_file(name)
    edits = {'carry': [{'item': 'FIXTURE', 'slot': 'SLOTID_ANY', 'qty': 9}],
             'bundles': [{'key': f'{name}|BUNDLE|OUTPUT', 'qty': 8} for name in s.LOOT_FILES[:2]],
             'quickSelect': [{'item': 'FIXTURE', 'slots': [{'id': 'SLOT_B', 'sortOrder': 40}]}]}
    return root, edits


def assert_reload(edits):
    assert s.apply_catalog_edits(copy.deepcopy(edits)) == 4
    s._files.clear()
    assert s.load_file(s.CATALOG_FILE)['root'].find('.//multiplicity/item/quantity').get('value') == '9'
    for name in s.LOOT_FILES[:2]:
        path = s.data_file_path(name, 'mine')
        assert path.read_bytes().startswith(b'\xef\xbb\xbf')
        assert '<!--preserve-->' in path.read_text(encoding='utf-8-sig')
        doc = s.load_file(name)['root']
        assert doc.find('.//Entries/Item/Min').get('value') == '8'
        assert doc.find('.//Entries/Item/Max').get('value') == '8'
        assert doc.find('.//Entries/Item/Opaque').get('value') == '17'
    doc = s.load_file(s.QUICK_SELECT_FILE)['root']
    edited = doc.find(".//Items/Item[@key='FIXTURE']")
    assert edited.findtext('Slots/Item/Id') == 'SLOT_B'
    assert edited.find('Slots/Item/SortOrder').get('value') == '40'
    assert edited.find('Opaque').get('value') == '17'
    assert doc.find(".//Items/Item[@key='UNTOUCHED']/Slots/Item/SortOrder").get('value') == '20'


@pytest.mark.parametrize('existing_backups,failure_name', CASES)
def test_each_replacement_failure_restores_all_bytes_backups_and_cached_roots(batch, monkeypatch, existing_backups, failure_name):
    root, edits = batch
    if existing_backups:
        for name in NAMES:
            path = s.data_file_path(name, 'mine')
            path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup ' + name.encode())
    cached = {name: s.load_file(name) for name in NAMES}
    original_roots = {name: entry['root'] for name, entry in cached.items()}
    before = snapshot(root)
    real_replace = Path.replace
    failed = False
    def replace(path, target):
        nonlocal failed
        if Path(target).name == Path(failure_name).name and not failed:
            failed = True
            raise OSError('Injected XML replacement failure')
        return real_replace(path, target)
    monkeypatch.setattr(Path, 'replace', replace)
    with pytest.raises(OSError, match='Injected XML replacement failure'):
        s.apply_catalog_edits(copy.deepcopy(edits))
    assert failed
    assert snapshot(root) == before
    for name, entry in cached.items():
        assert s.load_file(name) is entry
        assert entry['root'] is original_roots[name]
    assert not list(root.rglob('*.tmp'))
    assert_reload(edits)
    assert not list(root.rglob('*.tmp'))
    for name in NAMES:
        path = s.data_file_path(name, 'mine')
        expected = b'original backup ' + name.encode() if existing_backups else before[str(path.relative_to(root))]
        assert path.with_suffix(path.suffix + '.bak').read_bytes() == expected


def test_second_file_serialization_failure_changes_no_cache_or_output(batch, monkeypatch):
    root, edits = batch
    before = snapshot(root)
    original = {name: s.load_file(name)['root'] for name in NAMES}
    real_tostring = ET.tostring
    calls = 0
    def tostring(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise UnicodeEncodeError('utf-8', '\ud800', 0, 1, 'Injected serialization failure')
        return real_tostring(*args, **kwargs)
    monkeypatch.setattr(ET, 'tostring', tostring)
    with pytest.raises(UnicodeEncodeError):
        s.apply_catalog_edits(edits)
    assert snapshot(root) == before
    assert all(s.load_file(name)['root'] is value for name, value in original.items())


def test_last_staging_failure_preserves_all_outputs_and_removes_temps(batch, monkeypatch):
    root, edits = batch
    before = snapshot(root)
    real_temp = s.tempfile.NamedTemporaryFile
    calls = 0
    def temporary(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == len(NAMES) * 2:
            raise OSError('Injected last staging failure')
        return real_temp(*args, **kwargs)
    monkeypatch.setattr(s.tempfile, 'NamedTemporaryFile', temporary)
    with pytest.raises(OSError, match='Injected last staging failure'):
        s.apply_catalog_edits(edits)
    assert snapshot(root) == before
    assert not list(root.rglob('*.tmp'))


def test_direct_read_only_batch_writes_nothing(batch, monkeypatch):
    root, edits = batch
    monkeypatch.setitem(s.DATASETS['mine'], 'readonly', True)
    before = snapshot(root)
    with pytest.raises(PermissionError, match='read-only'):
        s.apply_catalog_edits(edits)
    assert snapshot(root) == before


def test_http_last_radial_write_failure_rolls_back_then_retry_reloads(batch, monkeypatch):
    root, edits = batch
    before = snapshot(root)
    real_replace = Path.replace
    failed = False
    def replace(path, target):
        nonlocal failed
        if Path(target).name == Path(s.QUICK_SELECT_FILE).name and not failed:
            failed = True
            raise OSError('Injected radial write failure')
        return real_replace(path, target)
    monkeypatch.setattr(Path, 'replace', replace)
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    try:
        request = Request(f'http://127.0.0.1:{http.server_port}/api/catalog/save',
                          data=json.dumps(edits).encode(), headers={'Content-Type': 'application/json'})
        with pytest.raises(HTTPError) as failure:
            urlopen(request, timeout=5)
        assert failure.value.code == 500
        assert 'Injected radial write failure' in json.load(failure.value)['error']
        assert snapshot(root) == before
        with urlopen(request, timeout=5) as response:
            assert json.load(response)['saved'] == 4
        s._files.clear()
        assert s.load_file(s.CATALOG_FILE)['root'].find('.//multiplicity/item/quantity').get('value') == '9'
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
