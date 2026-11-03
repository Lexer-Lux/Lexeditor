"""Exercise the production creation dialog with authored data and API replies."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rdr2_browser_check import document


def test_effect_creation_retains_invalid_drafts_and_posts_exact_values():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 900})
            page.route('**/*', lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            page.evaluate('''()=>{
              state.catalog.effects=[{key:'0x00000001',id:'BEHAVIOR',durationcategory:''}];
              window.__responses['/api/catalog/effects/create']={key:'0x00000002',label:'Fixture',symbol:'LEX_FIXTURE'};
              showCreateEffect();
            }''')
            dialog = page.get_by_role('dialog').filter(has_text='Create effect record')
            controls = dialog.get_by_role('spinbutton')
            expect(controls).to_have_count(3)
            value, percent, time = [controls.nth(i) for i in range(3)]
            dialog.get_by_role('textbox').nth(0).fill('LEX_FIXTURE')
            create = dialog.get_by_role('button', name='Create effect', exact=True)
            for control, drafts in [(value, ['1.5', '']), (time, ['-1.5', '']), (percent, [''])]:
                for raw in drafts:
                    control.fill(raw)
                    create.click()
                    expect(dialog).to_be_visible()
                    expect(control).to_have_value(raw)
                    assert not control.evaluate('e=>e.checkValidity()')
                    assert page.evaluate("window.__requests.filter(r=>r.path==='/api/catalog/effects/create').length") == 0
                    control.fill('0')
            value.fill('9007199254740993')
            time.fill('-9007199254740993')
            percent.fill('0.123456789123')
            create.click()
            page.wait_for_function("window.__requests.some(r=>r.path==='/api/catalog/effects/create')")
            posted = page.evaluate("window.__requests.find(r=>r.path==='/api/catalog/effects/create').body")
            assert posted['value'] == '9007199254740993'
            assert posted['time'] == '-9007199254740993'
            assert posted['percent'] == '0.123456789123'
            assert posted['timeunits'] == '0'
            assert posted['behavior'] == 'BEHAVIOR'
            assert posted['durationcategory'] == ''
            expect(dialog).to_have_count(0)
        finally:
            browser.close()
