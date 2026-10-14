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
from plugins.ds1.formats import ItemDocument, TEXT_SUBTABS, SUBTABS
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session


def test_menu_labels_are_a_text_subtab_not_an_items_one():
    assert [tab for tab, _, _ in SUBTABS if tab == 'menu-labels'] == []
    assert TEXT_SUBTABS == (('menu-labels', 'Menu labels', 'MenuText'),)


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
                                      'table': 'MenuText', 'count': 3}]
        edited = request('/api/edit', {'table': 'MenuText', 'id': 102204, 'field': 'label', 'value': 'MagAbsorb'})
        assert edited['values'] == {'label': 'MagAbsorb'}
        row = request('/api/row?table=MenuText&id=102204')['row']
        assert row['name'] == 'MagAbsorb'
        assert next(f['value'] for f in row['fields'] if f['key'] == 'label') == 'MagAbsorb'
    finally:
        session.stop()
