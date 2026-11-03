"""Data Map opens the Maps and Animations tabs from their folders."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
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


def test_area_folders_absent_leaves_current_rows(tmp_path):
    rows = data_map.payload(make_store(tmp_path))['rows']
    assert not [row for row in rows if row['id'].startswith('area:')]


def test_maps_open_maps_while_characters_open_animations(tmp_path):
    rows = data_map.payload(make_store(tmp_path, ('map', 'chr')))['rows']
    areas = {row['id']: row for row in rows if row['id'].startswith('area:')}
    assert set(areas) == {'area:maps', 'area:characters'}
    maps = areas['area:maps']
    assert maps['coverage'] == 'structured' and maps['status'] == 'partial' and maps['openable']
    assert (maps['target'], maps['sub']) == ('maps', 'placements')
    assert maps['targets'] == [{'id': 'maps', 'label': 'Maps'}]
    assert 'left untouched' in maps['notes']
    characters = areas['area:characters']
    assert characters['coverage'] == 'structured' and characters['status'] == 'partial'
    assert characters['openable']
    assert (characters['target'], characters['sub']) == ('animations', 'animations')
    assert characters['targets'] == [{'id': 'animations', 'label': 'Animations'}]
    assert 'stay untouched' in characters['notes']
