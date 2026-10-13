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
    for column in ('Parts', 'Models', 'Collision', 'Navigation'):
        assert f'label:"{column}"' in source
    rows = server()
    assert "'collision'" in rows
    assert "'navigation'" in rows
    assert "'models'" in rows


def test_selection_avoids_remount():
    source = editor()
    assert 'function selectPlacement(placementKey,fromCanvas){' in source
    assert 'function refreshMapSide(){' in source
    body = source[source.index('async function selectPlacement'):source.index('function refreshMapSide')]
    assert 'refreshMapSide();' in body
    assert 'render();' not in body.replace('renderMaps();', '')
