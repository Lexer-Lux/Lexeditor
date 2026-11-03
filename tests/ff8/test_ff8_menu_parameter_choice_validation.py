"""Menu parameter saves share the choices exposed by the reader."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import formats, menu_items
from plugins.ff8.server import create_server


ORIGINAL = bytes([16, 0xA5, 254, 9, 17, 0x5A, 254, 4, 19, 0xAA, 254, 0xCC])
TYPES = (16, 17, 19)
KINDS = ('gf_target', 'gf_ability', 'quistis_limit')


def edit(index, value):
    start = index * 4
    return dict(id=index, typeId=TYPES[index], flags=ORIGINAL[start + 1], param1=value, param2=ORIGINAL[start + 3])


@pytest.fixture
def files(tmp_path, monkeypatch):
    source = tmp_path / 'vanilla.bin'
    destination = tmp_path / 'mod' / 'mitem.bin'
    source.write_bytes(ORIGINAL)
    monkeypatch.setattr(formats, 'source_path', lambda *args: destination if destination.exists() else source)
    monkeypatch.setattr(formats, 'output_path', lambda *args: destination)
    monkeypatch.setattr(formats, 'source_label', lambda *args: 'Authored')
    return source, destination


@pytest.mark.parametrize('index', range(3))
def test_menu_unknown_choice_rejects_without_new_or_changed_outputs(files, index):
    source, destination = files
    choices = formats._menu_parameter_choices()
    valid = int(choices[KINDS[index]][0]['id'])
    invalid = next(i for i in range(256) if i != 254 and i not in {int(c['id']) for c in choices[KINDS[index]]})
    with pytest.raises(ValueError, match='documented'):
        formats.save_menu_items([edit((index + 1) % 2, 254) | dict(flags=0), edit(index, invalid)])
    assert not destination.exists()
    formats.save_menu_items([edit(index, valid)])
    before = destination.read_bytes()
    with pytest.raises(ValueError, match='documented'):
        formats.save_menu_items([edit((index + 1) % 2, 254) | dict(flags=0), edit(index, invalid)])
    assert destination.read_bytes() == before
    assert source.read_bytes() == ORIGINAL


@pytest.mark.parametrize('index', range(3))
def test_menu_all_published_choices_save_and_reload(files, index):
    source, destination = files
    choices = formats._menu_parameter_choices()
    assert formats.menu_item_rows()['parameterChoices'] == choices
    for choice in choices[KINDS[index]]:
        value = int(choice['id'])
        formats.save_menu_items([edit(index, value)])
        expected = bytearray(ORIGINAL)
        expected[index * 4 + 2] = value
        assert destination.read_bytes() == expected
        rows = menu_items.read_rows(destination.read_bytes(), {}, formats.SCHEMA_ROOT)['rows']
        assert rows[index]['param1'] == value
    assert source.read_bytes() == ORIGINAL


@pytest.mark.parametrize('index', range(3))
def test_menu_untouched_unknown_parameter_is_preserved_when_other_fields_change(files, index):
    source, destination = files
    # Quistis flags are overridden; its unknown parameter can only be retained.
    flags = ORIGINAL[index * 4 + 1] if index == 2 else 0
    formats.save_menu_items([edit(index, 254) | dict(flags=flags)])
    expected = bytearray(ORIGINAL)
    expected[index * 4 + 1] = flags
    assert destination.read_bytes() == expected
    assert source.read_bytes() == ORIGINAL


def test_menu_type_change_cannot_reuse_unknown_parameter(files):
    with pytest.raises(ValueError, match='documented'):
        formats.save_menu_items([edit(0, 254) | dict(typeId=17)])
    assert not files[1].exists()


def test_menu_parameter_http_rejection_and_valid_reload(files):
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/menu-items/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        with pytest.raises(HTTPError) as failure:
            urlopen(request([edit(0, 255), edit(2, 253)]), timeout=5)
        assert failure.value.code == 400
        failure.value.close()
        assert not files[1].exists()
        with urlopen(request([edit(0, 255)]), timeout=5) as response:
            assert json.load(response)['saved'] == 1
        assert files[1].read_bytes() == bytes([16, 0xA5, 255, 9]) + ORIGINAL[4:]
        assert files[0].read_bytes() == ORIGINAL
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
