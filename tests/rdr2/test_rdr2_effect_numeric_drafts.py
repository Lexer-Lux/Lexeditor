"""Effect detail controls keep invalid text and validate hidden drafts before Save."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rdr2_browser_check import document


def test_effect_integer_and_percent_drafts_and_exact_save_payload():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 900})
            page.route('**/*', lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            page.evaluate('''()=>{
                window.effect={key:'0x00000001',id:'EFFECT_FIXTURE',value:'2',percent:'0.25',time:'3',timeunits:'1',durationcategory:''};
                state.catalog.effects=[effect];state.effectByKey={[effect.key]:effect};
                window.draw=()=>document.querySelector('#main').replaceChildren(...['value','percent','time','timeunits'].map(field=>effectNumberEditor(effect,field,effect.id)));
                draw();
            }''')
            for field, initial in [('value', '2'), ('time', '3'), ('timeunits', '1'), ('percent', '0.25')]:
                control = page.get_by_role('spinbutton', name=f'Effect {field} for 0x00000001', exact=True)
                for raw in (['1.5', ''] if field != 'percent' else ['', '1e309']):
                    control.fill(raw)
                    control.blur()
                    retained = control.input_value()
                    assert not control.evaluate('e=>e.checkValidity()')
                    assert page.evaluate(f'state.effectEdits["0x00000001|{field}"]') == retained
                    page.evaluate('draw()')
                    expect(control).to_have_value(retained)
                    assert not control.evaluate('e=>e.checkValidity()')
                    page.evaluate("document.querySelector('#main').replaceChildren()")
                    before = page.evaluate('window.__requests.length')
                    failure = page.evaluate('''async()=>{try{await saveCatalog();return 'saved'}catch(e){return e.message}}''')
                    assert ('whole number' if field != 'percent' else 'finite number') in failure
                    page.evaluate('saveAllChanges()')
                    assert page.evaluate('window.__requests.length') == before
                    if page.locator('.lex-important-dialog').count():
                        page.locator('.lex-important-dialog').get_by_role('button', name='Confirm and Close', exact=True).click()
                    page.evaluate('draw()')
                    control.fill(initial)
                    assert page.evaluate('Object.keys(state.effectEdits).length') == 0
            value = page.get_by_role('spinbutton', name='Effect value for 0x00000001', exact=True)
            percent = page.get_by_role('spinbutton', name='Effect percent for 0x00000001', exact=True)
            value.fill('9007199254740993')
            percent.fill('-0.125')
            page.evaluate('draw()')
            expect(value).to_have_value('9007199254740993')
            expect(percent).to_have_value('-0.125')
            page.evaluate('saveCatalog()')
            assert page.evaluate('window.__requests.filter(r=>r.path==="/api/catalog/save").at(-1).body.effects') == [
                {'key': '0x00000001', 'field': 'value', 'value': '9007199254740993'},
                {'key': '0x00000001', 'field': 'percent', 'value': '-0.125'},
            ]
            assert page.evaluate('Object.keys(state.effectEdits).length') == 0
            assert page.evaluate('effect.value') == '9007199254740993'
            assert page.evaluate('effect.percent') == '-0.125'
            page.evaluate('''()=>{effect.id='EFFECT_HEALTH_CORE';effect.value='1';effect.percent='10';draw()}''')
            value = page.get_by_role('spinbutton', name='Effect value for 0x00000001', exact=True)
            percent = page.get_by_role('spinbutton', name='Effect percent for 0x00000001', exact=True)
            percent.fill('50')
            assert 'display tier 5' in value.evaluate('e=>e.title||e.dataset.lexTitle||""')
            expect(value).to_have_value('1')
            value.fill('5')
            assert 'Warning' not in value.evaluate('e=>e.title||e.dataset.lexTitle||""')
            expect(percent).to_have_value('50')
            page.locator('#global-save').click()
            page.wait_for_function('Object.keys(state.effectEdits).length===0')
            assert page.evaluate('window.__requests.filter(r=>r.path==="/api/catalog/save").length') == 2
            assert page.evaluate('effect.value') == '5'
            assert page.evaluate('effect.percent') == '50'
        finally:
            browser.close()
