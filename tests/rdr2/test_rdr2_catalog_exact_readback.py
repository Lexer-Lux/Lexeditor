"""Exact XML quantities survive catalog reading and JSON transfer to a browser."""
import json
import threading
import xml.etree.ElementTree as ET
from urllib.request import urlopen

import pytest
from test_rdr2_catalog_numeric_validation import fixture
from plugins.rdr2 import server as s


@pytest.mark.parametrize('raw,expected', [('0', 0), ('-1', -1), ('1.0', 1), ('1e3', 1000),
    ('9007199254740991', 9007199254740991), ('9007199254740992', '9007199254740992'),
    ('9007199254740993', '9007199254740993'), ('-9007199254740993', '-9007199254740993'),
    ('9007199254740993.0', '9007199254740993'), ('9.007199254740993e15', '9007199254740993')])
def test_catalog_whole_quantity_reader(raw, expected):
    assert s._catalog_quantity(raw) == expected


@pytest.mark.parametrize('raw', ['1.5', 'NaN', 'Infinity', '-Infinity', '', 'bad'])
def test_invalid_catalog_quantity_is_not_truncated_or_defaulted(raw):
    with pytest.raises(ValueError):
        s._catalog_quantity(raw)


def test_actual_catalog_http_preserves_saved_prices_yields_and_shop_counts(fixture, monkeypatch):
    root, _ = fixture
    # Only unrelated provenance sources/caching are stubbed; production XML
    # writers, catalog builder, HTTP serialization and quantity parsing run.
    monkeypatch.setattr(s, 'LABELS_FILE', root / 'labels.json')
    monkeypatch.setattr(s, 'ORIGIN_PROVENANCE_FILE', root / 'provenance.json')
    monkeypatch.setattr(s, '_CATALOG_RESULT_CACHE', {})
    monkeypatch.setattr(s, 'provenance_cache_key', lambda ds: s.load_file(s.CATALOG_FILE, ds)['mtime'])
    monkeypatch.setattr(s, 'build_static_provenance', lambda ds, items: {})
    monkeypatch.setattr(s, 'load_script_provenance_index', lambda: {})
    monkeypatch.setattr(s, 'provenance_coverage', lambda ds: [])
    doc = s.load_file(s.CATALOG_FILE)['root']
    shops = ET.SubElement(doc, 'shopsinventories')
    shop = ET.SubElement(shops, 'item')
    ET.SubElement(shop, 'type').text = 'SHOP_FIXTURE'
    rows = ET.SubElement(shop, 'items')
    item = ET.SubElement(rows, 'item')
    ET.SubElement(item, 'item').text = 'FIXTURE'
    groups = ET.SubElement(item, 'requirementgroups')
    for count in ['9007199254740993.0', '1', '1000.0']:
        group = ET.SubElement(groups, 'item')
        ET.SubElement(group, 'count', {'value': count})
    s.save_file(s.CATALOG_FILE)
    assert s.apply_catalog_edits({
        'prices': [{'item': 'FIXTURE', 'section': 'buy', 'costKey': 'BUY', 'partItem': 'CURRENCY_CASH', 'qty': '9007199254740993'}],
        'yields': [{'item': 'FIXTURE', 'section': 'buy', 'costKey': 'BUY', 'qty': '9007199254740995'}]}) == 2
    s._files.clear()
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    try:
        with urlopen(f'http://127.0.0.1:{http.server_port}/api/catalog?ds=mine', timeout=5) as response:
            result = json.load(response)
        item = next(row for row in result['items'] if row['key'] == 'FIXTURE')
        assert item['buy'][0]['parts'][0]['qty'] == '9007199254740993'
        assert item['buy'][0]['yield'] == '9007199254740995'
        assert item['shopListings'][0]['quantities'] == [1, 1000, '9007199254740993']
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
