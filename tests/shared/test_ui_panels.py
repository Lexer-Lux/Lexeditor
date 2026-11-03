"""Source-level contract for the shared hover, collapsible and detail-tab UI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / 'ui' / 'framework.js'
CSS = ROOT / 'ui' / 'framework.css'


def ui():
    return UI.read_text(encoding='utf-8', errors='replace')


def css():
    return CSS.read_text(encoding='utf-8', errors='replace')


def test_hover_actions_exported():
    source = ui()
    assert 'hoverActions, collapsiblePanel, promptText' in source
    assert 'const hoverActions = (host, options' in source
    assert 'lex-hover-actions-host' in source


def test_hover_css_states():
    sheet = css().replace(' ', '')
    assert '.lex-hover-actions-host:hover>.lex-hover-actions' in sheet
    assert '.lex-hover-actions-host>.lex-hover-actions:hover' in sheet
    assert 'opacity:.45' in sheet
    assert '.lex-hover-actions-inline' in sheet


def test_table_add_uses_hover():
    assert 'hoverActions(masterNode' in ui()


def test_collapsible_panel():
    source = ui()
    assert 'const collapsiblePanel = (options' in source
    assert 'const tabStrip = (options' in source
    assert 'lex-collapsible-collapsed' in source
    assert 'lex-collapsible-handle' in css()


def test_prompt_text():
    source = ui()
    assert 'const promptText = (options' in source
    assert 'lex-prompt-dialog' in source
    assert '.lex-prompt-dialog' in css()


def test_detail_tabs_keep_column_flow():
    source = ui()
    assert 'detailBody(bodyClass, options.body, options.paginate)' in source
    assert '.detailtabs' in source
    assert 'box._detailTabs' in source
    assert 'bodyBox._detailTabs?.addTab()' in source
    assert '.lex-detail-tabpane' in css()
    assert 'text/lex-detail-node' in source
    # A body of sections still flows into columns (the COLUMNS control sets
    # how many); tabs take over only where the developer gave the shape its
    # own, and then the pager's columns go.
    assert 'hasTabs' in source
    assert 'paginateSettings(box, flow)' in source
