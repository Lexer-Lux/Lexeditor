"""Right-click resets subtab views; tabs without saved views are badged.

Hold-to-save clears the badge it earned: the packaged defaults cache
is dropped and every dot is re-marked from the fresh store."""
from test_shared_ui_feedback import page, framework

MOUNT = '''() => {
  const U = LexeditorUI;
  document.body.prepend(U.element('div', {id: 'lexeditor-shell'}));
  window.__navigate = [];
  U.mountShell({host: '#lexeditor-shell', plugin: {id: 'fixture', name: 'Fixture'},
    tabs: [{id: 'a', label: 'A'}, {id: 'b', label: 'B'}],
    activeTab: () => 'a', navigate: tab => window.__navigate.push(tab)});
}'''

SUBTABS = '''() => {
  const U = LexeditorUI;
  window.__changed = [];
  localStorage.setItem('lexeditor:list-detail:fixture-a-weapons', '33');
  localStorage.setItem('lexeditor:list-detail:fixture-a-armor', '44');
  document.querySelector('main').append(U.subtabBar({tabs: [
    {id: 'weapons', label: 'Weapons'}, {id: 'armor', label: 'Armor'}],
    active: 'weapons', label: 'Kinds', change: id => window.__changed.push(id)}));
}'''


def test_subtab_right_click_resets_only_that_subtab(page):
    framework(page)
    page.evaluate(MOUNT)
    page.evaluate(SUBTABS)
    page.locator('[data-subtab="weapons"]').dispatch_event('contextmenu')
    page.wait_for_function("window.__changed.length > 0", timeout=8000)
    assert page.evaluate("window.__changed") == ['weapons']
    assert page.evaluate("localStorage.getItem('lexeditor:list-detail:fixture-a-weapons')") is None
    assert page.evaluate("localStorage.getItem('lexeditor:list-detail:fixture-a-armor')") == '44'


def test_tabs_without_saved_views_are_badged(page):
    framework(page)
    page.evaluate(MOUNT)
    page.evaluate(SUBTABS)
    page.wait_for_selector('.lex-shell-header nav button .lex-tab-no-default', timeout=8000)
    assert page.locator('.lex-shell-header nav button .lex-tab-no-default').count() >= 2
    page.wait_for_selector('[data-subtab="weapons"] .lex-tab-no-default', timeout=8000)


def hold_right(locator, page):
    box = locator.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down(button="right")
    page.wait_for_timeout(1100)
    page.mouse.up(button="right")


def enable_saving(page):
    page.evaluate("""() => {
      window.__views = {views: {}};
      window.pywebview = {api: {
        default_views: async () => window.__views,
        save_default_view: async (plugin, tab, prefs) => {
          window.__views.views[tab] = {...(window.__views.views[tab] || {}), ...prefs};
          return {saved: true};
        }}};
    }""")


def enable_developer_mode(page):
    page.evaluate("window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',"
                  " {detail: {developerMode: true}}))")


def test_hold_to_save_clears_the_tab_badge(page):
    framework(page)
    enable_saving(page)
    page.evaluate(MOUNT)
    page.evaluate(SUBTABS)
    page.wait_for_selector('[data-tab="a"] .lex-tab-no-default', timeout=8000)
    enable_developer_mode(page)
    hold_right(page.locator('[data-tab="a"]'), page)
    page.wait_for_function(
        "document.querySelector('[data-tab=a] .lex-tab-no-default') === null",
        timeout=8000)
    assert page.locator('[data-tab="b"] .lex-tab-no-default').count() == 1


def test_hold_to_save_clears_the_subtab_badge(page):
    framework(page)
    enable_saving(page)
    page.evaluate(MOUNT)
    page.evaluate(SUBTABS)
    page.wait_for_selector('[data-subtab="weapons"] .lex-tab-no-default', timeout=8000)
    enable_developer_mode(page)
    hold_right(page.locator('[data-subtab="weapons"]'), page)
    page.wait_for_function(
        "document.querySelector('[data-subtab=weapons] .lex-tab-no-default') === null",
        timeout=8000)


def test_tabs_with_saved_views_have_no_badge(page):
    framework(page)
    page.evaluate("""() => {
      window.pywebview = {api: {default_views: async () => ({views: {
        a: {'lexeditor:list-detail:fixture-a-weapons': '33'}}})}};
    }""")
    page.evaluate(MOUNT)
    page.wait_for_selector('[data-tab="b"] .lex-tab-no-default', timeout=8000)
    assert page.locator('[data-tab="a"] .lex-tab-no-default').count() == 0
    assert page.locator('[data-tab="b"] .lex-tab-no-default').count() == 1
