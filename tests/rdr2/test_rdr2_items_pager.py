"""The Items pagination bar carries page controls, not the save state.

The unsaved-change counter belongs with this plugin's other save controls in
the toolbar. In the pagination bar its text pushed the item filters onto a
second row inside a bar that has room for one, which read as a mangled bar.
"""
from pathlib import Path
import tempfile
from playwright.sync_api import sync_playwright, expect
from rdr2_browser_check import document


def open_items_page(page):
    page.route('**/*',lambda route:route.abort())
    page.set_content(document().replace(
        '<head>','<head><base href="https://lexeditor.test/">',1))
    page.evaluate('LexeditorUI.finishPluginLoading()')
    expect(page.locator('.lex-pager')).to_have_count(1)
    return page.get_by_role('textbox',name='Item name',exact=True)


def test_items_pager_holds_no_save_state():
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        name=open_items_page(page)
        # One real pending change, so the counter has text to print.
        name.fill('Renamed Rum')
        name.blur()
        assert page.evaluate('dirtyCount()')==1
        pager=page.locator('.lex-pager')
        expect(pager.locator('.savebar,.dirty')).to_have_count(0)
        assert 'unsaved change' not in pager.inner_text()
        assert 'use header SAVE' not in pager.inner_text()
        toolbar_save=page.locator('#toolbar .savebar .dirty')
        expect(toolbar_save).to_have_count(1)
        assert 'unsaved change' in toolbar_save.inner_text()
        # The bar has one height, so what it carries must fit inside it.
        assert page.evaluate("()=>{const bar=document.querySelector('.lex-pager');"
                             "return bar.scrollHeight<=bar.clientHeight+1;}")
        page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-rdr2-items-pager.png'))
        browser.close()
