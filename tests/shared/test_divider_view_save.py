"""Divider positions are automatic: nothing drags and nothing is saved.

A list-detail split always comes from its configured shares clamped to
measured minimums. Dragging and right-click change nothing; no divider
key is ever stored (stale keys from older versions are ignored, never
migrated). Holding a tab still ships the remaining view settings, and
says so when there are none.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401  (fixture)
from test_tab_rename import mount_shell

BUILD = """() => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  main.style.cssText = 'display:block;width:1000px;height:600px';
  window.drawSplit = (splitKey) => {
    main.replaceChildren(U.listDetail(
      U.el('div', {style: 'background:#333;height:100%'}, 'master'),
      U.el('div', {style: 'background:#555;height:100%'}, 'detail'),
      'test-layout',
      {splitKey, defaultSplit: 30, minLeft: 100, minRight: 100}));
  };
  drawSplit('plain');
}"""

KEYS = """() => Array.from({length: localStorage.length},
  (_, index) => localStorage.key(index))"""

TEMPLATE = """() => document.querySelector('.lex-panel-layout').style
  .getPropertyValue('--lex-panel-layout-template')"""


def mount(page):
    framework(page)
    mount_shell(page, developer=True)
    page.evaluate(BUILD)
    page.wait_for_timeout(300)


def master_width(page):
    return page.locator('.lex-panel-layout-pane').first.bounding_box()['width']


def drag_divider(page, delta=200):
    divider = page.locator('.lex-list-detail-divider')
    box = divider.bounding_box()
    x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + delta, y, steps=5)
    page.mouse.up()
    page.wait_for_timeout(150)


def hold_tab(page):
    button = page.locator('nav button[data-tab="items"]')
    box = button.bounding_box()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.mouse.down(button='right')
    page.wait_for_timeout(900)
    page.mouse.up(button='right')
    page.wait_for_timeout(200)


def test_split_follows_configured_shares(page):
    mount(page)
    assert 280 <= master_width(page) <= 315, master_width(page)


def test_divider_is_not_draggable(page):
    mount(page)
    strip = page.locator('.lex-list-detail-divider')
    assert strip.get_attribute('role') is None
    assert strip.get_attribute('tabindex') is None
    assert strip.evaluate('node => getComputedStyle(node).cursor') == 'default'
    before = (page.evaluate(TEMPLATE), master_width(page))
    drag_divider(page)
    assert page.evaluate(
        'document.body.classList.contains("lex-panel-layout-dragging")') is False
    assert (page.evaluate(TEMPLATE), master_width(page)) == before
    assert [key for key in page.evaluate(KEYS) if 'list-detail' in key] == []


def test_divider_ignores_right_click(page):
    mount(page)
    before = (page.evaluate(TEMPLATE), master_width(page))
    box = page.locator('.lex-list-detail-divider').bounding_box()
    page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2,
                     button='right')
    page.wait_for_timeout(150)
    assert (page.evaluate(TEMPLATE), master_width(page)) == before
    assert [key for key in page.evaluate(KEYS) if 'list-detail' in key] == []


def test_stale_divider_keys_are_ignored(page):
    framework(page)
    mount_shell(page, developer=True)
    page.evaluate("localStorage.setItem('lexeditor:list-detail:plain', '55')")
    page.evaluate(BUILD)
    page.wait_for_timeout(300)
    assert 280 <= master_width(page) <= 315, master_width(page)
    keys = page.evaluate(KEYS)
    assert 'lexeditor:list-detail:plain' in keys, keys
    assert [key for key in keys if 'fixture-items:list-detail' in key] == []


def test_holding_the_tab_ships_remaining_settings(page):
    mount(page)
    page.evaluate("localStorage.setItem('lexeditor:fixture-items:barrels:test', '2')")
    hold_tab(page)
    calls = page.evaluate('window.savedCalls')
    assert len(calls) == 1, calls
    _plugin, _tab, preferences = calls[0]
    assert 'lexeditor:fixture-items:barrels:test' in preferences, preferences
    assert not [key for key in preferences if 'list-detail' in key], preferences


def test_holding_a_tab_with_no_settings_says_so(page):
    mount(page)
    assert [key for key in page.evaluate(KEYS)
            if 'fixture-items' in key] == []
    hold_tab(page)
    assert page.evaluate('window.savedCalls') == []
    page.locator('.lex-toast-stack',
                 has_text='no view settings to save').wait_for()
