"""A renamed tab rejoins the bar in alphabetical order.

Subtab bars sort themselves (tweaks and misc last, everything else by
name), but a rename only repainted the label: the tab kept its old slot
and the bar stopped being alphabetical. Renaming back (or undoing) sorts
again, and the positional shortcut badges follow their slots.
"""
from test_shared_ui_feedback import framework, page  # noqa: F401  (fixture)
from test_tab_rename import mount_shell

BUILD = """() => {
  const U = LexeditorUI;
  const main = document.querySelector('main');
  window.showPanel = () => main.replaceChildren(U.tabbedPanel({
    label: 'Monster details', active: 'alpha',
    tabs: [{id: 'charlie', label: 'Charlie'}, {id: 'alpha', label: 'Alpha'},
           {id: 'bravo', label: 'Bravo'}],
    change: () => {}, content: U.el('div', {}, 'body')}));
  window.showBar = () => main.replaceChildren(U.subtabBar({
    label: 'Sections', active: 'apple',
    tabs: [{id: 'zebra', label: 'Zebra'}, {id: 'apple', label: 'Apple'},
           {id: 'mango', label: 'Mango'}],
    change: () => {}}));
}"""


def mount(page):
    framework(page)
    mount_shell(page, developer=True)
    page.evaluate(BUILD)


def order(page, bar):
    return page.locator(f'{bar} .lex-subtab-button').evaluate_all(
        'ns=>ns.map(n=>n.querySelector(".lex-tab-label-text").textContent.trim())')


def badges(page, bar):
    return page.locator(f'{bar} .lex-subtab-button').evaluate_all(
        'ns=>ns.map(n=>n.querySelector(".lex-tab-shortcut")?.textContent.trim() ?? "")')


def rename(page, bar, label, typed):
    page.locator(f'{bar} .lex-tab-label-text', has_text=label).dblclick()
    field = page.locator(f'{bar} .lex-label-rename')
    field.wait_for(timeout=3000)
    field.fill(typed)
    field.press('Enter')
    page.wait_for_timeout(300)


def test_panel_tab_rename_resorts(page):
    mount(page)
    page.evaluate('showPanel()')
    assert order(page, '.lex-tabbed-panel-tabs') == ['Alpha', 'Bravo', 'Charlie']
    rename(page, '.lex-tabbed-panel-tabs', 'Alpha', 'Zulu')
    assert order(page, '.lex-tabbed-panel-tabs') == ['Bravo', 'Charlie', 'Zulu']
    rename(page, '.lex-tabbed-panel-tabs', 'Zulu', 'Alpha')
    assert order(page, '.lex-tabbed-panel-tabs') == ['Alpha', 'Bravo', 'Charlie']


def test_rename_undo_restores_name_and_order(page):
    mount(page)
    page.evaluate('showBar()')
    rename(page, '.lex-subtab-bar', 'Apple', 'Zzz')
    assert order(page, '.lex-subtab-bar') == ['Mango', 'Zebra', 'Zzz']
    page.keyboard.press('Control+z')
    page.wait_for_timeout(300)
    assert order(page, '.lex-subtab-bar') == ['Apple', 'Mango', 'Zebra']


def test_subtab_rename_resorts_and_rebadges(page):
    mount(page)
    page.evaluate('showBar()')
    assert order(page, '.lex-subtab-bar') == ['Apple', 'Mango', 'Zebra']
    assert badges(page, '.lex-subtab-bar') == ['⇧1', '⇧2', '⇧3']
    rename(page, '.lex-subtab-bar', 'Apple', 'Zzz')
    assert order(page, '.lex-subtab-bar') == ['Mango', 'Zebra', 'Zzz']
    assert badges(page, '.lex-subtab-bar') == ['⇧1', '⇧2', '⇧3']
