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


def mount_subtabs(page):
    page.evaluate("""()=>{
      document.querySelector('main').replaceChildren(LexeditorUI.subtabBar({
        label: 'Sections',
        tabs: [{id:'stats',label:'Stats'},{id:'growth',label:'Growth'}],
        active: 'stats', change(){}}));
    }""")
    page.wait_for_timeout(200)


def subtab_label(page, index=0):
    return page.locator(".lex-subtab-button .lex-tab-label-text").nth(index) \
        .evaluate("n=>n.textContent.trim()")


def test_renaming_a_subtab_ships_under_the_page_tab_that_owns_it(page):
    framework(page)
    mount_shell(page)
    mount_subtabs(page)
    assert subtab_label(page) == "Stats"
    page.locator(".lex-subtab-button .lex-tab-label-text").first.dblclick()
    field = page.locator(".lex-subtab-button .lex-label-rename").first
    field.wait_for(timeout=3000)
    field.fill("Parameters")
    field.press("Enter")
    page.wait_for_timeout(250)
    assert subtab_label(page) == "Parameters"
    saved = page.evaluate("window.savedCalls")
    # The name is stored under the page tab the subtabs belong to, which is
    # where that screen's shippable view defaults live.
    assert saved == [["fixture", "items", {"fixture-items.sub.stats.label": "Parameters"}]], saved
    mount_subtabs(page)
    assert subtab_label(page) == "Parameters", "the saved subtab name did not come back"
    assert subtab_label(page, 1) == "Growth"


def mount_field(page):
    page.evaluate("""()=>{
      document.querySelector('main').replaceChildren(
        LexeditorUI.detailPanel({title:'Record', body:[
          LexeditorUI.detailField({label:'Weight',
            control:LexeditorUI.el('input',{type:'number',value:42})})]}));
    }""")
    page.wait_for_timeout(200)


def field_label(page):
    return page.locator(".lex-detail-field-label-text").first \
        .evaluate("n=>n.textContent.trim()")


def test_renaming_a_property_name_ships_for_that_property(page):
    framework(page)
    mount_shell(page)
    mount_field(page)
    assert field_label(page) == "Weight"
    page.locator(".lex-detail-field-label-text").first.dblclick()
    field = page.locator(".lex-detail-field-label .lex-label-rename").first
    field.wait_for(timeout=3000)
    field.fill("Mass")
    field.press("Enter")
    page.wait_for_timeout(250)
    assert field_label(page) == "Mass"
    saved = page.evaluate("window.savedCalls")
    assert saved == [["fixture", "items", {"fixture-items.field.Weight.label": "Mass"}]], saved
    # Every screen that draws this property reads the same name.
    mount_field(page)
    assert field_label(page) == "Mass", "the saved property name did not come back"


def test_escape_keeps_a_property_name_and_an_empty_one_restores_it(page):
    framework(page)
    mount_shell(page)
    mount_field(page)
    page.locator(".lex-detail-field-label-text").first.dblclick()
    page.locator(".lex-detail-field-label .lex-label-rename").first.fill("Half typed")
    page.locator(".lex-detail-field-label .lex-label-rename").first.press("Escape")
    page.wait_for_timeout(200)
    assert field_label(page) == "Weight"
    page.locator(".lex-detail-field-label-text").first.dblclick()
    page.locator(".lex-detail-field-label .lex-label-rename").first.fill("Mass")
    page.locator(".lex-detail-field-label .lex-label-rename").first.press("Enter")
    page.wait_for_timeout(200)
    page.locator(".lex-detail-field-label-text").first.dblclick()
    page.locator(".lex-detail-field-label .lex-label-rename").first.fill("   ")
    page.locator(".lex-detail-field-label .lex-label-rename").first.press("Enter")
    page.wait_for_timeout(200)
    assert field_label(page) == "Weight", "an empty name did not restore the shipped one"


def test_the_shell_undo_takes_a_rename_back_and_redo_puts_it_on_again(page):
    framework(page)
    mount_shell(page)
    assert page.locator("#global-undo").is_disabled()
    assert page.locator("#global-redo").is_disabled()
    rename(page, "items", "Gear")
    assert label_of(page, "items") == "Gear"
    assert not page.locator("#global-undo").is_disabled(), "a rename is not undoable"
    page.locator("#global-undo").click()
    page.wait_for_timeout(300)
    assert label_of(page, "items") == "Items", "undo did not put the shipped name back"
    assert page.evaluate('localStorage.getItem("fixture-items.label")') is None
    # The undo is saved the same way the rename was, so everyone sees it.
    assert page.evaluate("window.savedCalls").pop() == [
        "fixture", "items", {"fixture-items.label": ""}]
    assert not page.locator("#global-redo").is_disabled(), "nothing to redo"
    page.locator("#global-redo").click()
    page.wait_for_timeout(300)
    assert label_of(page, "items") == "Gear", "redo did not put the name back"
    assert page.evaluate('localStorage.getItem("fixture-items.label")') == "Gear"
