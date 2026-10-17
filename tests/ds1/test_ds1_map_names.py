"""Maps list human-readable area names from the merged place table."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.map_store import MapStore
from plugins.ds1.store import ItemStore, MARKER, RELATIVE

PLACES = {1010: 'Undead Burg', 1011: 'Undead Parish', 1020: 'Firelink Shrine'}


def make_maps(root, places=True):
    game, mod = root / 'game', root / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    if places:
        blob = make_text_archive(extra={'Place_name_.fmg': dict(PLACES)})
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(blob)
    mod.mkdir()
    (mod / MARKER).touch()
    store = ItemStore(game, mod, False)
    store.load()
    return MapStore(game, mod, False, store)


def test_place_name_lookup():
    doc = texts.TextDocument(make_text_archive(extra={'Place_name_.fmg': dict(PLACES)}))
    assert doc.place_name(1010) == 'Undead Burg'
    assert doc.place_name(1011) == 'Undead Parish'
    assert doc.place_name(9999) is None


def test_display_name_resolves_the_primary_area(tmp_path):
    maps = make_maps(tmp_path)
    assert maps.display_name('m10_01_00_00.msb') == 'Undead Burg (m10_01_00_00.msb)'
    assert maps.display_name('m10_02_00_00.msb') == 'Firelink Shrine (m10_02_00_00.msb)'


def test_display_name_skips_empty_areas(tmp_path):
    maps = make_maps(tmp_path)
    assert maps.display_name('m10_00_00_00.msb') == 'm10_00_00_00.msb'


def test_display_name_falls_back_without_text_or_match(tmp_path):
    maps = make_maps(tmp_path, places=False)
    assert maps.display_name('m10_01_00_00.msb') == 'm10_01_00_00.msb'
    maps = make_maps(tmp_path / 'named')
    assert maps.display_name('test.msb') == 'test.msb'
    assert maps.display_name('m99_00_00_00.msb') == 'Test map (m99_00_00_00.msb)'
