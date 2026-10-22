"""Source-level contract for the DS1 Maps screen layout."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDITOR = ROOT / 'plugins' / 'ds1' / 'editor.js'
SERVER = ROOT / 'plugins' / 'ds1' / 'server.py'


def editor():
    return EDITOR.read_text(encoding='utf-8', errors='replace')


def server():
    return SERVER.read_text(encoding='utf-8', errors='replace')


def test_maps_tab_replaces_areas():
    source = editor()
    assert '{id:"maps",label:"Maps"' in source
    assert 'state.mapTabs' not in source
    assert 'result.mapTabs' not in source
    assert 'renderViewport' not in source
    assert 'picker,collide,duplicate,remove,add,copy,paste,rotate' not in source
    assert 'mapTabs' not in server()


def test_maps_layout_uses_shared_components():
    source = editor()
    assert 'function renderMaps(){' in source
    assert 'function loadMaps(){' in source
    assert 'function mapsStrip(){' in source
    assert 'LexeditorUI.tabStrip(' in source
    assert 'LexeditorUI.hoverActions(wrap' in source
    assert 'LexeditorUI.bottomSearch(' in source
    assert 'LexeditorUI.pager(' in source
    assert 'data-maps-side' in source


def test_maps_table_shows_counts():
    source = editor()
    for column in ('NPCs', 'Drops', 'Enemies'):
        assert f'label:"{column}"' in source
    pane = source[source.index('function mapsListPane(){'):source.index('function placementsPane(){')]
    for gone in ('Parts', 'Models', 'Collision', 'Navigation'):
        assert f'label:"{gone}"' not in pane
    rows = server()
    assert "'npcs'" in rows
    assert "'drops'" in rows
    assert "'enemies'" in rows


def test_selection_avoids_remount():
    source = editor()
    assert 'function selectPlacement(placementKey,fromCanvas){' in source
    assert 'function refreshMapSide(){' in source
    body = source[source.index('async function selectPlacement'):source.index('function refreshMapSide')]
    assert 'refreshMapSide();' in body
    assert 'render();' not in body.replace('renderMaps();', '')


def test_placements_list_hides_its_map_column_on_one_map():
    source = editor()
    pane = source[source.index('function placementsPane(){'):source.index('function animCharMatches(){')]
    assert 'label:"Map"' in pane
    assert 'new Set(here.map(row=>row.table)).size>1' in pane
    assert 'dirRowMap(row)' in pane
    assert 'Show ${row.name} in the map viewport' in pane


def test_placements_search_still_matches_the_map_name():
    source = editor()
    haystack = source[source.index('const haystack=row=>{'):source.index('const filtered=state.rows.filter')]
    assert 'mapNames' in haystack
