"""Malformed recipe batches and read-only requests never replace custom recipes."""
import copy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from plugins.rdr2 import server

RECIPE = {'recipe_id': 'fixture', 'category': '', 'title': 'Fixture',
          'description': '', 'station': 'CUSTOM_ANY', 'output_item': 'OUTPUT',
          'output_quantity': 2, 'ingredients': [{'item': 'INPUT', 'quantity': 3}], 'unlock': ''}


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(server, 'CUSTOM_CRAFTING_FILE', tmp_path / 'custom.tsv')
    monkeypatch.setattr(server, 'DATASETS', {'mine': {'dir': tmp_path / 'mine', 'readonly': False}})
    monkeypatch.setattr(server, '_files', {})
    monkeypatch.delenv('LEXEDITOR_MOD_READ_ONLY', raising=False)
    return tmp_path


BAD_ROWS = []
for field in ['recipe_id', 'category', 'title', 'description', 'station', 'output_item', 'unlock']:
    for value in [None, True, 128, [], {}]:
        row = copy.deepcopy(RECIPE)
        row[field] = value
        BAD_ROWS.append(row)
for value in [None, True, 128, [], {}]:
    row = copy.deepcopy(RECIPE)
    row['ingredients'][0]['item'] = value
    BAD_ROWS.append(row)
BAD_ROWS.extend([dict(RECIPE, unknown=1), dict(RECIPE, ingredients=[{'item': 'INPUT', 'quantity': 3, 'unknown': 1}])])


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('bad', BAD_ROWS)
def test_invalid_later_recipe_preserves_saved_file(fixture, existing, bad):
    if existing:
        server.save_custom_crafting([RECIPE])
    before = {p.name: p.read_bytes() for p in fixture.iterdir() if p.is_file()}
    first = dict(RECIPE, recipe_id='valid_first', title='Changed')
    with pytest.raises(ValueError):
        server.save_custom_crafting([first, bad])
    assert {p.name: p.read_bytes() for p in fixture.iterdir() if p.is_file()} == before


def test_both_http_routes_reject_bad_text_and_put_respects_read_only(fixture, monkeypatch):
    server.save_custom_crafting([RECIPE])
    before = server.CUSTOM_CRAFTING_FILE.read_bytes()
    http = server.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{http.server_port}'
    def request(path, method, rows):
        return Request(base + path, data=json.dumps({'recipes': rows}).encode(), method=method,
                       headers={'Content-Type': 'application/json'})
    try:
        for method, path in [('PUT', '/api/custom-crafting'), ('POST', '/api/custom-crafting/save')]:
            with pytest.raises(HTTPError) as failure:
                urlopen(request(path, method, [dict(RECIPE, title=None)]), timeout=5)
            assert failure.value.code == 400
            assert 'text' in json.load(failure.value)['error']
            assert server.CUSTOM_CRAFTING_FILE.read_bytes() == before
        monkeypatch.setenv('LEXEDITOR_MOD_READ_ONLY', '1')
        monkeypatch.setenv('LEXEDITOR_NO_MOD', '1')
        with pytest.raises(HTTPError) as failure:
            urlopen(request('/api/custom-crafting', 'PUT', []), timeout=5)
        assert failure.value.code == 403
        assert 'Create a mod' in json.load(failure.value)['error']
        assert server.CUSTOM_CRAFTING_FILE.read_bytes() == before
        monkeypatch.delenv('LEXEDITOR_MOD_READ_ONLY')
        corrected = dict(RECIPE, title='Corrected', description='Retained description')
        with urlopen(request('/api/custom-crafting', 'PUT', [corrected]), timeout=5) as response:
            assert json.load(response) == {'saved': 1}
        loaded = server._load_craft_recipes(server.CUSTOM_CRAFTING_FILE)
        assert server._craft_recipe_json(loaded[0]) == corrected
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
