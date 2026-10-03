"""Merchant overrides validate all targets before loading or writing buyer data."""
import copy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_rdr2_catalog_numeric_validation import fixture, snapshot
from plugins.rdr2 import server as s

SHOP = s.BUYER_SHOPS[0]
BASE = {'shop': SHOP, 'item': 'FIXTURE', 'mode': 'accept'}
BAD = [None, {}, '', False, (), [None], [{}], [{'shop': SHOP}], [{**BASE, 'opaque': 1}]]
for field in ['shop', 'item', 'mode']:
    for bad in [None, True, 3, [], {}, '', 'UNKNOWN']:
        BAD.append([{**BASE, field: bad}])
BAD.append([BASE, {**BASE, 'item': ' fixture '}])


@pytest.fixture
def merchants(fixture, monkeypatch):
    root, _ = fixture
    mine = s.ds_dir('mine')
    monkeypatch.setattr(s, 'EDITABLE_MOD_ROOT', mine)
    for variable, filename in [('BUYER_STATE_FILE', 'merchant_buyers.json'),
                               ('BUYER_DATA_FILE', 'parseddata/buyers.ymt'),
                               ('BUYER_OVERRIDE_FILE', 'runtime/merchant_buy_overrides.csv'),
                               ('BUYER_DUMP_FILE', 'vanilla_shop_buyers.csv')]:
        monkeypatch.setattr(s, variable, mine / filename)
    return root


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('existing', [False, True])
def test_invalid_later_edits_do_not_import_baseline_or_change_outputs(merchants, bad, existing):
    root = merchants
    # Importing this authored dump would write state; rejected edits must fail
    # even before that reader-side import.
    s.BUYER_DUMP_FILE.write_text(f'shop,item\n{SHOP},FIXTURE\n')
    if existing:
        for path in [s.BUYER_STATE_FILE, s.BUYER_DATA_FILE, s.BUYER_OVERRIDE_FILE]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'original output')
    before = snapshot(root)
    edits = [BASE, *bad] if isinstance(bad, list) else bad
    with pytest.raises(ValueError):
        s.apply_shop_buyer_edits(copy.deepcopy(edits))
    assert snapshot(root) == before


def test_empty_batch_and_read_only_do_not_import_baseline(merchants, monkeypatch):
    root = merchants
    s.BUYER_DUMP_FILE.write_text(f'shop,item\n{SHOP},FIXTURE\n')
    before = snapshot(root)
    assert s.apply_shop_buyer_edits([]) == 0
    monkeypatch.setitem(s.DATASETS['mine'], 'readonly', True)
    with pytest.raises(PermissionError):
        s.apply_shop_buyer_edits([BASE])
    assert snapshot(root) == before


def test_http_rejects_then_accept_reject_default_reload_preserves_unresolved_baseline(merchants):
    root = merchants
    mine = s.ds_dir('mine')
    (mine / 'install.xml').write_text('<Install><Resources><Resource><Opaque>keep</Opaque></Resource></Resources></Install>')
    baseline = {shop: [] for shop in s.BUYER_SHOPS}
    baseline[SHOP] = ['FIXTURE', '0xDEADBEEF']
    s.BUYER_STATE_FILE.write_text(json.dumps({'buyers': baseline, 'vanillaBuyers': baseline, 'overrides': {}}))
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def request(edits):
        return Request(f'http://127.0.0.1:{http.server_port}/api/shop-buyers/save',
                       data=json.dumps({'edits': edits}).encode(), headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request([BASE, {**BASE, 'item': 'UNKNOWN'}]), timeout=5)
        assert failure.value.code == 400
        assert snapshot(root) == before
        for mode in ['reject', 'accept', 'default']:
            with urlopen(request([{**BASE, 'item': ' fixture ', 'mode': mode}]), timeout=5) as response:
                assert json.load(response)['saved'] == 1
            loaded = s.get_shop_buyers()
            assert ('FIXTURE' in loaded['buyers'][SHOP]) == (mode != 'reject')
            assert loaded['overrides'][SHOP].get('FIXTURE', 'default') == mode
            assert loaded['vanillaBuyers'][SHOP] == ['0XDEADBEEF', 'FIXTURE']
            assert '0XDEADBEEF' in loaded['buyers'][SHOP]
        stable = snapshot(root)
        assert s.apply_shop_buyer_edits([{'shop': SHOP, 'item': 'FIXTURE'}]) == 0
        assert snapshot(root) == stable
        assert s.BUYER_OVERRIDE_FILE.read_text() == 'shop,item,mode\n'
        assert 'keep' in (mine / 'install.xml').read_text()
        assert '0XDEADBEEF' in s.BUYER_DATA_FILE.read_text()
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


def test_failed_write_does_not_mutate_supplied_reader_snapshot(merchants, monkeypatch):
    current = {'available': True, 'buyers': {shop: [] for shop in s.BUYER_SHOPS},
               'vanillaBuyers': {shop: [] for shop in s.BUYER_SHOPS},
               'overrides': {shop: {} for shop in s.BUYER_SHOPS}}
    before = copy.deepcopy(current)
    monkeypatch.setattr(s, 'get_shop_buyers', lambda: current)
    def fail(*args):
        raise OSError('Injected writer failure')
    monkeypatch.setattr(s, 'write_shop_buyer_data', fail)
    with pytest.raises(OSError):
        s.apply_shop_buyer_edits([BASE])
    assert current == before
