"""NPCs tab: friend gating and shop price edits on synthetic params."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest
from ds1_fixture import make_archive
from plugins.ds1.formats import FormatError, ItemDocument


def test_npcs_tab_lists_friends_only():
    document = ItemDocument(make_archive())
    rows = document.list_rows('npcs')
    assert {row['id'] for row in rows} == {251000, 321001}
    assert all(row['table'] == 'NpcParam' for row in rows)


def test_friend_read_and_edit():
    document = ItemDocument(make_archive())
    row = document.read_row('NpcParam', 251000)
    assert row['fields']
    document.edit('NpcParam', 251000, 'hp', 500)
    assert document.value('NpcParam', 251000, 'hp') == 500
    assert document.read_row('NpcParam', 251000)['id'] == 251000


def test_unreviewed_rows_stay_shut():
    document = ItemDocument(make_archive())
    assert not document.is_monster(223000) and not document.is_friend(223000)
    with pytest.raises(FormatError, match='reviewed monster or NPC'):
        document.read_row('NpcParam', 223000)
    with pytest.raises(FormatError, match='reviewed monster or NPC'):
        document.edit('NpcParam', 223000, 'hp', 500)


def test_unowned_shops_lists_lines_without_merchants():
    document = ItemDocument(make_archive())
    rows = document.list_rows('unowned-shops')
    assert {row['id'] for row in rows} == {100, 101, 102}
    assert all(row['table'] == 'ShopLineupParam' for row in rows)


def test_owned_line_leaves_the_unowned_list():
    # Row 1100 carries a real merchant-prefixed Smithbox name; 100 has none.
    document = ItemDocument(make_archive(table_ids={'ShopLineupParam': [100, 1100]}))
    rows = document.list_rows('unowned-shops')
    assert {row['id'] for row in rows} == {100}


def test_shop_price_edit():
    document = ItemDocument(make_archive())
    row_id = document.params['ShopLineupParam'].rows[0].row_id
    document.edit('ShopLineupParam', row_id, 'value', 777)
    assert document.value('ShopLineupParam', row_id, 'value') == 777
