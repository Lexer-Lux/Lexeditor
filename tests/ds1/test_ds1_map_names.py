"""Maps list bare area names; the directory splits reference names into owner/item/map."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.map_store import (
    MapStore, describe_directory_name, describe_treasure_name, strip_owner_suffix)
from plugins.ds1.msb import MAP_DIR
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
    (game / MAP_DIR).mkdir(parents=True)
    (game / MAP_DIR / 'm10_01_00_00.msb').touch()
    (game / MAP_DIR / 'm10_02_00_00.msb').touch()
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


def test_display_name_shows_only_the_map_name(tmp_path):
    maps = make_maps(tmp_path)
    assert maps.display_name('m10_01_00_00.msb') == 'Undead Burg'
    assert maps.display_name('m10_02_00_00.msb') == 'Firelink Shrine'


def test_display_name_skips_empty_areas(tmp_path):
    maps = make_maps(tmp_path)
    assert maps.display_name('m10_00_00_00.msb') == 'm10_00_00_00.msb'


def test_display_name_falls_back_without_text_or_match(tmp_path):
    maps = make_maps(tmp_path, places=False)
    assert maps.display_name('m10_01_00_00.msb') == 'm10_01_00_00.msb'
    maps = make_maps(tmp_path / 'named')
    assert maps.display_name('test.msb') == 'test.msb'
    assert maps.display_name('m99_00_00_00.msb') == 'Test map m99_00_00_00'


def test_split_strips_the_bracket_area_from_the_owner():
    displays = {'new londo ruins': 'New Londo Ruins'}
    assert describe_directory_name('[Hollow - New Londo Ruins] None', displays) == (
        'Hollow', 'None', 'New Londo Ruins')


def test_split_keeps_owners_and_conditions_without_a_place():
    assert describe_directory_name('[Andre of Astora] Crest of Artorias', {}) == (
        'Andre of Astora', 'Crest of Artorias', '')
    assert describe_directory_name('[Ingward - Have Lordvessel] Key to the Seal', {}) == (
        'Ingward - Have Lordvessel', 'Key to the Seal', '')
    assert describe_directory_name('[Unknown] Purging Stone', {}) == (
        'Unknown', 'Purging Stone', '')
    assert describe_directory_name('Humanity', {}) == ('', 'Humanity', '')


def test_split_gives_place_only_brackets_no_owner():
    displays = {'anor londo': 'Anor Londo', "sen's fortress": "Sen's Fortress",
                'royal garden': None}
    assert describe_directory_name('[Anor Londo] Great Magic Weapon', displays) == (
        '', 'Great Magic Weapon', 'Anor Londo')
    assert describe_directory_name("[Sen's Fortress)] Balder Helm", displays) == (
        '', 'Balder Helm', "Sen's Fortress")
    assert describe_directory_name('[Royal Garden] Soul of a Lost Undead', displays) == (
        '', 'Soul of a Lost Undead', 'Royal Garden')


def test_who_strips_map_suffixes_but_keeps_distinct_owners():
    displays = {'blighttown': 'Blighttown', 'undead burg': 'Undead Burg'}
    assert strip_owner_suffix('Griggs of Vinheim (Hollow) - Blighttown', displays) == (
        'Griggs of Vinheim (Hollow)')
    assert strip_owner_suffix('Forest Hunter - Bandit', displays) == 'Forest Hunter - Bandit'
    assert strip_owner_suffix('Vagrant (Aggressive) - 1', displays) == 'Vagrant (Aggressive) - 1'
    assert strip_owner_suffix('Drake (Flying)', displays) == 'Drake (Flying)'


def test_treasure_splits_its_map_stem():
    stems = {('10', '01'): 'Undead Burg', ('12', '01'): 'Sanctuary Garden'}
    assert describe_treasure_name('m10_01_ church gate lever', stems) == (
        'church gate lever', 'Undead Burg')
    assert describe_treasure_name('??m12_01_ Door imprisoning Go', stems) == (
        'Door imprisoning Go', 'Sanctuary Garden')
    assert describe_treasure_name('Treasure Chest', stems) == ('Treasure Chest', '')


def test_place_display_names_resolve_areas_and_aliases(tmp_path):
    maps = make_maps(tmp_path)
    displays = maps.place_display_names()
    assert displays['undead burg'] == 'Undead Burg'
    assert displays['undead parish'] == 'Undead Burg'
    assert displays['firelink'] == 'Firelink Shrine'
    assert displays['royal garden'] is None


def test_describe_drop_prefers_links_over_the_bracket_place(tmp_path):
    maps = make_maps(tmp_path)
    displays = maps.place_display_names()
    assert maps.describe_drop('[Hollow - Undead Parish] None', [], displays) == {
        'owner': 'Hollow', 'item': 'None', 'mapNames': ['Undead Burg']}
    assert maps.describe_drop('[Hollow - Undead Parish] None', ['m10_02_00_00.msb'],
                              displays) == {
        'owner': 'Hollow', 'item': 'None', 'mapNames': ['Firelink Shrine']}


def test_describe_treasure_falls_back_to_the_whole_name(tmp_path):
    maps = make_maps(tmp_path)
    assert maps.describe_treasure('m10_01_ church gate lever') == {
        'owner': '', 'item': 'church gate lever', 'mapNames': ['Undead Burg']}
    assert maps.describe_treasure('Treasure Chest') == {
        'owner': '', 'item': 'Treasure Chest', 'mapNames': []}
