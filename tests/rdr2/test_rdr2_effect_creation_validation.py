"""Effect creation rejects malformed drafts before writes and preserves exact integers."""
import copy
import json
import threading
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_rdr2_catalog_numeric_validation import fixture, snapshot
from plugins.rdr2 import server as s


@pytest.fixture
def isolated(fixture, monkeypatch):
    root, path = fixture
    monkeypatch.setattr(s, 'LABELS_FILE', root / 'labels.json')
    monkeypatch.setattr(s, 'ORIGIN_PROVENANCE_FILE', root / 'provenance.json')
    monkeypatch.setattr(s, '_ORIGIN_MARKER_CACHE', {})
    return root, path


BASE = {'key': 'LEX_FIXTURE_EFFECT', 'behavior': 'BEHAVIOR', 'durationcategory': ''}
BAD = [None, [], {}, {**BASE, 'extra': 1}]
for field in ['key', 'label', 'behavior', 'durationcategory']:
    for bad in [None, True, 3, [], {}]:
        BAD.append({**BASE, field: bad})
for field in ['value', 'time', 'timeunits', 'percent']:
    for bad in [None, True, [], {}, '', float('nan'), float('inf')]:
        BAD.append({**BASE, field: bad})
for field in ['value', 'time', 'timeunits']:
    for bad in [1.5, '1.5']:
        BAD.append({**BASE, field: bad})
for bad in [-1, 4, '9007199254740993']:
    BAD.append({**BASE, 'timeunits': bad})
BAD.extend([{**BASE, 'behavior': 'UNKNOWN'}, {**BASE, 'durationcategory': 'UNKNOWN'},
            {**BASE, 'key': 'bad key'}, {**BASE, 'key': '0x00000001'}])


@pytest.mark.parametrize('existing_backup', [False, True])
@pytest.mark.parametrize('bad', BAD)
def test_rejected_creation_preserves_all_files_and_cached_xml(isolated, bad, existing_backup):
    root, path = isolated
    if existing_backup:
        path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    s.LABELS_FILE.write_text('{"effects":{"old":"Keep"}}')
    s.ORIGIN_PROVENANCE_FILE.write_text('{"schema":2,"customCatalogEffects":["old"]}')
    before = snapshot(root)
    cached = ET.tostring(s.load_file(s.CATALOG_FILE)['root'])
    with pytest.raises(ValueError):
        s.create_catalog_effect(copy.deepcopy(bad))
    assert snapshot(root) == before
    assert ET.tostring(s.load_file(s.CATALOG_FILE)['root']) == cached


def test_http_rejects_fraction_then_creates_exact_integers_and_metadata(isolated):
    root, path = isolated
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def request(body):
        return Request(f'http://127.0.0.1:{http.server_port}/api/catalog/effects/create',
                       data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request({**BASE, 'time': '1.5'}), timeout=5)
        assert failure.value.code == 400
        assert snapshot(root) == before
        with urlopen(request({**BASE, 'label': 'Fixture', 'value': '9007199254740993',
                              'time': '-9007199254740993', 'timeunits': '3',
                              'percent': '0.123456789123'}), timeout=5) as response:
            result = json.load(response)
        s._files.clear()
        doc = s.load_file(s.CATALOG_FILE)['root']
        effect = next(e for e in doc.findall('./effectsids/item') if e.findtext('key') == result['key'])
        assert effect.find('value').get('value') == '9007199254740993'
        assert effect.find('time').get('value') == '-9007199254740993'
        assert effect.find('timeunits').get('value') == '3'
        assert effect.find('percent').get('value') == '0.123456789123'
        assert effect.findtext('durationcategory') == ''
        assert '<!--keep-->' in path.read_text()
        assert doc.find('.//multiplicity/item/quantity').get('value') == '-1'
        labels = json.loads(s.LABELS_FILE.read_text())
        assert labels['effects'][result['key']] == 'Fixture'
        assert labels['effectSymbols'][result['key']] == BASE['key']
        assert result['key'] in json.loads(s.ORIGIN_PROVENANCE_FILE.read_text())['customCatalogEffects']
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
