"""Text dirty sets are computed once and memoized, not re-diffed per row.

row_modified() consults texts.dirty for every listed row; recomputing the
full FMG diff each time turned /api/state into a 27-second call on the
installed game. The sets stay live: every text edit invalidates them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_menu_archive, make_text_archive
from plugins.ds1 import texts


def test_item_text_dirty_is_memoized_until_edited():
    document = texts.TextDocument(make_text_archive())
    assert document.dirty is document.dirty
    assert document.dirty == set()
    document.rename('EquipParamGoods', 100, 'Renamed Stone')
    first = document.dirty
    assert first == {('name', 'EquipParamGoods', 100)}
    assert document.dirty is first
    document.set_description('EquipParamGoods', 100, 'New words')
    assert document.dirty == {('name', 'EquipParamGoods', 100),
                              ('description', 'EquipParamGoods', 100)}


def test_menu_dirty_sets_are_memoized_until_edited():
    document = texts.MenuDocument(make_menu_archive())
    assert document.dirty is document.dirty
    assert document.dirty_texts is document.dirty_texts
    document.set_label('magicDefense', 'MagD')
    assert document.dirty == {'magicDefense'}
    assert document.dirty is not document.dirty_texts
