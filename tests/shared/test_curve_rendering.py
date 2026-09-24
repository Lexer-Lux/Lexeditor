"""Graphs keep mathematical notation and invalid data visible to the user."""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def test_math_curve_resize_and_invalid_divisor():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1000, "height": 700})
            page.route('http://fixture/**', lambda route: route.fulfill(
                body='<main id="main"></main>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.evaluate('''() => {
                const UI=LexeditorUI;
                let divisor=2;
                const input=UI.el('input',{type:'number',value:2,
                    oninput:event=>divisor=Number(event.target.value)});
                const curve=UI.curveEditor({title:'HP',
                    variables:[{label:'B',control:input}],
                    range:{min:0,max:100},domain:{min:1,max:10},
                    evaluate:x=>divisor ? x*x/divisor : null,
                    invalidText:'A DIVISOR IS 0',
                    formula:UI.mathFormula('HP(L)=floor(L^2/B)')});
                document.querySelector('main').append(UI.curveGrid(curve));
            }''')
            assert page.locator('.lex-curve-plot math mfrac').count() == 1
            assert page.locator('.lex-curve-plot math msup').count() == 1
            assert page.locator('.lex-curve-svg').get_attribute('preserveAspectRatio') == 'xMidYMid meet'
            page.set_viewport_size({'width': 640, 'height': 700})
            page.locator('.lex-curve-editor').hover()
            page.locator('input').fill('0')
            page.wait_for_timeout(100)
            assert page.locator('.lex-curve-status').inner_text() == 'A DIVISOR IS 0'
            assert page.locator('.lex-curve-line').get_attribute('d') is None
            page.locator('input').fill('4')
            page.wait_for_timeout(100)
            assert page.locator('.lex-curve-status').inner_text() == ''
            assert page.locator('.lex-curve-line').get_attribute('d')
        finally:
            browser.close()
