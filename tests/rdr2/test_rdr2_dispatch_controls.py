"""Actual dispatch inputs preserve drafts, reject before writers and lock source rows."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0,str(Path(__file__).resolve().parent))
from rdr2_browser_check import document


def test_dispatch_drafts_readonly_references_and_save(tmp_path):
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1400,'height':900})
            page.route('**/*',lambda route:route.abort())
            page.set_content(document().replace('<head>','<head><base href="https://lexeditor.test/">',1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            page.evaluate('''()=>{
              for(const info of Object.values(state.config.datasets))info.scopes=[];
              window.dispatchFixture={group:'',field:'ParoleDuration',value:'9000'};
              state.store.mine.dispatch={rows:[dispatchFixture]};
              state.store.vanilla.dispatch={rows:[{...dispatchFixture,value:'8500'}]};
              state.tab='crime';state.filters.crimeSection='dispatch';
              window.__responses['/api/dispatch/save']={saved:1};
              window.drawDispatch=()=>document.querySelector('#main').replaceChildren(dispatchSection());drawDispatch();
            }''')
            control=page.get_by_role('spinbutton',name='Global ParoleDuration',exact=True)
            control.focus()  # Table reference actions appear while their cell is active.
            page.locator('#main .lex-reference-value').click()
            expect(control).to_have_value('8500')
            assert page.evaluate("state.dispatchEdits['|ParoleDuration']")=='8500'
            control.fill('')
            expect(control).to_have_value('')
            assert not control.evaluate('e=>e.checkValidity()')
            page.evaluate('drawDispatch()')
            expect(control).to_have_value('')
            page.evaluate("state.crimeEdits={'CRIME|Bounty':'10'}")
            before=page.evaluate('window.__requests.length')
            assert 'finite number' in page.evaluate("async()=>{try{await saveCrime();return ''}catch(e){return e.message}}")
            assert page.evaluate('window.__requests.length')==before
            page.evaluate('state.crimeEdits={}')
            control.fill('9000.125')
            page.evaluate('drawDispatch()')
            expect(control).to_have_value('9000.125')
            page.evaluate('saveCrime()')
            posted=page.evaluate("window.__requests.find(r=>r.path==='/api/dispatch/save').body.edits")
            assert posted==[{'group':'','field':'ParoleDuration','value':'9000.125'}]
            page.evaluate('''()=>{dispatchFixture.readonly=true;drawDispatch()}''')
            expect(control).to_be_disabled()
            assert page.locator('#main .lex-reference-value').count()>0
            assert page.locator('#main .lex-reference-value').evaluate_all('es=>es.every(e=>e.disabled)')
            page.evaluate("()=>{dispatchFixture.value='NaN';drawDispatch()}")
            expect(page.get_by_role('textbox',name='Global ParoleDuration',exact=True)).to_have_value('NaN')
            expect(page.get_by_role('textbox',name='Global ParoleDuration',exact=True)).to_be_disabled()
            page.screenshot(path=str(tmp_path/'readonly-dispatch.png'),full_page=True)
            page.evaluate("()=>{dispatchFixture.readonly=false;dispatchFixture.value='9000';state.ds='vanilla';drawDispatch()}")
            expect(control).to_be_disabled()
        finally:browser.close()
