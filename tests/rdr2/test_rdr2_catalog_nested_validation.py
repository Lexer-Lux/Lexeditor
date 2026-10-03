"""Recipe/tag schemas reject malformed nested data without discarding it on Save."""
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
    {'craft': [{'item': 'FIXTURE', 'entries': [{'unknown': 1}]}]},
    {'craft': [{'item': 'FIXTURE', 'entries': [{'parts': [{}]}]}]},
    {'craft': [{'item': 'FIXTURE', 'entries': [{'parts': [{'item': 'INPUT', 'opaque': 1}]}]}]},
]
for value in [None, True, 0, [], {}, '']:
    BAD.append({'craft': [{'item': 'FIXTURE', 'entries': [{'key': value}]}]})
    BAD.append({'craft': [{'item': 'FIXTURE', 'entries': [{'parts': [{'item': value}]}]}]})
    BAD.append({'craft': [{'item': 'FIXTURE', 'entries': [{'unlocks': [value]}]}]})
for value in [None, True, 'UNLOCK', {}]:
    BAD.append({'craft': [{'item': 'FIXTURE', 'entries': [{'unlocks': value}]}]})
for value in [None, True, {}, 'CI_TAG_FIXTURE', [None], [{}], ['CI_TAG_FIXTURE'],
              [{'key': 'CI_TAG_FIXTURE'}], [{'key': 'CI_TAG_FIXTURE', 'type': '0x00000001', 'opaque': 1}]]:
    BAD.append({'itemTags': [{'item': 'FIXTURE', 'tags': value}]})
for field in ['key', 'type']:
    for value in [None, True, 0, [], {}, '']:
        tag = {'key': 'CI_TAG_FIXTURE', 'type': '0x00000001'}
        tag[field] = value
        BAD.append({'itemTags': [{'item': 'FIXTURE', 'tags': [tag]}]})


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('existing_backup', [False, True])
def test_invalid_nested_later_family_preserves_prior_valid_edit(fixture, bad, existing_backup):
    root, path = fixture
    if existing_backup:
        path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    before = snapshot(root)
    cached = ET.tostring(s.load_file(s.CATALOG_FILE)['root'])
    batch = copy.deepcopy(bad)
    batch['carry'] = [{'item': 'FIXTURE', 'slot': 'SLOTID_ANY', 'qty': 9}]
    with pytest.raises(ValueError):
        s.apply_catalog_edits(batch)
    assert snapshot(root) == before
    assert ET.tostring(s.load_file(s.CATALOG_FILE)['root']) == cached


def test_http_rejects_nontext_unlock_and_valid_recipe_tag_round_trip(fixture):
    root, path = fixture
    doc = s.load_file(s.CATALOG_FILE)['root']
    tags = ET.SubElement(s.find_catalog_item(doc, 'FIXTURE'), 'tags')
    tag = ET.SubElement(tags, 'item')
    ET.SubElement(tag, 'key').text = 'CI_TAG_FIXTURE'
    ET.SubElement(tag, 'type').text = '0x00000001'
    s.save_file(s.CATALOG_FILE)
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def request(batch):
        return Request(f'http://127.0.0.1:{http.server_port}/api/catalog/save',
                       data=json.dumps(batch).encode(), headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request({'craft': [{'item': 'FIXTURE', 'entries': [{'unlocks': [None]}]}]}), timeout=5)
        assert failure.value.code == 400
        assert snapshot(root) == before
        batch = {'craft': [{'item': 'FIXTURE', 'entries': [{'key': 'COST_CRAFTING_FIRE', 'yield': 6,
                    'parts': [{'item': 'INPUT', 'qty': 9}], 'unlocks': ['UNLOCK_FIXTURE']}]}],
                 'itemTags': [{'item': 'FIXTURE', 'tags': [{'key': 'CI_TAG_FIXTURE', 'type': '0x00000001'}]}]}
        with urlopen(request(batch), timeout=5) as response:
            assert json.load(response)['saved'] == 2
        s._files.clear()
        item = s.find_catalog_item(s.load_file(s.CATALOG_FILE)['root'], 'FIXTURE')
        cost = next(cost for cost in item.findall('acquirecosts/item') if s.txt(cost, 'key') == 'COST_CRAFTING_FIRE')
        assert cost.find('quantity').get('value') == '6'
        assert cost.findtext('items/item/item') == 'INPUT'
        assert cost.find('items/item/quantity').get('value') == '9'
        assert cost.findtext('unlocks/item/key') == 'UNLOCK_FIXTURE'
        assert s.parse_catalog_tags(item.find('tags')) == [{'key': 'CI_TAG_FIXTURE', 'type': '0x00000001'}]
        assert item.find('multiplicity/item/quantity').get('value') == '-1'
        assert '<!--keep-->' in path.read_text()
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
