"""row_modified compares against vanilla, so saved edits stay marked."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ds1_fixture import make_archive, make_text_archive
from plugins.ds1.formats import ItemDocument
from plugins.ds1.texts import TextDocument

TABLE = 'EquipParamWeapon'


def loaded(saved_values=None):
    """A mod saved with saved_values, reloaded: session dirty is empty but
    vanilla still tells what changed."""
    doc = ItemDocument(make_archive(field_values={TABLE: saved_values or {}}))
    doc.texts = None
    doc.vanilla_document = ItemDocument(make_archive())
    assert not doc.dirty
    return doc


def test_saved_edit_stays_modified_after_reload():
    doc = loaded({100: {'weight': 5.0}})
    assert doc.row_modified(TABLE, 100) is True


def test_untouched_row_is_not_modified():
    doc = loaded({100: {'weight': 5.0}})
    assert doc.row_modified(TABLE, 101) is False


def test_session_edit_is_modified_without_vanilla():
    doc = ItemDocument(make_archive())
    doc.texts = None
    doc.edit(TABLE, 101, 'weight', 7.0)
    assert doc.row_modified(TABLE, 101) is True


def test_export_reload_keeps_param_edit_marked():
    vanilla = make_archive()
    doc = ItemDocument(make_archive())
    doc.texts = None
    doc.vanilla_document = ItemDocument(vanilla)
    doc.edit(TABLE, 100, 'weight', 5.0)
    assert doc.row_modified(TABLE, 100) is True
    reloaded = ItemDocument(doc.export())
    reloaded.texts = None
    reloaded.vanilla_document = ItemDocument(vanilla)
    assert not reloaded.dirty
    assert reloaded.row_modified(TABLE, 100) is True
    assert reloaded.row_modified(TABLE, 101) is False


def test_saved_rename_stays_modified_after_reload():
    doc = ItemDocument(make_archive())
    doc.vanilla_document = ItemDocument(make_archive())
    doc.texts = TextDocument(make_text_archive(names={'EquipParamWeapon': {100: 'Mod Sword'}}))
    doc.vanilla_texts = TextDocument(make_text_archive())
    assert not doc.dirty
    assert doc.row_modified(TABLE, 100) is True
    assert doc.row_modified(TABLE, 101) is False
