"""A mod's changed records and loaded files, against vanilla."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive  # noqa: E402
from plugins.ds1 import mod_loader, texts  # noqa: E402
from plugins.ds1.formats import ItemDocument  # noqa: E402
from plugins.ds1.store import RELATIVE  # noqa: E402


def layout(tmp_path, params, item_texts=None, menu_texts=None, extra=None):
    root = Path(tmp_path)
    (root / RELATIVE).parent.mkdir(parents=True, exist_ok=True)
    (root / RELATIVE).write_bytes(params)
    if item_texts is not None:
        (root / texts.RELATIVE).parent.mkdir(parents=True, exist_ok=True)
        (root / texts.RELATIVE).write_bytes(item_texts)
    if menu_texts is not None:
        (root / texts.MENU_RELATIVE).parent.mkdir(parents=True, exist_ok=True)
        (root / texts.MENU_RELATIVE).write_bytes(menu_texts)
    for relative, content in (extra or {}).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return root


def test_changed_added_and_removed_rows_list_their_fields(tmp_path):
    vanilla = layout(tmp_path / 'game', make_archive())
    mod_doc = ItemDocument(make_archive())
    mod_doc.edit('EquipParamGoods', 100, 'basicPrice', 999)
    mod_doc.add_row('EquipParamGoods', 100, 500)
    mod_doc.remove_row('EquipParamAccessory', 102)
    mod = layout(tmp_path / 'mod', mod_doc.export())
    result = mod_loader.describe_changes(mod, vanilla)
    assert result['truncated'] is False
    assert result['note'] == ''
    by_key = {(entry['table'], entry['id']): entry for entry in result['changes']}
    changed = by_key[('EquipParamGoods', 100)]
    assert changed['added'] is False and changed['removed'] is False
    assert any('price' in field.lower() for field in changed['fields'])
    assert by_key[('EquipParamGoods', 500)]['added'] is True
    assert by_key[('EquipParamAccessory', 102)]['removed'] is True
    assert ('EquipParamGoods', 101) not in by_key


def test_text_entries_show_before_and_after(tmp_path):
    vanilla = layout(tmp_path / 'game', make_archive(),
                     make_text_archive(), make_menu_archive())
    mod = layout(tmp_path / 'mod', make_archive(),
                 make_text_archive(names={'EquipParamGoods': {100: 'Changed Stone', 101: 'Fixture Key'}}),
                 make_menu_archive(labels={102204: 'ChangedDEF', 102205: 'FireDEF', 102206: 'LitngDEF'}))
    result = mod_loader.describe_changes(mod, vanilla)
    by_key = {(entry['table'], entry['id']): entry for entry in result['changes']}
    name = by_key[('Item name', 100)]
    assert name['before'] == 'Fixture Stone'
    assert name['after'] == 'Changed Stone'
    menu = by_key[('Menu Menu general text', 102204)]
    assert menu['before'] == 'MagDEF'
    assert menu['after'] == 'ChangedDEF'
    assert ('Item name', 101) not in by_key


def test_missing_game_or_archives_explain_themselves(tmp_path):
    mod = layout(tmp_path / 'mod', make_archive())
    result = mod_loader.describe_changes(mod, None)
    assert result['changes'] == []
    assert 'Locate the game' in result['note']
    bare = layout(tmp_path / 'bare', make_archive())
    (bare / RELATIVE).unlink()
    vanilla = layout(tmp_path / 'game', make_archive())
    assert mod_loader.describe_changes(bare, vanilla)['changes'] == []


def test_loaded_files_are_the_archives_and_maps(tmp_path):
    mod_doc = ItemDocument(make_archive())
    mod = layout(tmp_path / 'mod', mod_doc.export(),
                 make_text_archive(), make_menu_archive(),
                 extra={'map/MapStudio/m10_00_00_00.msb': b'msb-bytes', 'notes.txt': b'read me'})
    loaded = mod_loader.loaded_files(mod)
    assert RELATIVE.as_posix().casefold() in loaded
    assert 'map/mapstudio/m10_00_00_00.msb' in loaded
    assert 'notes.txt' not in loaded
    assert 'mod.json' not in loaded
