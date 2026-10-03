"""Menu item scalar validation precedes every output write."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import formats, menu_items
from plugins.ff8.server import create_server


ORIGINAL = bytes([0, 0xA5, 7, 9, 0, 0x5A, 3, 4, 254, 0xAA, 0xBB, 0xCC])


def edit(**changes):
    return dict(id=0, typeId=0, flags=0xA5, param1=11, param2=9) | changes


@pytest.fixture
def files(tmp_path, monkeypatch):
    source = tmp_path / 'vanilla.bin'
    destination = tmp_path / 'mod' / 'mitem.bin'
    source.write_bytes(ORIGINAL)
    schema = tmp_path / 'schema'
    schema.mkdir()
    (schema / 'limit_break.json').write_text(json.dumps(dict(quistis_blue_magic=[])), encoding='utf-8')
    (schema / 'mitem.json').write_text(json.dumps(dict(item_type=[dict(id=0, name='Authored')],
                                                    flag=[], param_type=[])), encoding='utf-8')
    monkeypatch.setattr(formats, 'SCHEMA_ROOT', schema)
    monkeypatch.setattr(formats, 'source_path', lambda *args: destination if destination.exists() else source)
    monkeypatch.setattr(formats, 'output_path', lambda *args: destination)
    return source, destination, schema


@pytest.mark.parametrize('field', ['id', 'typeId', 'flags', 'param1', 'param2'])
@pytest.mark.parametrize('value', [False, True, .5, float('inf'), float('-inf'), float('nan'), '1.5', None])
def test_menu_item_invalid_scalar_rejects_batch_and_preserves_existing_output(files, field, value):
    source, destination, schema = files
    batch = [edit(), edit(id=1) | {field: value}]
    with pytest.raises(ValueError, match='integer'):
        menu_items.apply_edits(ORIGINAL, batch, schema)
    with pytest.raises(ValueError, match='integer'):
        formats.save_menu_items(batch)
    assert not destination.exists()
    formats.save_menu_items([edit()])
    before = destination.read_bytes()
    with pytest.raises(ValueError, match='integer'):
        formats.save_menu_items([edit(param1=22), edit(id=1) | {field: value}])
    assert destination.read_bytes() == before
    assert source.read_bytes() == ORIGINAL


@pytest.mark.parametrize('bad', [dict(id=-1), dict(id=3), dict(id=0), dict(typeId=1),
                              dict(flags=256), dict(param1=-1), dict(param2=256)])
def test_menu_item_bounds_choices_and_duplicate_reject_before_write(files, bad):
    source, destination, _ = files
    with pytest.raises(ValueError):
        formats.save_menu_items([edit(), edit(id=1) | bad])
    assert not destination.exists()
    assert source.read_bytes() == ORIGINAL


def assert_reload(files):
    source, destination, schema = files
    assert destination.read_bytes() == bytes([0, 255, 0, 255]) + ORIGINAL[4:]
    row = menu_items.read_rows(destination.read_bytes(), {}, schema)['rows'][0]
    assert (row['typeId'], row['flags'], row['param1'], row['param2']) == (0, 255, 0, 255)
    assert source.read_bytes() == ORIGINAL


def test_menu_item_valid_bounds_preserve_unedited_unknown_record(files):
    assert formats.save_menu_items([edit(flags=255, param1=0, param2=255)])['saved'] == 1
    assert_reload(files)


def test_menu_item_http_rejects_invalid_later_scalar_then_reloads(files):
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/menu-items/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        for field in ('id', 'typeId', 'flags', 'param1', 'param2'):
            with pytest.raises(HTTPError) as failure:
                urlopen(request([edit(), edit(id=1) | {field: .5}]), timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert not files[1].exists()
            assert files[0].read_bytes() == ORIGINAL
        with urlopen(request([edit(flags=255, param1=0, param2=255)]), timeout=5) as response:
            assert json.load(response)['saved'] == 1
        assert_reload(files)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
