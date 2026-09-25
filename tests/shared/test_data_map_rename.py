"""A developer can reword a Data Map line, and the wording ships.

The two prose lines - what the file controls, and the notes under it - read the
same wherever the row is opened, because the file is the row's identity and the
shipped sentence is the key. Clearing a line restores the shipped sentence.
"""
import pytest

from test_shared_ui_feedback import framework, page
from test_tab_rename import mount_shell

CONTROLS = "Shop prices and stock"
NOTES = "Prices are 16-bit; stock is one byte."
REWORDED = "Prices are 16-bit; stock is one byte. Menu prices only."


def mount_map(page):
    page.evaluate("""([controls, notes]) => {
      document.querySelector('main').replaceChildren(LexeditorUI.dataMap({
        searchKey: 'fixture-data-map',
        rows: [{filename: 'menu/price.bin', controls, notes, status: 'integrated',
                coverage: 'structured', view: 'prices'}],
      }).content);
      document.querySelector('.lex-column-list-row')?.click();
    }""", [CONTROLS, NOTES])
    page.wait_for_timeout(300)


def line(page, selector):
    return page.locator(selector).first.evaluate("n=>n.textContent.trim()")


def test_reworded_data_map_line_saves_and_comes_back(page):
    framework(page)
    mount_shell(page)
    mount_map(page)
    assert line(page, ".lex-data-map-notes") == NOTES
    page.locator(".lex-data-map-notes").first.dblclick()
    field = page.locator(".lex-data-map-notes .lex-label-rename").first
    field.wait_for(timeout=3000)
    field.fill(REWORDED)
    field.press("Enter")
    page.wait_for_timeout(300)
    saved = page.evaluate("window.savedCalls")
    assert len(saved) == 1, saved
    assert saved[0][0:2] == ["fixture", "items"], saved
    key, value = list(saved[0][2].items())[0]
    assert key == "fixture-items.datamap.menu/price.bin.notes", key
    assert value == REWORDED, value
    # The same file's line reads the new wording wherever the row is opened.
    page.evaluate("()=>document.querySelector('main').replaceChildren()")
    mount_map(page)
    assert line(page, ".lex-data-map-notes") == REWORDED
    assert line(page, ".lex-data-map-scope") == CONTROLS


def test_escape_keeps_the_shipped_line(page):
    framework(page)
    mount_shell(page)
    mount_map(page)
    page.locator(".lex-data-map-scope").first.dblclick()
    field = page.locator(".lex-data-map-scope .lex-label-rename").first
    field.wait_for(timeout=3000)
    field.fill("Half typed")
    field.press("Escape")
    page.wait_for_timeout(250)
    assert line(page, ".lex-data-map-scope") == CONTROLS
    assert page.evaluate("window.savedCalls") == []


def test_a_reader_who_is_not_the_developer_cannot_reword_a_data_map_line(page):
    framework(page)
    mount_shell(page, developer=False)
    mount_map(page)
    page.locator(".lex-data-map-notes").first.dblclick()
    page.wait_for_timeout(200)
    assert page.locator(".lex-data-map-notes .lex-label-rename").count() == 0
    assert line(page, ".lex-data-map-notes") == NOTES
