"""Pager chrome shares one text shadow: page, total and rows match.

The theme's shadow lives on the page, and the pager's numbers read as one
line with it. The current-page box, the rows-per-page box and the rows
dropdown each dropped the shadow their "/ total" neighbor keeps, so the
three controls inherit it instead. Unskinned themes inherit none.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SHADOW = "rgb(10, 20, 30) 2px 2px 0px"


def test_pager_numbers_share_the_theme_shadow():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 800, "height": 600})
            page.route("http://fixture/**", lambda r: r.fulfill(body="<html></html>", content_type="text/html"))
            page.goto("http://fixture/")
            css = (ROOT / "ui/framework.css").read_text(encoding="utf-8")
            page.set_content("<style>" + css + "</style><main></main>")
            page.add_script_tag(path=str(ROOT / "ui/framework.js"))
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.evaluate("""() => {
              const host = document.createElement('div');
              host.style.textShadow = '2px 2px 0 rgb(10, 20, 30)';
              const bar = LexeditorUI.pager({page: 1, pages: 5, total: 100, range: [21, 40],
                rowControl: {value: 20, defaultValue: 20, overridden: true}, change(){}});
              bar.querySelector('.lex-pager-right').prepend(LexeditorUI.pagerSelect(
                {label: 'Rows', value: '20', options: [{id: '20', label: '20'}]}));
              host.append(bar);
              document.querySelector('main').append(host);
            }""")
            assert not errors, errors
            shadows = page.evaluate("""() => {
              const bar = document.querySelector('.lex-pager');
              const shadowOf = selector => getComputedStyle(bar.querySelector(selector)).textShadow;
              return {number: shadowOf('input.lex-page-number'),
                      total: shadowOf('.lex-page-total'),
                      rows: shadowOf('.lex-page-row-override input'),
                      select: shadowOf('.lex-pager-right select')};
            }""")
            assert shadows == {"number": SHADOW, "total": SHADOW, "rows": SHADOW, "select": SHADOW}, shadows
        finally:
            browser.close()
