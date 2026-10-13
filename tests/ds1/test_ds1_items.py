import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument, FormatError, SUBTABS, TABLES, inflate
from plugins.ds1.store import ItemStore, RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session


def project(tmp_path):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def test_all_categories_noop_and_changed_roundtrip():
    raw = make_archive()
    document = ItemDocument(raw)
    assert document.export() == raw
    allowed = set()
    changed = []
    for tab, _, _ in SUBTABS:
        row = document.list_rows(tab)[0]
        fields = document.read_row(row['table'], row['id'])['fields']
        field = next(f for f in fields if f['editable'] and f['type'] == 'number' and f['minimum'] <= 1 <= f['maximum'])
        document.edit(row['table'], row['id'], field['key'], 1)
        start = document._row(row['table'], row['id'])[1]
        spec = next(f['spec'] for f in document.schemas[row['table']]['fields'] if f['spec'].key == field['key'])
        allowed.update(range(start + spec.offset, start + spec.offset + 4))
        changed.append((row['table'], row['id'], field['key']))
    reopened = ItemDocument(document.export())
    for table, row_id, field in changed:
        assert reopened.value(table, row_id, field) == 1
    before, after = inflate(raw), inflate(document.export())
    assert len(before) == len(after)
    assert {i for i, (a, b) in enumerate(zip(before, after)) if a != b} <= allowed
    assert document.dirty_count == len(set(changed))


def test_validation_and_bit_preservation():
    document = ItemDocument(make_archive())
    table = 'EquipParamGoods'
    field = next(f for f in document.schemas[table]['fields'] if f['editable'] and f['spec'].bit_size == 1)
    spec = field['spec']
    start = document._row(table, 100)[1] + spec.offset
    before = bytes(document.plain)
    document.edit(table, 100, spec.key, 1)
    differences = [(i, a ^ b) for i, (a, b) in enumerate(zip(before, document.plain)) if a != b]
    assert differences == [(start, 1 << spec.bit_offset)]
    document.edit(table, 100, spec.key, 0)
    assert document.export() == document.original and document.dirty_count == 0
    for value in (0.5, -1, 256, float('nan'), '1'):
        with pytest.raises(FormatError): document.edit(table, 100, 'goodsType', value)
    padding = next(f['spec'].key for f in document.schemas[table]['fields'] if f['spec'].padding)
    with pytest.raises(FormatError): document.edit(table, 100, padding, 0)
    with pytest.raises(FormatError): ItemDocument(document.original[:-1])


def test_project_save_reload_isolation_and_stale_writes(tmp_path):
    game, mod = project(tmp_path)
    raw = (game / RELATIVE).read_bytes()
    store = ItemStore(game, mod, False)
    store.edit('EquipParamGoods', 100, 'sellValue', 42)
    store.save()
    assert (game / RELATIVE).read_bytes() == raw
    assert ItemStore(game, mod, False).get().value('EquipParamGoods', 100, 'sellValue') == 42
    assert ItemStore(game, mod, True).get().value('EquipParamGoods', 100, 'sellValue') == 42
    with pytest.raises(PermissionError): ItemStore(game).edit('EquipParamGoods', 100, 'sellValue', 8)
    with pytest.raises(ValueError): ItemStore(game, game / 'mod', False).get()
    store.edit('EquipParamGoods', 100, 'sellValue', 44)
    (mod / RELATIVE).write_bytes(raw)
    with pytest.raises(ValueError, match='changed outside'): store.save()
    store.discard()
    assert store.get().value('EquipParamGoods', 100, 'sellValue') == 0
    (game / RELATIVE).write_bytes(raw + b'changed')
    with pytest.raises(ValueError, match='changed outside'): store.save()


def test_service_edit_save_and_reload(tmp_path):
    game, mod = project(tmp_path)
    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                          'LEXEDITOR_MOD_READ_ONLY': '0', 'LEXEDITOR_NO_MOD': '0'})
    def request(path, payload=None):
        req = Request(session.url.rstrip('/') + path, data=None if payload is None else json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json'})
        with urlopen(req) as reply: return json.load(reply)
    try:
        session.start()
        assert len(request('/api/state')['tabs']) == 8
        assert request('/api/edit', {'table': 'EquipParamGoods', 'id': 100, 'field': 'sellValue', 'value': 42})['dirtyCount'] == 1
        assert request('/api/save', {})['saved']
        request('/api/discard', {})
        row = request('/api/row?table=EquipParamGoods&id=100')['row']
        assert next(f['value'] for f in row['fields'] if f['key'] == 'sellValue') == 42
        with pytest.raises(HTTPError): request('/api/edit', {'table': 'EquipParamGoods', 'id': 100, 'field': 'goodsType', 'value': 999})
    finally:
        session.stop()


def test_pending_changes_read_newest_first():
    # Lexer: "new things get placed on the top of the list".
    document = ItemDocument(make_archive())
    edited, originals = [], []
    for tab, _, _ in SUBTABS[:3]:
        row = document.list_rows(tab)[0]
        field = next(f for f in document.read_row(row['table'], row['id'])['fields']
                     if f['editable'] and f['type'] == 'number' and f['minimum'] <= 1 <= f['maximum'] and f['value'] != 1)
        document.edit(row['table'], row['id'], field['key'], 1)
        edited.append(field['label'])
        originals.append(field['value'])
    labels = [change['label'] for change in document.pending_changes()]
    assert [next(label for label in edited if entry.endswith(label)) for entry in labels] == edited[::-1]
    # Editing the oldest again brings it back to the top.
    first = labels[-1]
    row = document.list_rows(SUBTABS[0][0])[0]
    key = next(f['key'] for f in document.read_row(row['table'], row['id'])['fields'] if f['label'] == edited[0])
    document.edit(row['table'], row['id'], key, 2 if originals[0] != 2 else 3)
    assert document.pending_changes()[0]['label'] == first


def test_putting_a_float_back_as_shown_leaves_nothing_to_save():
    # Lexer: undo all the way back "and there are still 7 changes". Undo sends
    # back the value as shown (seven digits); a float needs up to nine.
    document = ItemDocument(make_archive())
    for tab, _, _ in SUBTABS:
        row = document.list_rows(tab)[0]
        fields = [f for f in document.read_row(row['table'], row['id'])['fields']
                  if f['editable'] and f['dtype'] == 'f32' and isinstance(f['value'], float)]
        if fields:
            break
    field = fields[0]
    # A saved value that seven digits cannot spell exactly, as most are.
    from plugins.ds1.formats import write_field, read_field
    spec = next(f['spec'] for f in document.schemas[row['table']]['fields'] if f['spec'].key == field['key'])
    _r, start, data = document._row(row['table'], row['id'])
    third = write_field(data, spec, 1 / 3, '<')
    document.plain[start:start + len(data)] = third
    original = document.original_plain
    document.original_plain = original[:start] + bytes(third) + original[start + len(data):]
    shown = document.read_row(row['table'], row['id'])['fields'][[f['key'] for f in document.read_row(row['table'], row['id'])['fields']].index(field['key'])]['value']
    assert shown != read_field(third, spec, '<')
    document.edit(row['table'], row['id'], field['key'], shown + 1 if shown + 1 <= field['maximum'] else shown - 1)
    assert document.dirty_count == 1
    document.edit(row['table'], row['id'], field['key'], shown)
    assert document.dirty_count == 0
    assert bytes(document.plain) == bytes(document.original_plain)
