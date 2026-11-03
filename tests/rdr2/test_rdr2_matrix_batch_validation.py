"""Skinning batches validate before cached rows, outputs or backups change."""
import copy
import json
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_rdr2_catalog_numeric_validation import fixture, snapshot
from plugins.rdr2 import server as s

ROW = {'damage': 'Good', 'skin': 'Perfect', 'item': 'FIXTURE', 'qty': '2'}
BAD = [None, {}, False, '', [None], [{}], [{'animalKey': 'FIRST'}],
       [{'animalKey': 'MISSING', 'rows': []}], [{'animalKey': None, 'rows': []}],
       [{'animalKey': 'SECOND', 'rows': {}}], [{'animalKey': 'SECOND', 'rows': [None]}],
       [{'animalKey': 'SECOND', 'rows': [{**ROW, 'opaque': 1}]}],
       [{'animalKey': 'FIRST', 'rows': []}]]
for field in ['damage', 'skin', 'item']:
    for value in [None, True, 3, [], {}, '', 'UNKNOWN']:
        BAD.append([{'animalKey': 'SECOND', 'rows': [{**ROW, field: value}]}])
for value in [None, True, [], {}, '', 0, -1, '1.5', 1.5, float('nan'), float('inf')]:
    BAD.append([{'animalKey': 'SECOND', 'rows': [{**ROW, 'qty': value}]}])


@pytest.fixture
def matrix(fixture):
    root, _ = fixture
    path = s.data_file_path(s.MATRIX_FILE, 'mine')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('''<Root><!--keep--><Entries><Item key="FIRST"><Opaque value="17"/><Items><!--rows-->
      <Item><DamageQuality>Poor</DamageQuality><SkinQuality>Good</SkinQuality><SatchelItem>FIXTURE</SatchelItem><Quantity value="1"/></Item>
      </Items></Item><Item key="SECOND"><Items><Item><DamageQuality>Good</DamageQuality><SkinQuality>Perfect</SkinQuality>
      <SatchelItem>FIXTURE</SatchelItem></Item></Items></Item></Entries></Root>''')
    s.load_file(s.MATRIX_FILE)
    return root, path


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('existing_backup', [False, True])
def test_invalid_later_animal_preserves_all_outputs_and_cached_root(matrix, bad, existing_backup):
    root, path = matrix
    if existing_backup:
        path.with_suffix(path.suffix + '.bak').write_bytes(b'original backup')
    before = snapshot(root)
    old_root = s.load_file(s.MATRIX_FILE)['root']
    edits = [{'animalKey': 'FIRST', 'rows': [ROW]}, *copy.deepcopy(bad)] if isinstance(bad, list) else bad
    with pytest.raises(ValueError):
        s.apply_matrix_edits(edits)
    assert snapshot(root) == before
    assert s.load_file(s.MATRIX_FILE)['root'] is old_root


@pytest.mark.parametrize('fragment', ['<Opaque value="17"/>', '<Quantity value="1"/>',
                                   '<SatchelItem extra="unknown">FIXTURE</SatchelItem>', '<SkinQuality><Unknown/></SkinQuality>'])
def test_unmodeled_source_rows_are_visible_readonly_and_cannot_be_rebuilt(matrix, fragment):
    root, _ = matrix
    doc = s.load_file(s.MATRIX_FILE)['root']
    doc.find('.//Items/Item').append(ET.fromstring(fragment))
    s.save_file(s.MATRIX_FILE)
    before = snapshot(root)
    assert s.get_matrix()['animals'][0]['readonly']
    with pytest.raises(ValueError, match='read-only'):
        s.apply_matrix_edits([{'animalKey': 'FIRST', 'rows': [ROW]}])
    assert snapshot(root) == before


def test_actual_http_rejects_then_reload_preserves_exact_quantity_and_quality_choices(matrix):
    root, path = matrix
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def request(edits):
        return Request(f'http://127.0.0.1:{http.server_port}/api/matrix/save',
                       data=json.dumps({'edits': edits}).encode(), headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request([{'animalKey': 'FIRST', 'rows': [{**ROW, 'qty': 1.5}]}]), timeout=5)
        assert failure.value.code == 400
        assert snapshot(root) == before
        with urlopen(request([{'animalKey': 'FIRST', 'rows': [{**ROW, 'qty': '9007199254740993', 'skin': 'Legendary'}]}]), timeout=5) as response:
            assert json.load(response)['saved'] == 1
        s._files.clear()
        result = s.get_matrix()['animals']
        assert result[0]['rows'] == [{**ROW, 'qty': '9007199254740993', 'skin': 'Legendary'}]
        assert not result[0]['readonly']
        assert result[1]['rows'][0]['qty'] == '1'
        assert '<!--keep-->' in path.read_text()
        assert '<!--rows-->' in path.read_text()
        assert s.load_file(s.MATRIX_FILE)['root'].find('.//Entries/Item/Opaque').get('value') == '17'
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


def test_replacement_failure_restores_cache_file_and_new_backup(matrix, monkeypatch):
    root, path = matrix
    before = snapshot(root)
    cached = s.load_file(s.MATRIX_FILE)['root']
    real_replace = Path.replace
    def replace(source, destination):
        if Path(destination) == path:
            raise OSError('Injected matrix replacement failure')
        return real_replace(source, destination)
    monkeypatch.setattr(Path, 'replace', replace)
    with pytest.raises(OSError):
        s.apply_matrix_edits([{'animalKey': 'FIRST', 'rows': [ROW]}])
    assert snapshot(root) == before
    assert s.load_file(s.MATRIX_FILE)['root'] is cached


def test_empty_batch_and_readonly_writer_do_not_change_any_file(matrix, monkeypatch):
    root, _ = matrix
    before = snapshot(root)
    assert s.apply_matrix_edits([]) == 0
    monkeypatch.setitem(s.DATASETS['mine'], 'readonly', True)
    with pytest.raises(PermissionError):
        s.apply_matrix_edits([{'animalKey': 'FIRST', 'rows': [ROW]}])
    assert snapshot(root) == before
