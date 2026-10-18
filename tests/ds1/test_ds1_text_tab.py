"""Menu labels live in the Text tab, named by their text.

The equipment defense labels (MagDEF, FireDEF, LitngDEF) are menu text,
not items; the Text tab lists them under their in-game text, and armor
defense fields link to them.
"""
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive
from plugins.ds1 import texts
from plugins.ds1.formats import ItemDocument, TEXT_SUBTABS, SUBTABS, FMG_SUBTABS, FMG_TABLES
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session


def test_menu_labels_are_a_text_subtab_not_an_items_one():
    assert [tab for tab, _, _ in SUBTABS if tab == 'menu-labels'] == []
    assert TEXT_SUBTABS[0] == ('menu-labels', 'Menu labels', 'MenuText')
    assert TEXT_SUBTABS[1:] == FMG_SUBTABS
    assert len(FMG_SUBTABS) == 14
    assert {table for _, _, table in FMG_SUBTABS} == FMG_TABLES


def test_menu_label_ids_match_the_three_defense_kinds():
    assert texts.MENU_LABELS == {'magicDefense': ('Magic defense label', 102204),
                                 'fireDefense': ('Fire defense label', 102205),
                                 'lightningDefense': ('Lightning defense label', 102206)}


def test_menu_label_rows_take_their_names_from_the_text():
    document = ItemDocument(make_archive())
    document.menu_texts = texts.MenuDocument(make_menu_archive())
    rows = {row['id']: row['name'] for row in document.list_rows('menu-labels')}
    assert rows == {102204: 'MagDEF', 102205: 'FireDEF', 102206: 'LitngDEF'}
    assert document.read_row('MenuText', 102205)['name'] == 'FireDEF'
    assert document.display_name('MenuText', 102206) == 'LitngDEF'
    assert document.display_name('MenuText', 999999) == 'Menu label 999999'


