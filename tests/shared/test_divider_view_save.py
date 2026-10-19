"""Divider positions ship with their tab's default view.

Dragging a list-detail divider stores under a key carrying the tab
token, so holding the tab ships the split with every other view
setting; keys that already name their tab keep working untouched,
and pre-token keys migrate on first read. Holding a tab with no view
settings at all says so instead of failing.
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


def mount(page):
    framework(page)
    mount_shell(page, developer=True)
    page.evaluate(BUILD)
    page.wait_for_timeout(300)


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


def test_divider_drag_stores_under_a_tokenized_key(page):
    mount(page)
    drag_divider(page)
    keys = page.evaluate(KEYS)
    assert 'lexeditor:fixture-items:list-detail:plain' in keys, keys
    assert 'lexeditor:list-detail:plain' not in keys, keys
    value = page.evaluate(
        "localStorage.getItem('lexeditor:fixture-items:list-detail:plain')")
    assert 40 <= float(value) <= 60, value


def test_pre_token_key_migrates_on_read(page):
    framework(page)
    mount_shell(page, developer=True)
    page.evaluate("localStorage.setItem('lexeditor:list-detail:plain', '55')")
    page.evaluate(BUILD)
    page.wait_for_timeout(300)
    master = page.locator('.lex-panel-layout-pane').first.bounding_box()
    assert 520 <= master['width'] <= 580, master
    drag_divider(page, delta=-100)
    keys = page.evaluate(KEYS)
    assert 'lexeditor:fixture-items:list-detail:plain' in keys, keys


def test_key_with_a_token_is_left_alone(page):
    mount(page)
    page.evaluate("drawSplit('fixture-items-sub')")
    page.wait_for_timeout(200)
    drag_divider(page)
    keys = [key for key in page.evaluate(KEYS) if 'list-detail' in key]
    assert keys == ['lexeditor:list-detail:fixture-items-sub'], keys


def test_holding_the_tab_ships_the_divider(page):
    mount(page)
    drag_divider(page)
    hold_tab(page)
    calls = page.evaluate('window.savedCalls')
    assert len(calls) == 1, calls
    _plugin, _tab, preferences = calls[0]
    assert 'lexeditor:fixture-items:list-detail:plain' in preferences, preferences


def test_holding_a_tab_with_no_settings_says_so(page):
    mount(page)
    assert [key for key in page.evaluate(KEYS)
            if 'fixture-items' in key] == []
    hold_tab(page)
    assert page.evaluate('window.savedCalls') == []
    page.locator('.lex-toast-stack',
                 has_text='no view settings to save').wait_for()
