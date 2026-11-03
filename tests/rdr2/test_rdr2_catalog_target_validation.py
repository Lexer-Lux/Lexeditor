"""Rejected catalog shapes and targets preserve earlier valid edits and backups."""
import copy
import json
import threading
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_rdr2_catalog_numeric_validation import fixture, snapshot
from plugins.rdr2 import server as s

BAD = [
    {'unknown': []}, {'prices': [{'item': 'FIXTURE', 'qty': 1}]},
    {'carry': [{'item': 'FIXTURE', 'slot': 'SLOTID_ANY', 'qty': 2, 'opaque': 1}]},
    {'carry': [{'item': None, 'slot': 'SLOTID_ANY', 'qty': 2}]},
    {'carry': [{'item': 'MISSING', 'slot': 'SLOTID_ANY', 'qty': 2}]},
    {'prices': [{'item': 'FIXTURE', 'section': 'other', 'costKey': 'BUY', 'partItem': 'CURRENCY_CASH', 'qty': 2}]},
    {'prices': [{'item': 'FIXTURE', 'section': 'buy', 'costKey': 'MISSING', 'partItem': 'CURRENCY_CASH', 'qty': 2}]},
    {'prices': [{'item': 'FIXTURE', 'section': 'buy', 'costKey': 'BUY', 'partItem': 'MISSING', 'qty': 2}]},
    {'yields': [{'item': 'FIXTURE', 'section': 'buy', 'costKey': 'MISSING', 'qty': 2}]},
    {'effects': [{'key': 'MISSING', 'field': 'value', 'value': 2}]},
    {'effects': [{'key': '0x00000001', 'field': 'opaque', 'value': 2}]},
    {'effects': [{'key': '0x00000001', 'field': 'id', 'value': 'MISSING'}]},
    {'effects': [{'key': '0x00000001', 'field': 'id', 'value': True}]},
    {'effects': [{'key': '0x00000001', 'field': 'durationcategory', 'value': 'MISSING'}]},
    {'itemEffects': [{'item': 'FIXTURE', 'effects': '0x00000001'}]},
    {'itemEffects': [{'item': 'FIXTURE', 'effects': [None]}]},
    {'itemEffects': [{'item': 'FIXTURE', 'effects': ['MISSING']}]},
]
for family in ['buyability', 'sellability', 'itemTags', 'descriptions', 'quickSelect', 'craft']:
    BAD.append({family: [{'item': 'FIXTURE', 'extra': 1}]})


@pytest.mark.parametrize('existing_backup', [False, True])
@pytest.mark.parametrize('bad', BAD)
def test_invalid_target_after_valid_quantity_is_atomic(fixture, bad, existing_backup):
    root, path = fixture
    if existing_backup:
        path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    before = snapshot(root)
    cached = ET.tostring(s.load_file(s.CATALOG_FILE)['root'])
    batch = copy.deepcopy(bad)
    batch.setdefault('carry', []).insert(0, {'item': 'FIXTURE', 'slot': 'SLOTID_ANY', 'qty': 9})
    with pytest.raises(ValueError):
        s.apply_catalog_edits(batch)
    assert snapshot(root) == before
    assert ET.tostring(s.load_file(s.CATALOG_FILE)['root']) == cached


def test_http_unknown_effect_does_not_apply_valid_price_and_known_choice_saves(fixture):
    root, path = fixture
    # A comment and unrelated engine value must remain untouched.
    doc = s.load_file(s.CATALOG_FILE)['root']
    ET.SubElement(doc.find('./effectsids/item'), 'durationcategory').text = 'DURATION_FIXTURE'
    s.save_file(s.CATALOG_FILE)
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def request(batch):
        return Request(f'http://127.0.0.1:{http.server_port}/api/catalog/save',
                       data=json.dumps(batch).encode(), headers={'Content-Type': 'application/json'})
    price = {'item': 'FIXTURE', 'section': 'buy', 'costKey': 'BUY', 'partItem': 'CURRENCY_CASH', 'qty': 129}
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request({'prices': [price], 'effects': [{'key': '0x00000001', 'field': 'id', 'value': 'MISSING'}]}), timeout=5)
        assert failure.value.code == 400
        assert snapshot(root) == before
        assert s.load_file(s.CATALOG_FILE)['root'].find('.//acquirecosts/item/items/item/quantity').get('value') == '100'
        with urlopen(request({'prices': [price], 'effects': [{'key': '0x00000001', 'field': 'id', 'value': 'BEHAVIOR'},
                                                           {'key': '0x00000001', 'field': 'durationcategory', 'value': 'DURATION_FIXTURE'}]}), timeout=5) as response:
            assert json.load(response)['saved'] == 3
        s._files.clear()
        loaded = s.load_file(s.CATALOG_FILE)['root']
        assert loaded.find('.//acquirecosts/item/items/item/quantity').get('value') == '129'
        assert loaded.findtext('./effectsids/item/id') == 'BEHAVIOR'
        assert loaded.findtext('./effectsids/item/durationcategory') == 'DURATION_FIXTURE'
        assert '<!--keep-->' in path.read_text()
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


def test_known_item_effect_assignment_creates_missing_container_and_reloads(fixture):
    _, path = fixture
    assert s.load_file(s.CATALOG_FILE)['root'].find('.//catalog/items/item/effectids') is None
    assert s.apply_catalog_edits({'itemEffects': [{'item': 'FIXTURE', 'effects': ['0x00000001']}]}) == 1
    s._files.clear()
    item = s.find_catalog_item(s.load_file(s.CATALOG_FILE)['root'], 'FIXTURE')
    assert item.findtext('effectids/item/key') == '0x00000001'
    assert item.find('multiplicity/item/quantity').get('value') == '-1'
    assert '<!--keep-->' in path.read_text()
    assert s.apply_catalog_edits({'itemEffects': [{'item': 'FIXTURE', 'effects': []}]}) == 1
    s._files.clear()
    assert not s.find_catalog_item(s.load_file(s.CATALOG_FILE)['root'], 'FIXTURE').findall('effectids/item')
