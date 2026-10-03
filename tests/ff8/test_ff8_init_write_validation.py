"""Starting-data writes validate complete batches and preserve unrelated bytes."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import formats, init_data
from plugins.ff8.server import create_server


@pytest.fixture
def files(tmp_path, monkeypatch):
    source = tmp_path / 'vanilla'
    source.mkdir()
    output = tmp_path / 'mod'
    (source / 'init.out').write_bytes(bytes([0xA5]) * (init_data.FULL_SIZE + 19))
    def current(name, dataset='current'):
        candidate = output / name
        return candidate if dataset == 'current' and candidate.exists() else source / name
    monkeypatch.setattr(formats, 'source_path', current)
    monkeypatch.setattr(formats, 'output_path', lambda name: output / name)
    monkeypatch.setattr(formats, 'source_label', lambda name: 'Authored source')
    monkeypatch.setattr(formats, 'ITEM_NAMES', {0: 'None', 1: 'Authored item'})
    monkeypatch.setattr(formats, 'item_choices', lambda: [{'id': 1, 'name': 'Authored item'}])
    monkeypatch.setattr(formats, 'WEAPONS', [{'id': 1, 'name': 'Authored weapon'}])
    monkeypatch.setattr(formats, 'MAGIC', [{'id': 1, 'name': 'Authored spell'}])
    monkeypatch.setattr(formats, 'GFORCES', [{'id': i, 'name': f'GF {i}'} for i in range(16)])
    return tmp_path, source, output


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def edit(kind):
    return {
        'general': dict(kind='general', id=0, field='gil', value=123),
        'config': dict(kind='config', id=0, field='volume', value=77),
        'gf': dict(kind='gf', id=2, field='current_hp', value=4321),
        'character': dict(kind='character', id=1, field='current_hp', value=8765),
        'magic': dict(kind='magic', id=1, slot=31, magicId=1, quantity=80),
        'inventory': dict(kind='inventory', slot=197, itemId=1, quantity=12),
    }[kind]


@pytest.mark.parametrize('kind,field', [
    ('general', 'id'), ('general', 'value'), ('config', 'value'),
    ('gf', 'id'), ('gf', 'value'), ('character', 'id'), ('character', 'value'),
    ('magic', 'id'), ('magic', 'slot'), ('magic', 'magicId'), ('magic', 'quantity'),
    ('inventory', 'slot'), ('inventory', 'itemId'), ('inventory', 'quantity'),
])
@pytest.mark.parametrize('value', [False, .5, float('inf'), float('nan'), '1.5'])
def test_init_nonintegers_rejected_before_writes(files, kind, field, value):
    root, _, output = files
    before = snapshot(root)
    bad = edit(kind)
    bad[field] = value
    with pytest.raises(ValueError, match='integer'):
        formats.save_init([dict(kind='config', field='camera', value=1), bad])
    assert snapshot(root) == before
    assert not output.exists()


@pytest.mark.parametrize('kind,field', [('gf', 'available'), ('character', 'alternate_model'), ('character', 'exists')])
@pytest.mark.parametrize('value', [0, 1, 'false', None, .5])
def test_init_switches_require_booleans(files, kind, field, value):
    root, _, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError, match='boolean'):
        formats.save_init([edit('general'), dict(kind=kind, id=0, field=field, value=value)])
    assert snapshot(root) == before


@pytest.mark.parametrize('bad', [
    dict(kind='general', field='gil', value=2**32),
    dict(kind='config', field='volume', value=-1),
    dict(kind='gf', id=16, field='current_hp', value=1),
    dict(kind='character', id=8, field='current_hp', value=1),
    dict(kind='gf', id=2, field='current_hp', value=65536),
    dict(kind='character', id=1, field='gf_compatibility_1', value=999),
    dict(kind='character', id=1, field='gf_compatibility_1', value=6001),
    dict(kind='character', id=1, field='weapon_id', value=2),
    dict(kind='inventory', slot=198, itemId=1, quantity=1),
    dict(kind='inventory', slot=0, itemId=2, quantity=1),
    dict(kind='inventory', slot=0, itemId=1, quantity=101),
    dict(kind='magic', id=1, slot=32, magicId=1, quantity=1),
    dict(kind='magic', id=1, slot=0, magicId=2, quantity=1),
    dict(kind='magic', id=1, slot=0, magicId=1, quantity=-1),
    dict(kind='general', field='unknown', value=1),
    edit('general'),
])
def test_init_rejected_batch_preserves_existing_output(files, bad):
    root, _, _ = files
    formats.save_init([dict(kind='config', field='camera', value=1)])
    before = snapshot(root)
    with pytest.raises(ValueError):
        formats.save_init([edit('general'), bad])
    assert snapshot(root) == before


def valid_edits():
    return [edit(kind) for kind in ('general', 'config', 'gf', 'character', 'magic', 'inventory')] + [
        dict(kind='gf', id=2, field='available', value=True),
        dict(kind='character', id=1, field='alternate_model', value=False),
        dict(kind='character', id=1, field='exists', value=True),
    ]


def assert_reload(source, output):
    original = (source / 'init.out').read_bytes()
    expected = bytearray(original)
    base = init_data.CHARACTER_OFFSET + init_data.CHARACTER_SIZE
    for offset, width, value in [
        (init_data.MISC_OFFSET + 24, 4, 123), (init_data.CONFIG_OFFSET + 3, 1, 77),
        (2 * init_data.GF_SIZE + 18, 2, 4321), (base, 2, 8765),
        (base + 16 + 31 * 2, 2, 0x5001), (init_data.ITEMS_OFFSET + 197 * 2, 2, 0x0C01),
        (2 * init_data.GF_SIZE + 17, 1, 1), (base + 91, 1, 0), (base + 148, 1, 1),
    ]:
        expected[offset:offset + width] = value.to_bytes(width, 'little')
    assert (output / 'init.out').read_bytes() == bytes(expected)
    assert (source / 'init.out').read_bytes() == original
    rows = formats.init_rows()
    def field(owner, name):
        return next(f['value'] for f in owner['fields'] if f['field'] == name)
    assert field(rows['general'], 'gil') == 123
    assert field(rows['config'], 'volume') == 77
    assert field(rows['gfs']['rows'][2], 'current_hp') == 4321
    assert field(rows['gfs']['rows'][2], 'available') is True
    character = rows['characters']['rows'][1]
    assert field(character, 'current_hp') == 8765
    assert field(character, 'alternate_model') is False
    assert field(character, 'exists') is True
    assert character['magics'][31] == dict(slot=31, magicId=1, quantity=80)
    assert rows['inventory']['rows'][197] == dict(slot=197, itemId=1, quantity=12)


def test_init_valid_save_reloads_all_families_and_preserves_unknown_bytes(files):
    _, source, output = files
    assert formats.save_init(valid_edits())['saved'] == 9
    assert_reload(source, output)


def test_init_http_rejects_later_invalid_edit_and_reloads_valid_batch(files):
    root, source, output = files
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/init/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request([edit('general'), dict(kind='inventory', slot=197.5, itemId=1, quantity=1)]), timeout=5)
        assert failure.value.code == 400
        failure.value.close()
        assert snapshot(root) == before
        with urlopen(request(valid_edits()), timeout=5) as response:
            assert json.load(response)['saved'] == 9
        assert_reload(source, output)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
