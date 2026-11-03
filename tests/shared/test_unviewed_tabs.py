"""Shell tabs the reader never opened carry a dot until first viewed.

The viewed set persists per plugin, seeded with the tabs present on
first mount so a fresh install shows no dots; a tab that appears later
(a new page) is dotted until the reader opens it.
"""
from test_shared_ui_feedback import page, framework  # noqa: F401

STUB = '''() => {
  document.body.insertAdjacentHTML('afterbegin', '<div id="lexeditor-shell"></div><main></main>');
  window.pywebview = {api: {
    loading_quote: async () => ({quote: 'Hi'}),
    lexeditor_settings: async () => ({loadingTransitionMinimumSeconds: 0}),
    default_views: async () => ({views: {}}),
  }};
}'''

MOUNT = '''(tabs) => {
  window.__tab = 'a';
  // The loading screen swallows input until the plugin finishes; the
  // fixture plugin is already up, so lift the guard directly.
  document.documentElement.classList.remove("lex-loading-live");
  window.__shell = LexeditorUI.mountShell({host: '#lexeditor-shell',
    plugin: {id: 'fixture', name: 'Fixture'},
    tabs: tabs.map(id => ({id, label: id.toUpperCase()})),
    activeTab: () => window.__tab, navigate: id => { window.__tab = id; window.__shell.refresh(); }});
}'''

DOTS = ".lex-shell-header nav button .lex-tab-unviewed"


def mount(page, tabs):
    page.evaluate(STUB)
    framework(page)
    page.evaluate(MOUNT, tabs)
    page.wait_for_selector('.lex-shell-header nav button')


def test_first_mount_shows_no_dots(page):
    mount(page, ['a', 'b'])
    # The shell's own Mods tab plus the plugin's two.
    assert page.locator('.lex-shell-header nav button').count() == 3
    assert page.locator(DOTS).count() == 0


def test_a_new_tab_is_dotted_until_opened(page):
    mount(page, ['a', 'b'])
    page.reload()
    mount(page, ['a', 'b', 'c'])
    dots = page.locator(DOTS)
    assert dots.count() == 1
    assert dots.first.evaluate('dot => dot.closest("button").dataset.tab') == 'c'
    before = page.locator('.lex-shell-header nav').evaluate('nav => nav.getBoundingClientRect().height')
    page.locator('.lex-shell-header nav button[data-tab="c"]').click()
    assert page.locator(DOTS).count() == 0
    after = page.locator('.lex-shell-header nav').evaluate('nav => nav.getBoundingClientRect().height')
    assert before == after, (before, after)
    page.reload()
    mount(page, ['a', 'b', 'c'])
    assert page.locator(DOTS).count() == 0
