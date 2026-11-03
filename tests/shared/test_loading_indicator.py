"""Source-level contract for the shared loading indicators."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / 'ui' / 'framework.js'
CSS = ROOT / 'ui' / 'framework.css'
DS1 = ROOT / 'plugins' / 'ds1'


def ui():
    return UI.read_text(encoding='utf-8', errors='replace')


def css():
    return CSS.read_text(encoding='utf-8', errors='replace')


def ds1(name):
    return (DS1 / name).read_text(encoding='utf-8', errors='replace')


def test_loading_status_exported():
    source = ui()
    assert 'const loadingStatus = (label' in source
    assert 'loadingPanel, loadingStatus, badge' in source
    assert 'lex-loading-status' in source
    assert 'lex-plugin-loading-pulse' in source


def test_loading_status_css():
    sheet = css().replace(' ', '')
    assert '.lex-loading-status{display:inline-flex' in sheet
    assert '.lex-loading-status>.lex-plugin-loading-pulse' in sheet


def test_ds1_status_bars_use_shared_loading():
    for name in ('editor.js', 'viewport.js', 'anim.js'):
        source = ds1(name)
        assert 'textContent = `Loading' not in source, name
        assert 'textContent = "Loading' not in source, name
    assert ds1('editor.js').count('LexeditorUI.loadingStatus(') == 3
    assert ds1('viewport.js').count('LexeditorUI.loadingStatus(') == 2
    assert ds1('anim.js').count('LexeditorUI.loadingStatus(') == 1