def test_text_tab_state_and_label_roundtrip(tmp_path):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    (game / texts.MENU_RELATIVE).parent.mkdir(parents=True, exist_ok=True)
    (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                          'LEXEDITOR_MOD_READ_ONLY': '0', 'LEXEDITOR_NO_MOD': '0'})

    def request(path, payload=None):
        req = Request(session.url.rstrip('/') + path, data=None if payload is None else json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json'})
        with urlopen(req) as reply:
            return json.load(reply)

    try:
        session.start()
        state = request('/api/state')
        assert [tab['id'] for tab in state['tabs']] == [tab for tab, _, _ in SUBTABS]
        assert state['textTabs'] == [{'id': 'menu-labels', 'label': 'Menu labels',
                                      'table': 'MenuText', 'count': 3},
                                     {'id': 'fmg-menu-text', 'label': 'Menu text',
                                      'table': 'Menu_general_text_.fmg', 'count': 3}]
        edited = request('/api/edit', {'table': 'MenuText', 'id': 102204, 'field': 'label', 'value': 'MagAbsorb'})
        assert edited['values'] == {'label': 'MagAbsorb'}
        row = request('/api/row?table=MenuText&id=102204')['row']
        assert row['name'] == 'MagAbsorb'
        assert next(f['value'] for f in row['fields'] if f['key'] == 'label') == 'MagAbsorb'
    finally:
        session.stop()


DIALOGUE = {10: 'Yes.', 11: 'No.\nReally not.'}


def dialogue_document():
    from ds1_fixture import make_menu_archive
    document = ItemDocument(make_archive())
    document.menu_texts = texts.MenuDocument(
        make_menu_archive(extra={'Dialogue_.fmg': dict(DIALOGUE)}))
    return document


def test_text_subtabs_follow_the_files_present():
    document = dialogue_document()
    assert [entry[0] for entry in document.text_subtabs()] == [
        'menu-labels', 'fmg-dialogue', 'fmg-menu-text']
    bare = ItemDocument(make_archive())
    bare.menu_texts = texts.MenuDocument(make_menu_archive())
    assert [entry[0] for entry in bare.text_subtabs()] == ['menu-labels', 'fmg-menu-text']


def test_fmg_rows_list_every_filled_entry_named_by_text():
    rows = dialogue_document().list_rows('fmg-dialogue')
    assert [(row['id'], row['table'], row['name']) for row in rows] == [
        (10, 'Dialogue_.fmg', 'Yes.'), (11, 'Dialogue_.fmg', 'No.')]
    assert rows[1]['values'] == {'text': 'No.\nReally not.'}


def test_fmg_read_edit_and_dirty_roundtrip():
    from plugins.ds1.formats import FormatError
    document = dialogue_document()
    row = document.read_row('Dialogue_.fmg', 11)
    assert row['name'] == 'No.'
    field = next(item for item in row['fields'] if item['key'] == 'text')
    assert field['type'] == 'longtext' and field['value'] == 'No.\nReally not.'
    assert document.display_name('Dialogue_.fmg', 10) == 'Yes.'
    assert document.display_name('Dialogue_.fmg', 999) == 'Dialogue 999'
    edited = document.edit('Dialogue_.fmg', 11, 'text', 'No.\nNever.')
    assert edited['fields'][0]['value'] == 'No.\nNever.'
    assert document.dirty_count == 1
    assert document.menu_texts.dirty_texts == {('Dialogue_.fmg', 11)}
    changes = document.pending_changes()
    assert [change['label'] for change in changes] == ['Dialogue · 11']
    assert (changes[0]['before'], changes[0]['after']) == ('No.\nReally not.', 'No.\nNever.')
    rebuilt = texts.MenuDocument(document.menu_texts.export())
    assert rebuilt.text('Dialogue_.fmg', 11) == 'No.\nNever.'
    assert rebuilt.label('magicDefense') == 'MagDEF'
    for bad in ('   ', 'x' * 4001):
        try:
            document.edit('Dialogue_.fmg', 11, 'text', bad)
        except FormatError:
            pass
        else:
            raise AssertionError(f'accepted {bad[:8]!r}')
    try:
        document.edit('Dialogue_.fmg', 999, 'text', 'New.')
    except FormatError:
        pass
    else:
        raise AssertionError('sprouted a new entry')


def test_text_rows_mark_modified_after_edit():
    document = ItemDocument(make_archive())
    document.menu_texts = texts.MenuDocument(make_menu_archive())
    tab = next(entry[0] for entry in FMG_SUBTABS if entry[2] in document.menu_texts.files())
    rows = document.list_rows(tab)
    assert rows and all(not row.get('modified') for row in rows)
    first = rows[0]
    document.edit(first['table'], first['id'], 'text',
                  (document.menu_texts.text(first['table'], first['id']) or 'x') + '!')
    flags = {row['id']: row.get('modified') for row in document.list_rows(tab)}
    assert flags[first['id']] is True
    assert all(value is not True for key, value in flags.items() if key != first['id'])
    labels = ItemDocument(make_archive())
    labels.menu_texts = texts.MenuDocument(make_menu_archive())
    assert all(not row.get('modified') for row in labels.list_rows('menu-labels'))
    labels.edit('MenuText', 102205, 'label', 'FireDEF!')
    flags = {row['id']: row.get('modified') for row in labels.list_rows('menu-labels')}
    assert flags[102205] is True
    assert all(value is not True for key, value in flags.items() if key != 102205)


def test_description_edit_marks_its_item_row_modified():
    from ds1_fixture import make_text_archive
    document = ItemDocument(make_archive())
    document.texts = texts.TextDocument(make_text_archive())
    row = document.list_rows('consumables')[0]
    assert document.row_modified(row['table'], row['id']) is False
    document.edit(row['table'], row['id'], 'description', 'A safer stone.')
    assert document.row_modified(row['table'], row['id']) is True
