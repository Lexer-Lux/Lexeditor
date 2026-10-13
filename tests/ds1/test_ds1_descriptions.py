"""Item descriptions: short and long FMG texts editable per item."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive, make_text_archive
from plugins.ds1 import data_map, mod_loader, texts
from plugins.ds1.formats import FormatError, ItemDocument
from plugins.ds1.store import MARKER, RELATIVE, ItemStore


def project(tmp_path, raw=None, words=None):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive() if raw is None else raw)
    (game / texts.RELATIVE).parent.mkdir(parents=True)
    (game / texts.RELATIVE).write_bytes(make_text_archive() if words is None else words)
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def test_descriptions_roundtrip_both_copies_and_nothing_else():
    document = texts.TextDocument(make_text_archive())
    assert document.description('EquipParamGoods', 100) == 'A stone of safety.'
    assert document.description('EquipParamGoods', 100, long=True).startswith('A stone that keeps')
    assert document.description('Magic', 100) is None
    document.set_description('EquipParamGoods', 100, 'A safer stone.')
    document.set_description('EquipParamGoods', 100, 'Line one.\r\nLine two.', long=True)
    document.set_description('Magic', 100, 'A new spell summary.')
    assert document.dirty == {('description', 'EquipParamGoods', 100),
                              ('longDescription', 'EquipParamGoods', 100),
                              ('description', 'Magic', 100)}
    reread = texts.TextDocument(document.export())
    assert reread.description('EquipParamGoods', 100) == 'A safer stone.'
    assert reread.description('EquipParamGoods', 100, long=True) == 'Line one.\nLine two.'
    assert reread.description('Magic', 100) == 'A new spell summary.'
    assert reread.description('EquipParamWeapon', 100) == 'A blade for testing.'
    for filename in ('Item_description_.fmg', 'Item_long_desc_.fmg'):
        copies = [position for position in reread.tables if reread._file(position) == filename]
        assert len(copies) == 2
    assert reread.name('EquipParamGoods', 100) == 'Fixture Stone'


def test_clearing_a_description_removes_its_text():
    document = texts.TextDocument(make_text_archive())
    assert document.set_description('EquipParamGoods', 100, '   ') is None
    assert document.set_description('EquipParamGoods', 100, '', long=True) is None
    reread = texts.TextDocument(document.export())
    assert reread.description('EquipParamGoods', 100) is None
    assert reread.description('EquipParamGoods', 100, long=True) is None


@pytest.mark.parametrize('long,value', [
    (False, 'two\nlines'),
    (False, 'x' * (texts.MAX_DESCRIPTION + 1)),
    (False, 'bell\a'),
    (True, 'x' * (texts.MAX_LONG_DESCRIPTION + 1)),
    (True, 'tab\there'),
])
def test_a_bad_description_is_refused(long, value):
    with pytest.raises(FormatError):
        texts.TextDocument(make_text_archive()).set_description('EquipParamGoods', 100, value, long=long)


def test_item_detail_shows_both_descriptions(tmp_path):
    document = ItemDocument(make_archive())
    assert [field['key'] for field in document.read_row('EquipParamGoods', 100)['fields']
            if field['key'] in ('description', 'longDescription')] == []
    game, mod = project(tmp_path)
    store = ItemStore(game, mod, read_only=False)
    fields = {field['key']: field for field in store.get().read_row('EquipParamGoods', 100)['fields']}
    short, full = fields['description'], fields['longDescription']
    assert (short['type'], short['group'], short['editable']) == ('text', 'Description', True)
    assert (full['type'], full['group'], full['editable']) == ('longtext', 'Description', True)
    assert short['value'] == 'A stone of safety.' and short['vanilla'] == 'A stone of safety.'
    assert full['value'].startswith('A stone that keeps') and full['vanilla'] == full['value']
    assert short['description'] and full['description']
    assert 'description' not in {field['key'] for field in store.get().read_row('NpcParam', 120000)['fields']}


def test_descriptions_save_into_the_mod_and_reject_foreign_tables(tmp_path):
    game, mod = project(tmp_path)
    store = ItemStore(game, mod, read_only=False)
    store.edit('EquipParamGoods', 100, 'description', 'A safer stone.')
    store.edit('EquipParamGoods', 100, 'longDescription', 'Line one.\nLine two.')
    assert store.get().dirty_count == 2
    assert not (mod / texts.RELATIVE).exists()
    store.save()
    reopened = ItemStore(game, mod, read_only=False)
    fields = {field['key']: field for field in reopened.get().read_row('EquipParamGoods', 100)['fields']}
    assert fields['description']['value'] == 'A safer stone.'
    assert fields['longDescription']['value'] == 'Line one.\nLine two.'
    assert reopened.get().dirty_count == 0
    with pytest.raises(FormatError):
        store.edit('NpcParam', 120000, 'description', 'Rat lore.')
    with pytest.raises(PermissionError):
        ItemStore(game).edit('EquipParamGoods', 100, 'description', 'Nope.')


def test_descriptions_merge_by_entry_and_conflict_by_role():
    vanilla = make_text_archive()
    game = {texts.RELATIVE: vanilla}

    def edited(*edits):
        document = texts.TextDocument(vanilla)
        for table, row, value, long in edits:
            document.set_description(table, row, value, long)
        return document.export()

    def mod(name, words):
        return mod_loader.Mod(name, Path(name), {texts.RELATIVE: words})

    a = mod('A', edited(('EquipParamGoods', 100, 'Alpha short.', False)))
    b = mod('B', edited(('EquipParamGoods', 100, 'Alpha long.\nSecond line.', True)))
    result = mod_loader.compose(game, [a, b])
    assert result.conflicts == []
    merged = texts.TextDocument(result.files[texts.RELATIVE])
    assert merged.description('EquipParamGoods', 100) == 'Alpha short.'
    assert merged.description('EquipParamGoods', 100, long=True) == 'Alpha long.\nSecond line.'
    c = mod('C', edited(('EquipParamGoods', 100, 'Gamma short.', False)))
    result = mod_loader.compose(game, [a, c])
    assert [(c.part, c.mods) for c in result.conflicts] == [('Description 100 (Item description)', ['A', 'C'])]
    d = mod('D', edited(('EquipParamGoods', 100, 'Delta long.', True)))
    result = mod_loader.compose(game, [b, d])
    assert [(c.part, c.mods) for c in result.conflicts] == [('Full description 100 (Item long desc)', ['B', 'D'])]


def test_data_map_points_descriptions_at_items(tmp_path):
    game, mod = project(tmp_path)
    rows = data_map.payload(ItemStore(game, mod, False))['rows']
    descs = [row for row in rows if row['id'].startswith('desc:')]
    assert len(descs) == 10
    for row in descs:
        assert row['coverage'] == 'structured' and row['status'] == 'partial'
        assert row['openable'] and row['target'] == 'items'
    goods = next(row for row in rows if row['id'] == 'name:EquipParamGoods')
    assert {row['sub'] for row in descs if 'EquipParamGoods' in row['id']} == {goods['sub']}
    assert not [row for row in rows if row['id'].startswith('message:')]


def test_pending_changes_names_description_edits(tmp_path):
    game, mod = project(tmp_path)
    store = ItemStore(game, mod, read_only=False)
    store.edit('EquipParamGoods', 100, 'description', 'A safer stone.')
    store.rename('EquipParamGoods', 100, 'Soul Safety Stone')
    labels = [row['label'] for row in store.get().pending_changes()]
    assert 'Description · EquipParamGoods 100' in labels
    assert 'Name · EquipParamGoods 100' in labels
