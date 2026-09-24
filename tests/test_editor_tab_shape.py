"""G5: editor tabs are tab-shaped at rest, not only on hover."""
from pathlib import Path

from test_shared_ui_feedback import page, framework

ROOT = Path(__file__).resolve().parents[1]

STUB = '''() => {
  document.body.insertAdjacentHTML('afterbegin', '<div id="lexeditor-shell"></div>');
  window.pywebview = {api: {
    loading_quote: async () => ({quote: 'Hi'}),
    lexeditor_settings: async () => ({loadingTransitionMinimumSeconds: 0}),
    default_views: async () => ({views: {}}),
  }};
}'''

MOUNT = '''() => LexeditorUI.mountShell({host: '#lexeditor-shell',
  plugin: {id: 'fixture', name: 'Fixture'},
  tabs: [{id: 'a', label: 'Alpha'}, {id: 'b', label: 'Beta'}, {id: 'c', label: 'Gamma'}],
  activeTab: () => 'a', navigate: () => {}})'''


def mount(page):
    page.evaluate(STUB)
    framework(page)
    page.evaluate(MOUNT)


def test_tabs_tab_shaped_at_rest(page):
    mount(page)
    page.wait_for_selector('.lex-shell-header nav button')
    page.wait_for_timeout(300)
    radii = page.locator('.lex-shell-header nav button').evaluate_all(
        'ns => ns.map(n => getComputedStyle(n).borderTopLeftRadius)')
    assert len(radii) == 3, radii
    assert all(r == '8px' for r in radii), radii


def test_square_theme_stays_square(page):
    mount(page)
    page.add_style_tag(path=str(ROOT / 'plugins/ff8/editor.css'))
    page.wait_for_selector('.lex-shell-header nav button')
    page.wait_for_timeout(300)
    radii = page.locator('.lex-shell-header nav button').evaluate_all(
        'ns => ns.map(n => getComputedStyle(n).borderTopLeftRadius)')
    assert all(r == '0px' for r in radii), radii
