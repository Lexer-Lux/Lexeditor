"""Merchant PDATA, state, runtime overrides and install mappings commit together."""
import copy
import json
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_rdr2_merchant_batch_validation import merchants, fixture, SHOP
from test_rdr2_catalog_numeric_validation import snapshot
from plugins.rdr2 import server as s


def write():
    s.write_shop_buyer_data({SHOP: ['FIXTURE', '0XDEADBEEF']},
                           {SHOP: ['0XDEADBEEF']}, {SHOP: {'FIXTURE': 'accept'}})


@pytest.mark.parametrize('target', ['pdata', 'state', 'csv', 'install'])
@pytest.mark.parametrize('existing', [False, True])
def test_failed_output_restores_all_files_and_retry_reloads(merchants, monkeypatch, target, existing):
    root = merchants
    install = s.EDITABLE_MOD_ROOT / 'install.xml'
    install.write_text('<Install><Resources><Resource><Opaque>keep</Opaque></Resource></Resources></Install>')
    paths = {'pdata': s.BUYER_DATA_FILE, 'state': s.BUYER_STATE_FILE,
             'csv': s.BUYER_OVERRIDE_FILE, 'install': install}
    if existing:
        for path in paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
        paths['pdata'].write_bytes(b'original pdata')
        paths['csv'].write_bytes(b'original csv')
        paths['state'].write_text('{"source":"authored fixture","opaque":{"keep":true}}')
    before = snapshot(root)
    real_replace = Path.replace
    failed = False
    def replace(path, destination):
        nonlocal failed
        if Path(destination) == paths[target] and not failed:
            failed = True
            raise OSError('Injected merchant replacement failure')
        return real_replace(path, destination)
    monkeypatch.setattr(Path, 'replace', replace)
    with pytest.raises(OSError, match='Injected merchant replacement failure'):
        write()
    assert failed
    assert snapshot(root) == before
    assert not list(root.rglob('*.tmp'))
    if not existing:
        assert not paths['pdata'].parent.exists()
        assert not paths['csv'].parent.exists()
    write()
    loaded = s.get_shop_buyers()
    assert loaded['buyers'][SHOP] == ['0XDEADBEEF', 'FIXTURE']
    assert loaded['vanillaBuyers'][SHOP] == ['0XDEADBEEF']
    assert loaded['overrides'][SHOP] == {'FIXTURE': 'accept'}
    assert paths['csv'].read_text() == f'shop,item,mode\n{SHOP},FIXTURE,accept\n'
    tree = ET.parse(install)
    assert tree.findtext('.//FilePath') == paths['pdata'].relative_to(s.EDITABLE_MOD_ROOT).as_posix()
    assert tree.findtext('.//Opaque') == 'keep'
    pdata = ET.parse(paths['pdata'])
    assert [row.text for row in pdata.findall('./attributeValueStringStore/item')] == ['0XDEADBEEF', 'FIXTURE', SHOP]
    if existing:
        state = json.loads(paths['state'].read_text())
        assert state['source'] == 'authored fixture'
        assert state['opaque'] == {'keep': True}
    assert not list(root.rglob('*.tmp'))


BAD = []
for field in ['buyers', 'vanilla', 'overrides']:
    for value in [[], False, {'UNKNOWN': []}, {SHOP: None}, {SHOP: [True]}, {SHOP: ['']}, {SHOP: ['BAD,CSV']}]:
        BAD.append((field, value))
BAD += [('overrides', {SHOP: {'FIXTURE': mode}}) for mode in [None, True, 'default', 'unknown']]
BAD += [('overrides', {SHOP: {'FIXTURE': 'accept', ' fixture ': 'reject'}})]


@pytest.mark.parametrize('field,bad', BAD)
def test_direct_writer_rejects_invalid_later_metadata_before_any_output(merchants, field, bad):
    root = merchants
    args = {'buyers': {SHOP: ['FIXTURE']}, 'vanilla': {SHOP: ['FIXTURE']},
            'overrides': {SHOP: {'FIXTURE': 'accept'}}}
    args[field] = copy.deepcopy(bad)
    before = snapshot(root)
    with pytest.raises(ValueError):
        s.write_shop_buyer_data(args['buyers'], args['vanilla'], args['overrides'])
    assert snapshot(root) == before


@pytest.mark.parametrize('content', ['<Install/>', '<invalid'])
def test_invalid_install_preparation_preserves_all_outputs(merchants, content):
    root = merchants
    (s.EDITABLE_MOD_ROOT / 'install.xml').write_text(content)
    before = snapshot(root)
    with pytest.raises(ValueError):
        write()
    assert snapshot(root) == before


def test_empty_resources_and_stale_mapping_are_repaired_without_duplicate(merchants):
    install = s.EDITABLE_MOD_ROOT / 'install.xml'
    install.write_text('<Install><Resources/></Install>')
    write()
    tree = ET.parse(install)
    mapping = tree.find('.//FileReplacement')
    mapping.find('FilePath').text = 'stale/buyers.ymt'
    tree.write(install)
    write()
    tree = ET.parse(install)
    assert len(tree.findall('.//FileReplacement')) == 1
    assert tree.findtext('.//FilePath') == s.BUYER_DATA_FILE.relative_to(s.EDITABLE_MOD_ROOT).as_posix()
    stable = install.read_bytes()
    write()
    assert install.read_bytes() == stable


def test_direct_writer_read_only_does_not_create_outputs(merchants, monkeypatch):
    before = snapshot(merchants)
    monkeypatch.setitem(s.DATASETS['mine'], 'readonly', True)
    with pytest.raises(PermissionError):
        write()
    assert snapshot(merchants) == before


def test_real_http_csv_failure_preserves_every_output_then_retry_saves(merchants, monkeypatch):
    s.BUYER_STATE_FILE.write_text(json.dumps({'buyers': {SHOP: []}, 'vanillaBuyers': {SHOP: []}, 'overrides': {}}))
    (s.EDITABLE_MOD_ROOT / 'install.xml').write_text('<Install><Resources/></Install>')
    before = snapshot(merchants)
    real_replace = Path.replace
    failed = False
    def replace(path, destination):
        nonlocal failed
        if Path(destination) == s.BUYER_OVERRIDE_FILE and not failed:
            failed = True
            raise OSError('Injected runtime override write failure')
        return real_replace(path, destination)
    monkeypatch.setattr(Path, 'replace', replace)
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    try:
        request = Request(f'http://127.0.0.1:{http.server_port}/api/shop-buyers/save',
                          data=json.dumps({'edits': [{'shop': SHOP, 'item': 'FIXTURE', 'mode': 'accept'}]}).encode(),
                          headers={'Content-Type': 'application/json'})
        with pytest.raises(HTTPError) as failure:
            urlopen(request, timeout=5)
        assert failure.value.code == 500
        assert 'Injected runtime override write failure' in json.load(failure.value)['error']
        assert snapshot(merchants) == before
        with urlopen(request, timeout=5) as response:
            assert json.load(response)['saved'] == 1
        assert s.get_shop_buyers()['overrides'][SHOP] == {'FIXTURE': 'accept'}
        assert not list(merchants.rglob('*.tmp'))
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
