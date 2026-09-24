"""The shell header's control groups never overlap, at any window size or scale.

The undo/save/play/redo group was absolutely centred on the row, outside the
grid, so nothing reserved room for it: in a 900x620 window the zoom slider
and settings slid under the redo button. The UI scale is the webview zoom,
so 150% in a 900x620 window is a 600x413 CSS viewport at 1.5x density.
"""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
THEMES = sorted(p.parent.name for p in (ROOT / "plugins").glob("*/editor.css"))
SIZES = {
    "desktop": (1440, 900, 1),
    "small": (900, 620, 1),
    "small-150": (600, 413, 1.5),
}

MEASURE = '''() => {
  const row = document.querySelector('.lex-shell-command-row');
  const groups = ['.lex-brand-slot', '.lex-shell-left-actions', '.lex-shell-center-actions', '.lex-shell-right-actions',
                  '.lex-developer-actions', '.lex-window-actions']
    .flatMap(sel => [...row.querySelectorAll(sel)])
    .filter(n => n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden');
  // The mod picker's own box counts too: collapsed, it once drew its empty
  // frame under the undo button while every button still passed.
  const controls = groups.flatMap(g => [...g.querySelectorAll('button:not(.lex-project-menu button), label, input')])
    .filter(n => n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden')
    .filter(n => !n.closest('label') || n.tagName === 'LABEL');
  const box = n => n.getBoundingClientRect();
  const overlaps = [];
  for (let i = 0; i < controls.length; i++) for (let j = i + 1; j < controls.length; j++) {
    const a = box(controls[i]), b = box(controls[j]);
    if (controls[i].contains(controls[j]) || controls[j].contains(controls[i])) continue;
    const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (w > 1 && h > 1) overlaps.push([controls[i].title || controls[i].className, controls[j].title || controls[j].className]);
  }
  const r = box(row);
  const outside = controls.filter(n => box(n).right > r.right + 1 || box(n).left < r.left - 1)
    .map(n => n.title || n.className);
  return {overlaps, outside};
}'''


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as play:
        instance = play.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("theme", THEMES)
def test_header_controls_do_not_overlap(browser, theme, size):
    width, height, scale = SIZES[size]
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=scale)
    try:
        page.route("http://fixture/**", lambda r: r.fulfill(
            body='<body><div id="lexeditor-shell"></div><main id="main"></main></body>',
            content_type="text/html"))
        page.goto("http://fixture/")
        page.add_style_tag(path=str(ROOT / "ui/framework.css"))
        page.add_style_tag(path=str(ROOT / f"plugins/{theme}/editor.css"))
        page.evaluate('''() => { window.pywebview = {api: new Proxy({
            loading_quote: async () => ({quote: ''}),
            lexeditor_settings: async () => ({loadingTransitionMinimumSeconds: 0}),
            default_views: async () => ({views: {}}),
          }, {get: (t, k) => t[k] || (async () => ({}))})}; }''')
        page.add_script_tag(path=str(ROOT / "ui/framework.js"))
        page.evaluate('''() => LexeditorUI.mountShell({host: '#lexeditor-shell',
          plugin: {id: 'check', name: 'Check'},
          tabs: [{id: 'a', label: 'Items'}, {id: 'b', label: 'Magic'}],
          activeTab: () => 'a', navigate: () => {}})''')
        page.evaluate("LexeditorUI.finishPluginLoading()")
        page.wait_for_selector(".lex-shell-command-row .lex-ui-scale")
        page.wait_for_timeout(150)
        result = page.evaluate(MEASURE)
        assert result["overlaps"] == [], result
        assert result["outside"] == [], result
    finally:
        page.close()
