"""Starting classes and gifts: Menu_others_ descriptions editable per row."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive, make_menu_archive
from plugins.ds1 import mod_loader, texts
from plugins.ds1.formats import FormatError, ItemDocument, stats_fields
from plugins.ds1.store import MARKER, RELATIVE, ItemStore

WORDS = {'Menu_others_.fmg': {132320: 'Fearless test.\nSecond line.',
                              132321: 'Knight test.',
                              132351: 'Gift test desc.'}}
ROWS = {'CharaInitParam': [3000, 3001, 2401, 9999]}


def project(tmp_path, words=None):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive(table_ids=ROWS))
    (game / texts.MENU_RELATIVE).parent.mkdir(parents=True)
    (game / texts.MENU_RELATIVE).write_bytes(
        make_menu_archive(extra=WORDS if words is None else words))
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def test_class_detail_shows_its_menu_description(tmp_path):
    game, mod = project(tmp_path)
    store = ItemStore(game, mod, read_only=False)
    fields = {field['key']: field
              for field in store.get().read_row('CharaInitParam', 3000)['fields']}
    desc = fields['longDescription']
    assert (desc['label'], desc['type'], desc['group'], desc['editable']) == (
        'Description', 'longtext', 'Description', True)
    assert desc['value'] == 'Fearless test.\nSecond line.'
    assert desc['vanilla'] == desc['value']
    assert 'class' in desc['description']
    gift = {field['key']: field
            for field in store.get().read_row('CharaInitParam', 2401)['fields']}
    assert gift['longDescription']['value'] == 'Gift test desc.'
    assert 'gift' in gift['longDescription']['description']
    plain = {field['key'] for field in store.get().read_row('CharaInitParam', 9999)['fields']}
    assert 'longDescription' not in plain and 'description' not in plain


def test_class_description_without_menu_text_has_no_field(tmp_path):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive(table_ids=ROWS))
    mod.mkdir()
    (mod / MARKER).touch()
    store = ItemStore(game, mod, read_only=False)
    fields = {field['key'] for field in store.get().read_row('CharaInitParam', 3000)['fields']}
    assert 'longDescription' not in fields
    with pytest.raises(FormatError):
        store.edit('CharaInitParam', 3000, 'longDescription', 'Nope.')


def test_class_description_edit_roundtrip_and_save(tmp_path):
    game, mod = project(tmp_path)
    store = ItemStore(game, mod, read_only=False)
    assert not store.get().row_modified('CharaInitParam', 3000)
    store.edit('CharaInitParam', 3000, 'longDescription', 'Fearless edit.\nStill two lines.')
    assert store.get().row_modified('CharaInitParam', 3000)
    assert not store.get().row_modified('CharaInitParam', 3001)
    store.save()
    reopened = ItemStore(game, mod, read_only=False)
    fields = {field['key']: field
              for field in reopened.get().read_row('CharaInitParam', 3000)['fields']}
    assert fields['longDescription']['value'] == 'Fearless edit.\nStill two lines.'
    assert reopened.get().row_modified('CharaInitParam', 3000)


def test_clearing_a_class_description_removes_its_text(tmp_path):
    game, mod = project(tmp_path)
    store = ItemStore(game, mod, read_only=False)
    store.edit('CharaInitParam', 3000, 'longDescription', '   ')
    fields = {field['key']: field
              for field in store.get().read_row('CharaInitParam', 3000)['fields']}
    assert fields['longDescription']['value'] == ''
    assert fields['longDescription']['vanilla'] == 'Fearless test.\nSecond line.'


@pytest.mark.parametrize('table,row,value', [
    ('CharaInitParam', 3000, 'x' * (texts.MAX_LONG_DESCRIPTION + 1)),
    ('CharaInitParam', 3000, 'bell\a'),
    ('CharaInitParam', 9999, 'Nowhere to put this.'),
])
def test_a_bad_class_description_is_refused(tmp_path, table, row, value):
    game, mod = project(tmp_path)
    store = ItemStore(game, mod, read_only=False)
    with pytest.raises(FormatError):
        store.edit(table, row, 'longDescription', value)


def test_class_short_description_key_is_protected(tmp_path):
    game, mod = project(tmp_path)
    store = ItemStore(game, mod, read_only=False)
    with pytest.raises(FormatError):
        store.edit('CharaInitParam', 3000, 'description', 'One line.')


def test_gift_description_survives_the_subtab_filter(tmp_path):
    game, mod = project(tmp_path)
    store = ItemStore(game, mod, read_only=False)
    only = stats_fields('starting-gifts', 'CharaInitParam')
    fields = {field['key']: field
              for field in store.get().read_row('CharaInitParam', 2401, only=only)['fields']}
    assert fields['longDescription']['value'] == 'Gift test desc.'
    assert fields['longDescription']['editable']


def test_class_descriptions_merge_by_entry():
    vanilla = make_menu_archive(extra=WORDS)
    game = {texts.MENU_RELATIVE: vanilla}

    def edited(row, value):
        document = texts.MenuDocument(vanilla)
        document.set_class_description('CharaInitParam', row, value)
        return document.export()

    def mod(name, words):
        return mod_loader.Mod(name, Path(name), {texts.MENU_RELATIVE: words})

    result = mod_loader.compose(game, [mod('A', edited(3000, 'Alpha.')),
                                       mod('B', edited(3001, 'Beta.'))])
    assert result.conflicts == []
    merged = texts.MenuDocument(result.files[texts.MENU_RELATIVE])
    assert merged.class_description('CharaInitParam', 3000) == 'Alpha.'
    assert merged.class_description('CharaInitParam', 3001) == 'Beta.'
