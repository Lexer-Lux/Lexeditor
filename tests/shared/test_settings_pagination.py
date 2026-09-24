"""Whole setting panels fit their pages and can be reached with the wheel."""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('zoom', [1, 1.25])
def test_settings_pages_fit_and_wheel_preserves_edits(zoom):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 900})
            page.route('http://fixture/**', lambda r: r.fulfill(
                body='<main id="main"></main>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.evaluate('''zoom => {
              document.body.style.zoom=zoom;
              const U=LexeditorUI;
              const cards=Array.from({length:364},(_,i)=>U.detailPanel({title:'Setting '+i,
                help:'Use this setting to change the example value.',
                body:Array.from({length:i%3+1},(_,j)=>U.detailField({label:'Value '+j,
                  control:U.element('input',{value:i,'aria-label':`Value ${i}-${j}`})}))}));
              document.querySelector('main').append(U.settingsColumns(cards));
            }''', zoom)
            page.wait_for_timeout(500)
            page.get_by_role('textbox', name='Value 0-0', exact=True).fill('edited')
            page.get_by_role('textbox', name='Value 0-0', exact=True).blur()
            assert page.locator('.lex-page-total').inner_text() != '1'
            assert page.evaluate('''() => {
              const box=document.querySelector('.lex-tweaks-scroll').getBoundingClientRect();
              return [...document.querySelectorAll('.lex-tweak-column > section')]
                .every(n=>n.getBoundingClientRect().bottom<=box.bottom+2);
            }''')
            page.locator('.lex-tweaks-scroll').hover(position={'x': 10, 'y': 10})
            page.mouse.wheel(0, 160)
            page.wait_for_timeout(250)
            assert page.locator('.lex-page-number').input_value() == '2'
            page.get_by_role('button', name='First page', exact=True).click()
            assert page.get_by_role('textbox', name='Value 0-0', exact=True).input_value() == 'edited'
            page.set_viewport_size({'width': 1050, 'height': 750})
            page.wait_for_timeout(350)
            assert page.locator('.lex-page-number').is_visible()
        finally:
            browser.close()


@pytest.mark.parametrize('minimum, count', [(400, 3), (180, 6)])
def test_columns_order_and_reject_oversize_cards(minimum, count):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('http://fixture/**', lambda route: route.fulfill(body='<body></body>', content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
            page.add_script_tag(path=str(ROOT / 'ui/framework.js'))
            page.evaluate('''minimum => {
              const U=LexeditorUI;
              const cards=Array.from({length:36},(_,i)=>{
                const card=U.detailPanel({title:`Setting ${String(35-i).padStart(2,'0')}`});
                card.style.height='100px'; return card;
              });
              window.fixture=U.settingsColumns(cards);
              fixture.style.cssText=`height:500px;width:1500px;--lex-tweak-card-width:${minimum}px`;
              document.body.append(fixture);
            }''', minimum)
            page.wait_for_timeout(150)
            assert not errors
            columns = page.locator('.lex-tweak-column')
            assert columns.count() == count
            widths = columns.evaluate_all('nodes=>nodes.map(n=>n.getBoundingClientRect().width)')
            assert max(widths) - min(widths) < 1
            titles = page.locator('.lex-tweak-column .lex-detail-panel-title').all_text_contents()
            assert titles == sorted(titles)
            assert columns.first.locator('section').count() > 1
            assert page.locator('.lex-tweaks-scroll').evaluate('n=>n.scrollHeight<=n.clientHeight+1')
            for css in ('width:600px', 'height:900px'):
                failure = page.evaluate('''css => {
                  const card=fixture.querySelector('.lex-tweak-column > section');
                  const previous=card.style.cssText;
                  card.style.cssText=css;
                  try { fixture.lexFitPage(); return ''; }
                  catch(error) { return error.message; }
                  finally { card.style.cssText=previous; fixture.lexFitPage(); }
                }''', css)
                assert 'Tweak cannot fit one column' in failure
        finally:
            browser.close()
