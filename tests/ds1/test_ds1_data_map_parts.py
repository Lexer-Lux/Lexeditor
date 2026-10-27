"""Data Map points equipment models at their Items previews."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from plugins.ds1.store import ItemStore, RELATIVE, MARKER
from plugins.ds1 import data_map


def make_store(root, areas=()):
    game, mod = root / 'game', root / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    for folder in areas:
        (game / folder).mkdir(parents=True)
    mod.mkdir()
    (mod / MARKER).touch()
    return ItemStore(game, mod, False)


def test_parts_row_names_the_items_model_previews(tmp_path):
    rows = data_map.payload(make_store(tmp_path, ('parts',)))['rows']
    parts = next(row for row in rows if row['id'] == 'assets:parts')
    assert parts['coverage'] == 'structured' and parts['status'] == 'partial'
    assert parts['openable']
    assert (parts['target'], parts['sub']) == ('models', 'files')
    assert parts['targets'] == [{'id': 'models', 'label': 'Models'}]
    assert parts['controls'] == 'Assets: whole-file replacement with previews'
    assert 'also preview in their Items detail' in parts['notes']


def test_other_asset_rows_keep_the_generic_wording(tmp_path):
    rows = data_map.payload(make_store(tmp_path, ('parts', 'chr', 'sound')))['rows']
    others = [row for row in rows if row['id'].startswith('assets:') and row['id'] != 'assets:parts']
    assert len(others) == 2
    for row in others:
        assert row['controls'] == 'Assets: whole-file replacement with previews'
        assert 'Sounds replace without a preview' in row['notes']


def test_parts_row_absent_without_the_folder(tmp_path):
    rows = data_map.payload(make_store(tmp_path, ('chr',)))['rows']
    assert not [row for row in rows if row['id'] == 'assets:parts']
