"""Divider gizmos meet the cursor instead of waiting at the middle.

Hovering anywhere along a divider strip summons its Barrels/Columns gizmos
centered on the cursor's height, clamped so they never hang past the
strip's ends. They used to sit at the divider's vertical middle, so
summoning them meant hunting the one spot they waited at.
"""
from test_shared_ui_feedback import framework, page

BUILD = """() => {
  const U = LexeditorUI;
  localStorage.clear();
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;height:760px;';
  const gizmo = U.el('div', {class: 'lex-barrel-control'},
    U.el('span', {class: 'lex-barrel-label'}, 'COLUMNS'));
  main.replaceChildren(U.panelLayout(
    [U.el('div', {style: 'min-width:0;min-height:0;background:#111'}),
     U.el('div', {style: 'min-width:0;min-height:0;background:#222'})],
    'gizmo-y-check', {dividerAccessories: [[gizmo]]}));
}"""

STATE = """() => {
  const strip = document.querySelector('.lex-panel-layout-divider');
  const gizmo = strip.querySelector(':scope > .lex-barrel-control');
  const sbox = strip.getBoundingClientRect();
  const gbox = gizmo.getBoundingClientRect();
  return {
    top: parseFloat(gizmo.style.top) || 0,
    center: gbox.top + gbox.height / 2 - sbox.top,
    stripH: sbox.height,
    half: gbox.height / 2,
  };
}"""


def test_gizmo_follows_cursor_height_clamped_to_strip(page):
    framework(page)
    page.evaluate(BUILD)
    page.wait_for_timeout(300)
    box = page.locator('.lex-panel-layout-divider').bounding_box()
    assert box['height'] > 200, box
    cx = box['x'] + box['width'] / 2
    page.mouse.move(cx, box['y'] + box['height'] * 0.3)
    page.wait_for_timeout(200)
    mid = page.evaluate(STATE)
    assert abs(mid['center'] - box['height'] * 0.3) <= 2, mid
    page.mouse.move(cx, box['y'] + 2)
    page.wait_for_timeout(200)
    top = page.evaluate(STATE)
    assert top['center'] >= top['half'] - 1, top
    assert top['center'] < box['height'] * 0.3, (mid, top)
    page.mouse.move(cx, box['y'] + box['height'] - 2)
    page.wait_for_timeout(200)
    bottom = page.evaluate(STATE)
    assert bottom['center'] <= bottom['stripH'] - bottom['half'] + 1, bottom
    assert bottom['center'] > box['height'] * 0.7, (mid, bottom)
