"""Invalid quick-select edits must not follow an already committed catalog save."""
import json
import threading
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_rdr2_catalog_numeric_validation import fixture, snapshot
from plugins.rdr2 import server as s


@pytest.fixture
def quick(fixture):
    root, _ = fixture
    path = s.data_file_path(s.QUICK_SELECT_FILE, 'mine')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'''<Root><!--preserve--><ItemGroups><Item key="{s.QUICK_SELECT_SATCHEL_GROUP}"><Items>
      <Item key="FIXTURE"><Opaque value="17"/><Slots><Item><Id>SLOT_A</Id><SortOrder value="10"/></Item></Slots></Item>
      <Item key="UNTOUCHED"><Slots><Item><Id>SLOT_B</Id><SortOrder value="20"/></Item></Slots></Item>
    </Items></Item></ItemGroups></Root>''')
    s.load_file(s.QUICK_SELECT_FILE)
    return root, path


BAD_SLOTS = [None, {}, [None], [{}], [{'id': None}], [{'id': True}], [{'id': 'MISSING'}],
             [{'id': 'SLOT_A', 'extra': 1}], [{'id': 'SLOT_A'}, {'id': 'SLOT_A'}]]
BAD_SLOTS += [[{'id': 'SLOT_A', 'sortOrder': value}] for value in
              [None, True, 1.5, '1.5', float('nan'), float('inf'), -1, 1000001]]


@pytest.mark.parametrize('slots', BAD_SLOTS)
@pytest.mark.parametrize('existing_backup', [False, True])
def test_later_bad_slots_preserve_catalog_radial_cache_and_outputs(quick, slots, existing_backup):
    root, _ = quick
    if existing_backup:
        for name in [s.CATALOG_FILE, s.QUICK_SELECT_FILE]:
            path = s.data_file_path(name, 'mine')
            path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    before = snapshot(root)
    cached = {name: ET.tostring(s.load_file(name)['root']) for name in [s.CATALOG_FILE, s.QUICK_SELECT_FILE]}
    with pytest.raises(ValueError):
        s.apply_catalog_edits({'carry': [{'item': 'FIXTURE', 'slot': 'SLOTID_ANY', 'qty': 9}],
                              'quickSelect': [{'item': 'FIXTURE', 'slots': slots}]})
    assert snapshot(root) == before
    assert {name: ET.tostring(s.load_file(name)['root']) for name in cached} == cached


def test_actual_http_rejects_mixed_batch_and_known_slots_save_reload(quick):
    root, path = quick
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def request(batch):
        return Request(f'http://127.0.0.1:{http.server_port}/api/catalog/save',
                       data=json.dumps(batch).encode(), headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        carry = [{'item': 'FIXTURE', 'slot': 'SLOTID_ANY', 'qty': 9}]
        with pytest.raises(HTTPError) as failure:
            urlopen(request({'carry': carry, 'quickSelect': [{'item': 'FIXTURE', 'slots': [{'id': 'MISSING'}]}]}), timeout=5)
        assert failure.value.code == 400
        assert snapshot(root) == before
        with urlopen(request({'carry': carry, 'quickSelect': [{'item': 'FIXTURE', 'slots': [{'id': 'SLOT_B', 'sortOrder': 1000000}]}]}), timeout=5) as response:
            assert json.load(response)['saved'] == 2
        s._files.clear()
        assert s.get_quick_select()['items']['FIXTURE']['slots'] == [{'id': 'SLOT_B', 'sortOrder': 1000000}]
        doc = s.load_file(s.QUICK_SELECT_FILE)['root']
        assert doc.find('.//Item[@key="FIXTURE"]/Opaque').get('value') == '17'
        assert s.get_quick_select()['items']['UNTOUCHED']['slots'] == [{'id': 'SLOT_B', 'sortOrder': 20}]
        assert '<!--preserve-->' in path.read_text()
        assert s.load_file(s.CATALOG_FILE)['root'].find('.//multiplicity/item/quantity').get('value') == '9'
        # Automatic placement also respects the declared maximum.
        before = snapshot(root)
        with pytest.raises(ValueError):
            s.apply_quick_select_edits([{'item': 'FIXTURE', 'slots': [{'id': 'SLOT_B'}]}])
        assert snapshot(root) == before
        assert s.apply_quick_select_edits([{'item': 'FIXTURE', 'slots': []}]) == 1
        s._files.clear()
        assert 'FIXTURE' not in s.get_quick_select()['items']
        assert s.get_quick_select()['items']['UNTOUCHED']['slots'] == [{'id': 'SLOT_B', 'sortOrder': 20}]
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


@pytest.mark.parametrize('edits', [None, {}, [None], [{'item': None, 'slots': []}],
                                  [{'item': 'FIXTURE', 'slots': [], 'extra': 1}],
                                  [{'item': 'MISSING', 'slots': []}]])
def test_direct_writer_rejects_malformed_batches_without_outputs(quick, edits):
    root, _ = quick
    before = snapshot(root)
    with pytest.raises(ValueError):
        s.apply_quick_select_edits(edits)
    assert snapshot(root) == before


def test_valid_auto_order_is_prepared_without_writes_and_commits_through_direct_writer(quick):
    root, _ = quick
    edits = [{'item': 'FIXTURE', 'slots': [{'id': 'SLOT_B'}]}]
    before = snapshot(root)
    cached = ET.tostring(s.load_file(s.QUICK_SELECT_FILE)['root'])
    s._prepare_quick_select_edits(edits)
    assert snapshot(root) == before
    assert ET.tostring(s.load_file(s.QUICK_SELECT_FILE)['root']) == cached
    assert s.apply_quick_select_edits(edits) == 1
    s._files.clear()
    assert s.get_quick_select()['items']['FIXTURE']['slots'] == [{'id': 'SLOT_B', 'sortOrder': 30}]
