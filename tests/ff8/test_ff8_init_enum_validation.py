"""Starting Data writes accept the same finite choices exposed by its reader."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import formats, init_data
from plugins.ff8.server import create_server
from test_ff8_init_write_validation import files, snapshot


JUNCTIONS = ['hp', 'str', 'vit', 'mag', 'spr', 'spd', 'eva', 'hit', 'luck', 'element_attack',
             'status_attack', 'element_defense_1', 'element_defense_2', 'element_defense_3',
             'element_defense_4', 'status_defense_1', 'status_defense_2', 'status_defense_3',
             'status_defense_4']


@pytest.fixture
def lookup_files(files, monkeypatch):
    monkeypatch.setattr(formats, 'INIT_ABILITIES', [dict(id=1, name='Authored ability')])
    return files


CHOICES = ([('general', f'party_{slot}', 11) for slot in range(1, 4)] +
           [('general', f'weapon_{name}', 2) for name in ('laguna', 'kiros', 'ward')] +
           [('character', 'weapon_id', 2)] +
           [('character', f'{family}_ability_{slot}', 2) for family in ('active', 'passive') for slot in range(1, 5)] +
           [('character', f'junction_{name}', 2) for name in JUNCTIONS])


@pytest.mark.parametrize('kind,field,value', CHOICES)
def test_init_unknown_enum_after_valid_edit_has_no_outputs(lookup_files, kind, field, value):
    root, _, output = lookup_files
    before = snapshot(root)
    with pytest.raises(ValueError, match='Invalid'):
        formats.save_init([dict(kind='general', field='gil', value=123),
                           dict(kind=kind, id=0 if kind == 'general' else 1, field=field, value=value)])
    assert snapshot(root) == before
    assert not output.exists()


@pytest.mark.parametrize('kind,field,value', CHOICES)
def test_init_unknown_enum_preserves_existing_output(lookup_files, kind, field, value):
    root, _, _ = lookup_files
    formats.save_init([dict(kind='general', field='gil', value=123)])
    before = snapshot(root)
    with pytest.raises(ValueError, match='Invalid'):
        formats.save_init([dict(kind='config', field='volume', value=77),
                           dict(kind=kind, id=0 if kind == 'general' else 1, field=field, value=value)])
    assert snapshot(root) == before


def choices():
    edits = [dict(kind='general', field=f'party_{slot}', value=value)
             for slot, value in enumerate((255, 10, 0), 1)]
    edits += [dict(kind='general', field=f'weapon_{name}', value=1) for name in ('laguna', 'kiros', 'ward')]
    edits += [dict(kind='character', id=1, field='weapon_id', value=1)]
    edits += [dict(kind='character', id=1, field=f'{family}_ability_{slot}', value=0 if slot == 1 else 1)
              for family in ('active', 'passive') for slot in range(1, 5)]
    edits += [dict(kind='character', id=1, field=f'junction_{name}', value=index % 2)
              for index, name in enumerate(JUNCTIONS)]
    return edits


def assert_reload(source, output):
    original = bytes([0xA5]) * (init_data.FULL_SIZE + 19)
    expected = bytearray(original)
    expected[init_data.MISC_OFFSET:init_data.MISC_OFFSET + 3] = bytes((255, 10, 0))
    expected[init_data.MISC_OFFSET + 20:init_data.MISC_OFFSET + 23] = bytes((1, 1, 1))
    base = init_data.CHARACTER_OFFSET + init_data.CHARACTER_SIZE
    expected[base + 9] = 1
    expected[base + 80:base + 88] = bytes((0, 1, 1, 1, 0, 1, 1, 1))
    expected[base + 92:base + 111] = bytes(index % 2 for index in range(19))
    assert (output / 'init.out').read_bytes() == bytes(expected)
    assert (source / 'init.out').read_bytes() == original
    rows = formats.init_rows()
    for change in choices():
        owner = rows['general'] if change['kind'] == 'general' else rows['characters']['rows'][1]
        definition = next(field for field in owner['fields'] if field['field'] == change['field'])
        assert definition['value'] == change['value']
        assert change['value'] in {entry['id'] for entry in definition['lookup']['entries']}
    party = next(field for field in rows['general']['fields'] if field['field'] == 'party_1')
    assert {entry['id'] for entry in party['lookup']['entries']} == set(range(11)) | {255}
    # An unedited unresolved model byte remains intact, rather than being
    # rewritten merely because other fields are constrained by lookups.
    assert next(field['value'] for field in rows['characters']['rows'][1]['fields'] if field['field'] == 'model_id') == 0xA5


def test_init_valid_enum_choices_reload_and_preserve_unknown_bytes(lookup_files):
    _, source, output = lookup_files
    assert formats.save_init(choices())['saved'] == 34
    assert_reload(source, output)


def test_init_enum_http_rejects_invalid_choice_then_saves_known_choices(lookup_files):
    root, source, output = lookup_files
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/init/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request([dict(kind='general', field='gil', value=123),
                             dict(kind='character', id=1, field='junction_hp', value=2)]), timeout=5)
        assert failure.value.code == 400
        failure.value.close()
        assert snapshot(root) == before
        with urlopen(request(choices()), timeout=5) as response:
            assert json.load(response)['saved'] == 34
        assert_reload(source, output)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
