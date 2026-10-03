"""Exercise actual skinning controls, draft validation and read-only source display."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rdr2_browser_check import document


def test_matrix_drafts_exact_save_and_readonly(tmp_path):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 900})
            page.route('**/*', lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            page.evaluate('''async()=>{
              for(const info of Object.values(state.config.datasets)){info.scopes=[];info.matrix=true;}
              window.animalFixture={key:'ANIMAL',rows:[{damage:'Poor',skin:'Perfect',item:'CONSUMABLE_RUM',qty:'1'}]};
              state.store.mine.matrix={animals:[animalFixture]};
              state.store.vanilla.matrix={animals:[structuredClone(animalFixture)]};
              state.store.kiddos.matrix={animals:[]};
              state.lootFile='__matrix';state.filters.animal='ANIMAL';
              window.__responses['/api/matrix/save']={saved:1};await renderMatrix();
            }''')
            for raw in ['1.5', '0', '-1', '']:
                control = page.get_by_role('spinbutton', name='Quantity', exact=True)
                control.fill(raw)
                expect(control).to_have_value(raw)
                assert not control.evaluate('e=>e.checkValidity()')
                page.evaluate('renderMatrix()')
                expect(page.get_by_role('spinbutton', name='Quantity', exact=True)).to_have_value(raw)
                before = page.evaluate('window.__requests.length')
                assert page.evaluate("async()=>{try{await saveMatrix();return ''}catch(e){return e.message}}")
                assert page.evaluate('window.__requests.length') == before
            page.get_by_role('spinbutton', name='Quantity', exact=True).fill('9007199254740993')
            page.evaluate('renderMatrix()')
            expect(page.get_by_role('spinbutton', name='Quantity', exact=True)).to_have_value('9007199254740993')
            qualities = page.locator('#main select')
            assert qualities.nth(0).locator('option').evaluate_all('es=>es.map(e=>e.value)') == ['Poor', 'Good', 'Perfect']
            assert qualities.nth(1).locator('option').evaluate_all('es=>es.map(e=>e.value)') == ['Poor', 'Good', 'Perfect', 'Rare', 'Legendary']
            qualities.nth(0).select_option('Good')
            page.wait_for_function("animalFixture.rows[0].damage==='Good'")
            page.locator('#main select').nth(1).select_option('Legendary')
            page.wait_for_function("animalFixture.rows[0].skin==='Legendary'")
            page.evaluate('saveMatrix()')
            posted = page.evaluate("window.__requests.find(r=>r.path==='/api/matrix/save').body.edits[0]")
            assert posted['rows'] == [{'damage': 'Good', 'skin': 'Legendary', 'item': 'CONSUMABLE_RUM', 'qty': '9007199254740993'}]
            page.get_by_role('button', name='Add yield', exact=True).click()
            page.wait_for_function('animalFixture.rows.length===2')
            before = page.evaluate('window.__requests.length')
            assert 'catalog item' in page.evaluate("async()=>{try{await saveMatrix();return ''}catch(e){return e.message}}")
            assert page.evaluate('window.__requests.length') == before
            page.evaluate("async()=>{animalFixture.rows.pop();animalFixture.readonly=true;animalFixture.rows[0].skin='UNKNOWN';animalFixture.rows[0].qty='NaN';state.store.vanilla.matrix.animals[0].rows[0].damage='Good';state.store.vanilla.matrix.animals[0].rows[0].skin='UNKNOWN';await renderMatrix()}")
            expect(page.get_by_role('textbox', name='Quantity', exact=True)).to_have_value('NaN')
            expect(page.get_by_role('textbox', name='Quantity', exact=True)).to_be_disabled()
            assert 'UNKNOWN' in page.locator('#main').inner_text() or page.locator('#main input').evaluate_all("es=>es.some(e=>e.value==='UNKNOWN')")
            for name in ['Remove yield', 'Add yield', 'Add matrix row']:
                expect(page.get_by_role('button', name=name, exact=True)).to_be_disabled()
            assert page.locator('#main .lex-reference-value').count() > 0
            assert page.locator('#main .lex-reference-value').evaluate_all('es=>es.every(e=>e.disabled)')
            page.screenshot(path=str(tmp_path / 'readonly-matrix.png'), full_page=True)
            page.evaluate("async()=>{animalFixture.readonly=false;animalFixture.rows[0].skin='Perfect';animalFixture.rows[0].qty='1';state.ds='vanilla';await renderMatrix()}")
            expect(page.get_by_role('spinbutton', name='Quantity', exact=True)).to_be_disabled()
            expect(page.get_by_role('button', name='Add yield', exact=True)).to_be_disabled()
            expect(page.get_by_role('button', name='Remove yield', exact=True)).to_be_disabled()
        finally:
            browser.close()
