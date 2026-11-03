"""Item creation validates before output and uses isolated localization metadata."""
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
    for variable, filename in [('VANILLA_LOCALIZATION_FILE', 'baseline.json'),
                               ('ONLINE_LOCALIZATION_FILE', 'online.json'),
                               ('ORIGIN_PROVENANCE_FILE', 'provenance.json')]:
        monkeypatch.setattr(s, variable, root / filename)
    s.VANILLA_LOCALIZATION_FILE.write_text('{}')
    monkeypatch.setattr(s, '_ORIGIN_MARKER_CACHE', {})
    doc = s.load_file(s.CATALOG_FILE)['root']
    template = ET.fromstring('''<item key="LEX_GUNPOWDER"><key>LEX_GUNPOWDER</key>
      <category>CI_CATEGORY_MATERIALS</category><group>PROVISION</group>
      <multiplicity><item><quantity value="20"/><slotid>SLOTID_ANY</slotid></item></multiplicity>
      <acquirecosts><item>old recipe</item></acquirecosts><sellprices><item>old price</item></sellprices>
      <effectids><item>old effect</item></effectids><opaque value="keep"/></item>''')
    doc.find('./catalog/items').append(template)
    s.save_file(s.CATALOG_FILE)
    return root, path


BASE = {'key': 'LEX_FIXTURE', 'name': 'Fixture', 'description': 'Description'}
BAD = [None, [], {}, {**BASE, 'opaque': 1}]
for field in ['key', 'name', 'description', 'category', 'group']:
    for bad in [None, True, 3, [], {}]:
        BAD.append({**BASE, field: bad})
for bad in [None, True, [], {}, '', 0, -1, 1.5, '1.5', float('nan'), float('inf')]:
    BAD.append({**BASE, 'capacity': bad})
for field in ['category', 'group']:
    for bad in ['', 'UNKNOWN']:
        BAD.append({**BASE, field: bad})
for field in ['name', 'description']:
    for bad in ['bad\x00text', '\ud800']:
        BAD.append({**BASE, field: bad})
BAD.extend([{**BASE, 'key': 'bad key'}, {**BASE, 'key': 'LEX_GUNPOWDER'}])


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('existing_backup', [False, True])
def test_invalid_creation_preserves_catalog_localization_and_provenance(isolated, bad, existing_backup):
    root, path = isolated
    backup = path.with_suffix(path.suffix + '.bak')
    if not existing_backup:
        backup.unlink()
    (s.ds_dir('mine') / s.LOCALIZATION_FILE).write_text('[LEXEDITOR OVERRIDES]\nOLD = Keep\n')
    s.ORIGIN_PROVENANCE_FILE.write_text('{"schema":2,"customCatalogItems":["OLD"]}')
    before = snapshot(root)
    cached = ET.tostring(s.load_file(s.CATALOG_FILE)['root'])
    with pytest.raises(ValueError):
        s.create_catalog_item(copy.deepcopy(bad))
    assert snapshot(root) == before
    assert ET.tostring(s.load_file(s.CATALOG_FILE)['root']) == cached


def test_http_item_creation_rejects_then_reloads_exact_capacity_and_strings(isolated):
    root, path = isolated
    (s.ds_dir('mine') / 'install.xml').write_text('<Install><Resources><Resource><Opaque>keep</Opaque></Resource></Resources></Install>')
    http = s.create_server(0)
    original_template = ET.tostring(s.find_catalog_item(s.load_file(s.CATALOG_FILE)['root'], 'LEX_GUNPOWDER'))
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def request(body):
        return Request(f'http://127.0.0.1:{http.server_port}/api/catalog/create',
                       data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request({**BASE, 'category': 'UNKNOWN'}), timeout=5)
        assert failure.value.code == 400
        assert snapshot(root) == before
        with urlopen(request({**BASE, 'capacity': '9007199254740993'}), timeout=5) as response:
            assert json.load(response)['key'] == BASE['key']
        s._files.clear()
        doc = s.load_file(s.CATALOG_FILE)['root']
        item = s.find_catalog_item(doc, BASE['key'])
        assert ET.tostring(s.find_catalog_item(doc, 'LEX_GUNPOWDER')) == original_template
        assert item.find('multiplicity/item/quantity').get('value') == '9007199254740993'
        assert item.findtext('category') == 'CI_CATEGORY_MATERIALS'
        assert item.findtext('group') == 'PROVISION'
        assert item.find('opaque').get('value') == 'keep'
        for tag in ['acquirecosts', 'sellprices', 'effectids']:
            assert not list(item.find(tag))
        assert s.parse_gxt2(s.ds_dir('mine') / s.LOCALIZATION_FILE) == {'LEX_FIXTURE': 'Fixture', 'LEX_FIXTURE_DESC': 'Description'}
        assert BASE['key'] in json.loads(s.ORIGIN_PROVENANCE_FILE.read_text())['customCatalogItems']
        install = ET.parse(s.ds_dir('mine') / 'install.xml')
        assert install.findtext('.//DataFile') == s.LOCALIZATION_FILE
        assert install.findtext('.//Opaque') == 'keep'
        assert '<!--keep-->' in path.read_text()
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
