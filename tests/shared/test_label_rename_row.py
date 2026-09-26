"""Renaming a property in place gives the input the whole row.

Lexer: "when i'm double clicking a property name to edit it the ref rail thing
should not show. and the text box should expand to fit available space instead
of being this tiny little thing". The input replaced the label text inside the
fixed name lane, so it was a tenth of the row wide, and the value's reference
rail stayed beside it.
"""
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "shared"))


def test_a_rename_input_takes_the_row_and_the_rail_stands_down():
    from test_shared_ui_feedback import framework

    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True, ignore_default_args=["--hide-scrollbars"])
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 800})
            page.route("http://fixture/**", lambda route: route.fulfill(
                body="<main id='main'></main>", content_type="text/html"))
            page.goto("http://fixture/")
            page.add_style_tag(path=str(ROOT / "ui" / "framework.css"))
            framework(page)
            page.evaluate("""()=>{const U=LexeditorUI;
              document.querySelector('#main').append(
                U.detailField({label:'Strength',control:U.el('div',{class:'control-box'},
                  U.el('span',{class:'lex-reference-values'},'V 25'),U.el('input',{value:'25'}))}));}""")
            page.wait_for_timeout(150)
            sizes = page.evaluate("""()=>{const field=document.querySelector('#main .lex-detail-field'),
              label=field.querySelector('.lex-detail-field-label-text'),
              input=document.createElement('input');
              input.type='text'; input.className='lex-label-rename'; input.value=label.textContent;
              label.replaceWith(input);
              const box=field.getBoundingClientRect(), control=field.querySelector('.lex-detail-field-control');
              return {field:Math.round(box.width), input:Math.round(input.getBoundingClientRect().width),
                controlHidden:getComputedStyle(control).display==='none'};}""")
            # The row, minus the name lane's own padding.
            assert sizes["input"] >= sizes["field"] - 40, sizes
            assert sizes["controlHidden"], sizes
        finally:
            browser.close()
