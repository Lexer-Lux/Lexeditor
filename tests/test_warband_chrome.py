"""Warband chrome: readable brand, readable tabs, left thumbnail (W1/W2/W3)."""
from pathlib import Path

from test_shared_ui_feedback import page, framework

ROOT = Path(__file__).resolve().parents[1]

RATIO_FN = '''(fg, bg) => {
  const lum = c => {
    const m = c.match(/[\\d.]+/g).map(Number).slice(0, 3).map(v => {
      v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4);
    });
    return .2126 * m[0] + .7152 * m[1] + .0722 * m[2];
  };
  const [x, y] = [lum(fg), lum(bg)].sort((p, q) => q - p);
  return (x + .05) / (y + .05);
}'''


def mount_warband(page):
    page.add_style_tag(path=str(ROOT / 'plugins/warband/editor.css'))
    page.evaluate('''() => {
      document.body.insertAdjacentHTML('afterbegin', '<div id="lexeditor-shell"></div>');
      window.pywebview = {api: {
        loading_quote: async () => ({quote: 'Hi'}),
        lexeditor_settings: async () => ({loadingTransitionMinimumSeconds: 0}),
        default_views: async () => ({views: {}}),
      }};
    }''')
    framework(page)
    page.evaluate('''() => LexeditorUI.mountShell({host: '#lexeditor-shell',
      plugin: {id: 'warband', name: 'Warband'},
      tabs: [{id: 'troops', label: 'Troops'}, {id: 'items', label: 'Items'}],
      activeTab: () => 'troops', navigate: () => {}})''')
    page.evaluate('LexeditorUI.finishPluginLoading()')
    page.wait_for_selector('.lex-shell-header nav button')


def test_brand_readable_on_command_row(page):
    mount_warband(page)
    ratio = page.evaluate(f'''() => {{
      const brand = document.querySelector('.lex-brand-button h1');
      const row = document.querySelector('.lex-shell-command-row');
      return ({RATIO_FN})(getComputedStyle(brand).color, getComputedStyle(row).backgroundColor);
    }}''')
    assert ratio >= 4.5, ratio


def test_tab_text_readable_in_every_state(page):
    mount_warband(page)
    ratios = page.evaluate(f'''() => {{
      const tabs = [...document.querySelectorAll('.lex-shell-header nav button')];
      const ratio = {RATIO_FN};
      return tabs.map(t => ratio(getComputedStyle(t).color, getComputedStyle(t).backgroundColor));
    }}''')
    assert len(ratios) == 2, ratios
    assert all(r >= 4.5 for r in ratios), ratios
    rest = page.locator('.lex-shell-header nav button:not(.active)')
    rest.hover()
    page.wait_for_timeout(300)
    hovered = page.evaluate(f'''() => {{
      const t = document.querySelector('.lex-shell-header nav button:not(.active)');
      return ({RATIO_FN})(getComputedStyle(t).color, getComputedStyle(t).backgroundColor);
    }}''')
    assert hovered >= 4.5, hovered


def test_preview_thumbnail_sits_left(page):
    mount_warband(page)
    page.evaluate('''() => {
      const U = LexeditorUI;
      const icon = () => U.iconSlot({content: U.element('div', {style: 'width:60px;height:60px'})});
      document.querySelector('main').append(U.detailPanel({icon: icon(), title: 'A',
        meta: 'sub', modelPreview: {label: 'model', content: () => U.element('div', {}, 'p')}}));
      document.querySelector('main').append(U.detailPanel({icon: icon(), title: 'B', meta: 'sub'}));
    }''')
    page.wait_for_selector('.lex-model-preview-heading .lex-detail-panel-icon')
    sides = page.evaluate('''() => [...document.querySelectorAll('.lex-detail-panel')].map(p => {
      const h = p.querySelector('.lex-detail-panel-heading');
      const icon = h.querySelector('.lex-detail-panel-icon').getBoundingClientRect();
      const idn = h.querySelector('.lex-detail-panel-identity').getBoundingClientRect();
      return {iconLeft: icon.left, identityLeft: idn.left};
    })''')
    assert len(sides) == 2, sides
    for row in sides:
        assert row['iconLeft'] < row['identityLeft'], sides
