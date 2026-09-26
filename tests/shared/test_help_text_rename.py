"""A developer can reword a help bubble, and the wording ships.

A bubble has no name of its own, so the shipped text is the key: the stored
override is found by a digest of it. Escape keeps the shipped text, an empty
text restores it, and a reader who is not the developer cannot edit it.
"""
import pytest

from test_shared_ui_feedback import framework, page
from test_tab_rename import mount_shell

SHIPPED = "Chance that this item drops, in percent."
REWORDED = "How often this item drops, in percent."


def mount_help(page):
    page.evaluate("""shipped => {
      document.querySelector('main').replaceChildren(
        LexeditorUI.detailPanel({title:'Record', body:[
          LexeditorUI.detailField({label:'Drop rate', help:LexeditorUI.infoHelp(shipped),
            control:LexeditorUI.el('input',{type:'number',value:25})})]}));
    }""", SHIPPED)
    page.wait_for_timeout(200)


def open_help(page):
    page.locator(".lex-field-help .lex-info-help").first.hover()
    page.wait_for_selector(".lex-help-popover", timeout=3000)
    page.wait_for_timeout(150)
    return page.locator(".lex-help-popover").last


def popover_text(page):
    return page.locator(".lex-help-popover").last.evaluate("n=>n.textContent.trim()")


def test_reworded_help_is_saved_and_shown_again(page):
    framework(page)
    mount_shell(page)
    mount_help(page)
    open_help(page)
    assert popover_text(page) == SHIPPED
    page.locator(".lex-field-help .lex-info-help").first.dblclick()
    editor = page.locator(".lex-help-edit").first
    editor.wait_for(timeout=3000)
    assert editor.input_value() == SHIPPED
    editor.fill(REWORDED)
    editor.press("Control+Enter")
    page.wait_for_timeout(300)
    saved = page.evaluate("window.savedCalls")
    assert len(saved) == 1 and saved[0][0:2] == ["fixture", "items"], saved
    key, value = list(saved[0][2].items())[0]
    assert key.startswith("fixture-items.help.") and key.endswith(".text"), key
    assert value == REWORDED, saved
    # The same explanation reads the new wording wherever it is shown again.
    page.mouse.move(0, 0)
    page.wait_for_timeout(250)
    mount_help(page)
    open_help(page)
    assert popover_text(page) == REWORDED


def test_escape_keeps_the_shipped_text_and_an_empty_one_restores_it(page):
    framework(page)
    mount_shell(page)
    mount_help(page)
    page.locator(".lex-field-help .lex-info-help").first.dblclick()
    editor = page.locator(".lex-help-edit").first
    editor.wait_for(timeout=3000)
    editor.fill("Half typed")
    editor.press("Escape")
    page.wait_for_timeout(250)
    assert popover_text(page) == SHIPPED
    assert page.evaluate("window.savedCalls") == []
    page.locator(".lex-field-help .lex-info-help").first.dblclick()
    editor = page.locator(".lex-help-edit").first
    editor.wait_for(timeout=3000)
    editor.fill(REWORDED)
    editor.press("Control+Enter")
    page.wait_for_timeout(250)
    page.locator(".lex-field-help .lex-info-help").first.dblclick()
    editor = page.locator(".lex-help-edit").first
    editor.wait_for(timeout=3000)
    editor.fill("   ")
    editor.press("Control+Enter")
    page.wait_for_timeout(250)
    assert popover_text(page) == SHIPPED


def test_a_reader_who_is_not_the_developer_cannot_reword_help(page):
    framework(page)
    mount_shell(page, developer=False)
    mount_help(page)
    page.locator(".lex-field-help .lex-info-help").first.dblclick()
    page.wait_for_timeout(200)
    assert page.locator(".lex-help-edit").count() == 0
    assert popover_text(page) == SHIPPED


@pytest.mark.parametrize('finish', ['Enter', 'click away'])
def test_plain_enter_or_clicking_away_keeps_the_new_wording(page, finish):
    # Lexer: "any changes i make straight up don't even matter. just ignored."
    # Only Ctrl+Enter saved; clicking away threw the edit away.
    framework(page)
    mount_shell(page)
    mount_help(page)
    open_help(page)
    page.locator(".lex-field-help .lex-info-help").first.dblclick()
    editor = page.locator(".lex-help-edit").first
    editor.wait_for(timeout=3000)
    widths = page.evaluate("""() => {const e=document.querySelector('.lex-help-edit'),p=e.parentElement,s=getComputedStyle(p);
      return {editor:e.getBoundingClientRect().width, room:p.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)}}""")
    assert abs(widths['editor'] - widths['room']) <= 2, widths  # fills the bubble
    editor.fill(REWORDED)
    if finish == 'Enter':
        editor.press("Enter")
    else:
        page.mouse.click(600, 700)
    page.wait_for_timeout(300)
    saved = page.evaluate("window.savedCalls")
    assert saved and list(saved[-1][2].values())[0] == REWORDED, saved
