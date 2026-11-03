"""Drop-table references resolve to the Drops tab, with picker choices."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument, LINK_NOUNS, field_link


def test_item_lot_reference_resolves_to_drop_kind():
    doc = ItemDocument(make_archive())
    assert field_link(doc, 'NpcParam', 120000,
                      SimpleNamespace(reference='ItemLotParam')) == ('drop', 'ItemLotParam')


def test_drop_link_choices_list_lots():
    doc = ItemDocument(make_archive())
    choices = doc.link_choices('drop', 'ItemLotParam')
    assert choices['100'] == doc.display_name('ItemLotParam', 100)
    assert choices['-1'] == 'None'


def test_drop_noun():
    assert LINK_NOUNS['drop'] == 'drop table'
