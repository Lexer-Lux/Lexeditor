"""A developer can rename a page tab in place, and the name ships.

Double-click the name in developer mode, type, press Enter. The name is saved
with that tab's view defaults, the same way holding a tab saves its layout, so
every reader sees it. Escape keeps the old name and an empty name restores the
shipped one: a tab nobody can name is a tab nobody can find.
"""
import pytest

from test_shared_ui_feedback import framework, page


def mount_shell(page, developer=True):
    page.evaluate("""developer => {
      window.savedCalls = [];
      window.pywebview = {api: {
        lexeditor_settings: async () => ({developerMode: developer}),
        save_default_view: async (...args) => {
          window.savedCalls.push(args);
          return {saved: true};
        },
      }};
      document.body.insertAdjacentHTML('afterbegin','<div id="shell"></div>');
      window.shell = LexeditorUI.mountShell({host:'#shell',brand:'LEXEDITOR',
        plugin:{id:'fixture',name:'Fixture'},
        tabs:[{id:'items',label:'Items'},{id:'magic',label:'Magic'}],
        activeTab:()=> 'items', navigate(){}});
    }""", developer)
    page.wait_for_timeout(300)


def label_of(page, tab):
    # The bar uppercases its labels for display; the stored name is what the
    # reader typed, so read the text itself rather than the painted case.
    return page.locator(
        f'nav button[data-tab="{tab}"] .lex-tab-label-text').evaluate("n=>n.textContent.trim()")


def rename(page, tab, typed, key="Enter"):
    page.locator(f'nav button[data-tab="{tab}"] .lex-tab-label-text').dblclick()
    field = page.locator(f'nav button[data-tab="{tab}"] .lex-label-rename')
    field.wait_for(timeout=3000)
    field.fill(typed)
    field.press(key)
    page.wait_for_timeout(250)


def test_renaming_a_tab_saves_the_name_for_everyone(page):
    framework(page)
    mount_shell(page)
    assert label_of(page, "items") == "Items"
    rename(page, "items", "Gear")
    assert label_of(page, "items") == "Gear"
    saved = page.evaluate("window.savedCalls")
    assert saved == [["fixture", "items", {"fixture-items.label": "Gear"}]], saved
    assert page.evaluate('localStorage.getItem("fixture-items.label")') == "Gear"
    # A tab that was not renamed keeps its shipped name.
    assert label_of(page, "magic") == "Magic"


def test_a_saved_name_is_used_when_the_shell_is_built_again(page):
    framework(page)
    mount_shell(page)
    rename(page, "items", "Gear")
    page.evaluate("document.querySelector('.lex-shell-header').remove()")
    mount_shell(page)
    assert label_of(page, "items") == "Gear", "the saved name did not come back"


def test_escape_keeps_the_name_and_an_empty_name_restores_it(page):
    framework(page)
    mount_shell(page)
    rename(page, "items", "Half typed", key="Escape")
    assert label_of(page, "items") == "Items"
    assert page.evaluate("window.savedCalls") == []
    rename(page, "items", "Gear")
    assert label_of(page, "items") == "Gear"
    rename(page, "items", "   ")
    assert label_of(page, "items") == "Items"
    assert page.evaluate('localStorage.getItem("fixture-items.label")') is None


def test_a_reader_who_is_not_the_developer_cannot_rename(page):
    framework(page)
    mount_shell(page, developer=False)
    page.locator('nav button[data-tab="items"] .lex-tab-label-text').dblclick()
    page.wait_for_timeout(200)
    assert page.locator('nav button[data-tab="items"] .lex-label-rename').count() == 0
    assert label_of(page, "items") == "Items"
