"""Loot validation rejects later malformed tables without cache or disk changes."""
import copy
import json
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_rdr2_catalog_numeric_validation import fixture, snapshot
from plugins.rdr2 import server as s

ROW = {'name': 'FIXTURE', 'type': 'Item', 'rate': '0.25', 'min': '1', 'max': '2'}
BAD = [None, {}, False, '', [None], [{}], [{'tableKey': 'FIRST'}],
       [{'tableKey': 'MISSING', 'entries': []}], [{'tableKey': None, 'entries': []}],
       [{'tableKey': 'FIRST', 'entries': {}}], [{'tableKey': 'FIRST', 'entries': [None]}],
       [{'tableKey': 'FIRST', 'entries': [{**ROW, 'opaque': 1}]}]]
for field in ['name', 'type', 'rewardcondition']:
    for value in [None, True, 3, [], {}, 'UNKNOWN']:
        BAD.append([{'tableKey': 'FIRST', 'entries': [{**ROW, field: value}]}])
for field in ['rate', 'min', 'max']:
    for value in [None, True, [], {}, 'bad', float('nan'), float('inf')]:
        BAD.append([{'tableKey': 'FIRST', 'entries': [{**ROW, field: value}]}])
for field in ['min', 'max']:
    BAD.append([{'tableKey': 'FIRST', 'entries': [{**ROW, field: '1.5'}]}])
BAD += [[{'tableKey': 'FIRST', 'entries': [{**ROW, 'rate': -1}]}],
        [{'tableKey': 'FIRST', 'entries': [{**ROW, 'min': 3, 'max': 2}]}],
        [{'tableKey': 'FIRST', 'entries': []}]]  # Duplicates the earlier FIRST edit.


@pytest.fixture
def loot(fixture):
    root, _ = fixture
    name = s.LOOT_FILES[0]
    path = s.data_file_path(name, 'mine')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('''<Root><!--keep--><LootTables><Item key="FIRST"><Opaque value="17"/>
      <Type>AggregateDrop</Type><Entries><!--entries comment--><Item><Name>FIXTURE</Name><Type>Item</Type>
      <Rate value="0.25"/><Min value="1"/><Max value="2"/><RewardCondition ref="KNOWN"/></Item></Entries></Item>
      <Item key="SECOND"><Type>AggregateDrop</Type><Entries/></Item></LootTables></Root>''')
    s.load_file(name)
    return root, path, name


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('existing_backup', [False, True])
def test_invalid_later_table_preserves_all_bytes_and_cached_root(loot, bad, existing_backup):
    root, path, name = loot
    if existing_backup:
        path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    before = snapshot(root)
    cached = s.load_file(name)['root']
    edits = [{'tableKey': 'FIRST', 'entries': [{**ROW, 'rate': 0.5}]}]
    edits = edits + copy.deepcopy(bad) if isinstance(bad, list) else bad
    with pytest.raises(ValueError):
        s.apply_loot_edits(name, edits)
    assert snapshot(root) == before
    assert s.load_file(name)['root'] is cached


@pytest.mark.parametrize('fragment', ['<Opaque value="17"/>', '<Min value="2"/>',
                                   '<Name extra="unknown">OTHER</Name>', '<Min value="1"><Child/></Min>'])
def test_unmodeled_or_repeated_entry_data_is_protected(loot, fragment):
    root, path, name = loot
    doc = s.load_file(name)['root']
    doc.find('.//Entries/Item').append(ET.fromstring(fragment))
    s.save_file(name)
    before = snapshot(root)
    with pytest.raises(ValueError, match='read-only'):
        s.apply_loot_edits(name, [{'tableKey': 'FIRST', 'entries': [ROW]}])
    assert snapshot(root) == before


def test_real_http_rejects_then_saves_exact_quantities_known_choices_and_omissions(loot):
    root, path, name = loot
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def request(edits):
        return Request(f'http://127.0.0.1:{http.server_port}/api/loot/{name}/save',
                       data=json.dumps({'edits': edits}).encode(), headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request([{'tableKey': 'FIRST', 'entries': [{**ROW, 'min': '1.5'}]}]), timeout=5)
        assert failure.value.code == 400
        assert snapshot(root) == before
        rows = [{**ROW, 'rate': '1.25', 'min': '-9007199254740993', 'max': '9007199254740995', 'rewardcondition': 'KNOWN'},
                {'name': 'SECOND', 'type': 'Table', 'rate': 0, 'min': '', 'max': '', 'rewardcondition': ''}]
        with urlopen(request([{'tableKey': 'FIRST', 'entries': rows}]), timeout=5) as response:
            assert json.load(response)['saved'] == 1
        s._files.clear()
        loaded = s.get_loot(name)['tables'][0]['entries']
        assert loaded[0]['min'] == '-9007199254740993'
        assert loaded[0]['max'] == '9007199254740995'
        assert loaded[0]['rate'] == '1.25'
        assert loaded[0]['rewardcondition'] == 'KNOWN'
        assert loaded[1] == {'name': 'SECOND', 'type': 'Table', 'rate': '0.0'}
        assert '<!--keep-->' in path.read_text()
        assert '<!--entries comment-->' in path.read_text()
        assert s.load_file(name)['root'].find('.//LootTables/Item/Opaque').get('value') == '17'
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


def test_failed_loot_write_restores_cache_output_and_new_backup(loot, monkeypatch):
    root, path, name = loot
    before = snapshot(root)
    cached = s.load_file(name)['root']
    real_replace = Path.replace
    def replace(source, destination):
        if Path(destination) == path:
            raise OSError('Injected loot replacement failure')
        return real_replace(source, destination)
    monkeypatch.setattr(Path, 'replace', replace)
    with pytest.raises(OSError):
        s.apply_loot_edits(name, [{'tableKey': 'FIRST', 'entries': [ROW]}])
    assert snapshot(root) == before
    assert s.load_file(name)['root'] is cached
