"""List and detail rows carry the vanilla name, for blank-rename restore."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ds1_fixture import make_archive, make_text_archive
from plugins.ds1.formats import ItemDocument
from plugins.ds1.texts import TextDocument

TABLE = 'EquipParamWeapon'


def renamed_doc():
    doc = ItemDocument(make_archive())
    doc.vanilla_document = ItemDocument(make_archive())
    doc.texts = TextDocument(make_text_archive(names={'EquipParamWeapon': {100: 'Mod Sword'}}))
    doc.vanilla_texts = TextDocument(make_text_archive())
    return doc


def test_list_rows_carry_shipped_name():
    rows = renamed_doc().list_rows('weapons')
    row = next(entry for entry in rows if entry['id'] == 100)
    assert row['name'] == 'Mod Sword'
    assert row['shippedName'] == 'Fixture Sword'


def test_read_row_carries_shipped_name():
    row = renamed_doc().read_row(TABLE, 100)
    assert row['name'] == 'Mod Sword'
    assert row['shippedName'] == 'Fixture Sword'


def test_no_vanilla_text_means_no_shipped_name():
    doc = ItemDocument(make_archive())
    doc.texts = TextDocument(make_text_archive(names={'EquipParamWeapon': {100: 'Mod Sword'}}))
    assert doc.read_row(TABLE, 100)['shippedName'] is None
