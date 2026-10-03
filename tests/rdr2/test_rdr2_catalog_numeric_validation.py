"""Catalog numeric batches are validated before cached XML or files change."""
import copy
import json
import threading
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from plugins.rdr2 import server as s

XML = '''<Root><!--keep--><catalog><items><item key="FIXTURE"><multiplicity><item>
<quantity value="-1"/><slotid>SLOTID_ANY</slotid></item></multiplicity>
<acquirecosts><item><key>BUY</key><quantity value="1"/><items><item><item>CURRENCY_CASH</item>
<quantity value="100"/></item></items></item></acquirecosts></item></items></catalog>
<effectsids><item><key>0x00000001</key><id>BEHAVIOR</id><value value="2"/>
<percent value="0.5"/><time value="3"/><timeunits value="1"/></item></effectsids></Root>'''


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    mine = tmp_path / 'mine'
    mine.mkdir()
    monkeypatch.setattr(s, 'DATASETS', {'mine': {'dir': mine, 'readonly': False}})
    monkeypatch.setattr(s, '_files', {})
    monkeypatch.delenv('LEXEDITOR_MOD_READ_ONLY', raising=False)
    path = s.data_file_path(s.CATALOG_FILE, 'mine')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(XML, encoding='utf-8')
    s.load_file(s.CATALOG_FILE)
    return tmp_path, path


CASES = []
for family, key in [('prices', 'qty'), ('yields', 'qty'), ('bundles', 'qty'), ('carry', 'qty'),
                    ('sellability', 'cents'), ('buyability', 'cents')]:
    for value in [True, None, [], {}, '', 1.5, '1.5', float('nan'), float('inf')]:
        CASES.append({family: [{'item': 'FIXTURE', key: value}]})
for field in ['value', 'time', 'timeunits', 'percent']:
    for value in [True, None, [], {}, '', float('nan'), float('inf'), 10**400]:
        if field != 'percent' and isinstance(value, int) and not isinstance(value, bool):
            continue  # XML has no established storage maximum for integer fields.
        CASES.append({'effects': [{'key': '0x00000001', 'field': field, 'value': value}]})
for value in [0, -1, 1.5, True, None]:
    CASES.append({'craft': [{'item': 'FIXTURE', 'entries': [{'yield': value}]}]})
    CASES.append({'craft': [{'item': 'FIXTURE', 'entries': [{'parts': [{'item': 'INPUT', 'qty': value}]}]}]})
for family in ['prices', 'sellability', 'buyability']:
    CASES.append({family: [{'item': 'FIXTURE', 'qty' if family == 'prices' else 'cents': -1}]})
for family in ['yields', 'bundles']:
    CASES.append({family: [{'item': 'FIXTURE', 'qty': 0}]})
CASES.extend([None, [], {'prices': {}}, {'effects': [None]}, {'craft': [{'entries': {}}]},
              {'craft': [{'entries': [{'parts': [None]}]}]},
              {'buyability': [{'buyable': 'false'}]}, {'sellability': [{'sellable': 1}]}])


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('bad', CASES)
@pytest.mark.parametrize('existing_backup', [False, True])
def test_invalid_later_family_does_not_mutate_cache_or_disk(fixture, bad, existing_backup):
    root, path = fixture
    if existing_backup:
        path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    before = snapshot(root)
    cached = ET.tostring(s.load_file(s.CATALOG_FILE)['root'])
    batch = copy.deepcopy(bad)
    if isinstance(batch, dict):
        batch.setdefault('carry', []).insert(0, {'item': 'FIXTURE', 'slot': 'SLOTID_ANY', 'qty': 7})
    with pytest.raises(ValueError):
        s.apply_catalog_edits(batch)
    assert snapshot(root) == before
    assert ET.tostring(s.load_file(s.CATALOG_FILE)['root']) == cached


def test_real_http_rejects_and_valid_exact_values_reload(fixture):
    root, path = fixture
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{http.server_port}/api/catalog/save'
    def request(batch):
        return Request(url, data=json.dumps(batch).encode(), headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request({'carry': [{'item': 'FIXTURE', 'slot': 'SLOTID_ANY', 'qty': 1.5}]}), timeout=5)
        assert failure.value.code == 400
        assert 'integer' in json.load(failure.value)['error']
        assert snapshot(root) == before
        batch = {'carry': [{'item': 'FIXTURE', 'slot': 'SLOTID_ANY', 'qty': -1}],
                 'prices': [{'item': 'FIXTURE', 'section': 'buy', 'costKey': 'BUY', 'partItem': 'CURRENCY_CASH', 'qty': 0}],
                 'yields': [{'item': 'FIXTURE', 'section': 'buy', 'costKey': 'BUY', 'qty': 4}],
                 'effects': [{'key': '0x00000001', 'field': 'value', 'value': '9007199254740993'},
                             {'key': '0x00000001', 'field': 'percent', 'value': 0.25}]}
        with urlopen(request(batch), timeout=5) as response:
            assert json.load(response)['saved'] == 5
        s._files.clear()
        doc = s.load_file(s.CATALOG_FILE)['root']
        assert doc.find('.//multiplicity/item/quantity').get('value') == '-1'
        assert doc.find('.//acquirecosts/item/quantity').get('value') == '4'
        assert doc.find('.//acquirecosts/item/items/item/quantity').get('value') == '0'
        assert doc.find('./effectsids/item/value').get('value') == '9007199254740993'
        assert doc.find('./effectsids/item/percent').get('value') == '0.25'
        assert path.with_suffix(path.suffix + '.bak').read_text() == XML
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


def test_positive_craft_and_bundle_quantities_preserve_other_records(fixture):
    _, _ = fixture
    loot_name = s.LOOT_FILES[0]
    path = s.data_file_path(loot_name, 'mine')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<Root><LootTables><Item key="BUNDLE"><Entries><Item><Name>OUTPUT</Name>'
                    '<Min value="1"/><Max value="1"/><Opaque value="17"/></Item></Entries></Item>'
                    '</LootTables></Root>')
    batch = {'bundles': [{'key': f'{loot_name}|BUNDLE|OUTPUT', 'qty': 8}],
             'craft': [{'item': 'FIXTURE', 'entries': [{'key': 'COST_CRAFTING_FIRE', 'yield': 6,
                       'parts': [{'item': 'INPUT', 'qty': 9}], 'unlocks': ['UNLOCK_FIXTURE']}]}]}
    before = copy.deepcopy(batch)
    assert s.apply_catalog_edits(batch) == 2
    assert batch == before
    s._files.clear()
    catalog = s.load_file(s.CATALOG_FILE)['root']
    craft = next(item for item in catalog.findall('.//acquirecosts/item')
                 if item.findtext('key') == 'COST_CRAFTING_FIRE')
    assert craft.find('quantity').get('value') == '6'
    assert craft.find('items/item/quantity').get('value') == '9'
    assert craft.findtext('unlocks/item/key') == 'UNLOCK_FIXTURE'
    assert catalog.find('.//acquirecosts/item/items/item/quantity').get('value') == '100'
    loot = s.load_file(loot_name)['root']
    assert loot.find('.//Entries/Item/Min').get('value') == '8'
    assert loot.find('.//Entries/Item/Max').get('value') == '8'
    assert loot.find('.//Entries/Item/Opaque').get('value') == '17'
