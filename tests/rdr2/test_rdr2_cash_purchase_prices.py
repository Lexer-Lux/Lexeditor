"""Cash purchase toggles persist actual costs without editing merchant membership."""
import json
import threading
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_rdr2_catalog_numeric_validation import fixture, snapshot
from plugins.rdr2 import server as s


def prepare():
    root = s.load_file(s.CATALOG_FILE)['root']
    item = s.find_catalog_item(root, 'FIXTURE')
    costs = item.find('acquirecosts')
    costs.clear()
    cost = ET.SubElement(costs, 'item')
    ET.SubElement(cost, 'key').text = 'CRAFT_EXISTING'
    ET.SubElement(cost, 'costtype').text = 'COST_TYPE_CRAFT'
    ET.SubElement(cost, 'opaque', {'value': '17'})
    ET.SubElement(root, 'merchant_membership', {'value': 'unchanged'})
    root.append(ET.fromstring('<shopsinventories><item><type>SHOP_FIXTURE</type><items><item>'
                             '<item>FIXTURE</item><requirementgroups><item><opaque value="7"/></item>'
                             '</requirementgroups></item></items></item></shopsinventories>'))
    root.append(ET.fromstring('<cataloglayout><item><shoptype>SHOP_FIXTURE</shoptype><pages><item>'
                             '<key>PAGE_FIXTURE</key><items><item><key>FIXTURE</key></item></items>'
                             '</item></pages></item></cataloglayout>'))
    s.save_file(s.CATALOG_FILE)


def test_enable_price_and_dependent_yield_then_disable_reload(fixture):
    _, path = fixture
    prepare()
    before = ET.tostring(s.load_file(s.CATALOG_FILE)['root'].find('merchant_membership'))
    membership = {name: ET.tostring(s.load_file(s.CATALOG_FILE)['root'].find(name))
                  for name in ['shopsinventories', 'cataloglayout']}
    assert s.apply_catalog_edits({'buyability': [{'item': 'FIXTURE', 'buyable': True, 'cents': '129'}],
                                 'yields': [{'item': 'FIXTURE', 'section': 'buy', 'costKey': 'COST_SHOP_DEFAULT', 'qty': 4}]}) == 2
    s._files.clear()
    root = s.load_file(s.CATALOG_FILE)['root']
    cost = next(cost for cost in root.findall('.//acquirecosts/item') if s.txt(cost, 'key') == 'COST_SHOP_DEFAULT')
    assert s.txt(cost, 'costtype') == 'COST_TYPE_PRICE'
    assert cost.find('quantity').get('value') == '4'
    assert cost.find('items/item/quantity').get('value') == '129'
    assert ET.tostring(root.find('merchant_membership')) == before
    assert {name: ET.tostring(root.find(name)) for name in membership} == membership
    assert root.find('.//acquirecosts/item/opaque').get('value') == '17'
    assert s.apply_catalog_edits({'buyability': [{'item': 'FIXTURE', 'buyable': True, 'cents': '9007199254740993'}]}) == 1
    s._files.clear()
    root = s.load_file(s.CATALOG_FILE)['root']
    assert root.find('.//acquirecosts/item/items/item/quantity').get('value') == '9007199254740993'
    cost = next(cost for cost in root.findall('.//acquirecosts/item') if s.txt(cost, 'key') == 'COST_SHOP_DEFAULT')
    assert cost.find('quantity').get('value') == '4'
    assert s.apply_catalog_edits({'buyability': [{'item': 'FIXTURE', 'buyable': False}]}) == 1
    s._files.clear()
    root = s.load_file(s.CATALOG_FILE)['root']
    assert all(s.txt(cost, 'costtype') != 'COST_TYPE_PRICE' for cost in root.findall('.//acquirecosts/item'))
    assert root.find('.//acquirecosts/item/opaque').get('value') == '17'
    assert ET.tostring(root.find('merchant_membership')) == before
    assert {name: ET.tostring(root.find(name)) for name in membership} == membership
    assert s.shop_stock_types(root, 'FIXTURE') == ['SHOP_FIXTURE']
    assert s.catalog_page_shops(root, 'FIXTURE') == ['SHOP_FIXTURE']
    assert '<!--keep-->' in path.read_text()


def test_rejected_later_edit_leaves_new_price_uncreated_in_cache_and_disk(fixture):
    root, _ = fixture
    prepare()
    before = snapshot(root)
    cached = ET.tostring(s.load_file(s.CATALOG_FILE)['root'])
    with pytest.raises(ValueError):
        s.apply_catalog_edits({'buyability': [{'item': 'FIXTURE', 'buyable': True, 'cents': 129}],
                              'effects': [{'key': '0x00000001', 'field': 'id', 'value': 'MISSING'}]})
    assert snapshot(root) == before
    assert ET.tostring(s.load_file(s.CATALOG_FILE)['root']) == cached


def test_real_http_enable_and_remove_without_vanilla_files(fixture):
    root, _ = fixture
    prepare()
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def request(rows):
        return Request(f'http://127.0.0.1:{http.server_port}/api/catalog/save',
                       data=json.dumps({'buyability': rows}).encode(), headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request([{'item': 'FIXTURE', 'buyable': True, 'cents': 129.5}]), timeout=5)
        assert failure.value.code == 400
        assert snapshot(root) == before
        for enabled in [True, False]:
            with urlopen(request([{'item': 'FIXTURE', 'buyable': enabled, 'cents': 129}]), timeout=5) as response:
                assert json.load(response)['saved'] == 1
            s._files.clear()
            costs = s.load_file(s.CATALOG_FILE)['root'].findall('.//acquirecosts/item')
            assert any(s.txt(cost, 'key') == 'COST_SHOP_DEFAULT' for cost in costs) == enabled
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
