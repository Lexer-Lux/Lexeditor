"""Honor master/detail controls retain drafts and protect global Save."""
from playwright.sync_api import sync_playwright, expect
from rdr2_browser_check import document
from plugins.rdr2 import honor_actions as honor


def test_honor_drafts_exact_amounts_and_readonly(tmp_path):
    with sync_playwright() as play:
        browser=play.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1400,'height':1100})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('**/*',lambda route:route.abort())
            page.set_content(document().replace('<head>','<head><base href="https://lexeditor.test/">',1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            data=honor._defaults();data['available']=True
            for row in data['tiers']:row['amount']=str(row['amount'])
            page.evaluate('''async data=>{
              for(const info of Object.values(state.config.datasets)){info.scopes=[];info.crime=true;}
              state.config.datasets.crimeTweaks={readonly:true,crime:true,scopes:[]};
              for(const ds of ['mine','vanilla','crimeTweaks'])state.store[ds]={crime:{crimes:[]}};
              state.honorActions=normalizeHonorActions(data);window.__responses['/api/honor-actions']=data;
              window.__responses['/api/honor-actions/save']={saved:1};
              state.tab='crime';state.filters.crimeSection='honor';
              state.filters.honorSelected='tier_+5';
              window.__saveFailures=[];window.showSaveFailure=e=>__saveFailures.push(e.message);
              await renderCrime();
            }''',data)
            def amount():return page.get_by_role('spinbutton',name='Replacement for vanilla honor amount 5',exact=True)
            assert page.locator('.honor-table input,.honor-table select').count()==0
            for value in ['', '1.5']:
                amount().fill(value)
                assert not amount().evaluate('e=>e.checkValidity()')
                page.evaluate('renderCrime()');expect(amount()).to_have_value(value)
                before=page.evaluate('window.__requests.length')
                assert page.evaluate("async()=>{try{await saveHonorActions();return ''}catch(e){return e.message}}")
                page.evaluate("state.alcoholEdits={CONSUMABLE_RUM:0.25};document.querySelector('#main').innerHTML='';saveAllChanges()")
                assert page.evaluate('window.__requests.length')==before
                assert page.evaluate("state.honorActionEdits['tier_+5'].amount")==value
                assert page.evaluate('state.alcoholEdits.CONSUMABLE_RUM')==0.25
                page.evaluate('state.honorActionEdits={};state.alcoholEdits={};renderCrime()')
            amount().fill('-9007199254740993')
            page.evaluate('renderCrime()');expect(amount()).to_have_value('-9007199254740993')
            page.evaluate('saveHonorActions()')
            assert page.evaluate("window.__requests.find(row=>row.path==='/api/honor-actions/save').body.edits") == [{'id':'tier_+5','amount':'-9007199254740993'}]
            page.wait_for_function('Object.keys(state.honorActionEdits).length===0')
            page.evaluate("async()=>{state.filters.honorSelected='HONOR_EVENT_LOOT_INNOCENT';await renderCrime()}")
            page.get_by_role('checkbox',name='Loot an innocent enabled',exact=True).uncheck()
            assert page.evaluate("state.honorActionEdits.HONOR_EVENT_LOOT_INNOCENT.enabled") is False
            page.get_by_role('checkbox',name='Loot an innocent enabled',exact=True).check()
            assert page.evaluate('Object.keys(state.honorActionEdits).length')==0
            page.evaluate("async()=>{state.honorActions.events[0].enabled='unknown';await renderCrime()}")
            expect(page.get_by_role('textbox',name='Enabled',exact=True)).to_have_value('unknown')
            expect(page.get_by_role('textbox',name='Enabled',exact=True)).to_be_disabled()
            page.evaluate("async()=>{state.honorActions.tiers.find(row=>row.id==='tier_+5').amount='unknown';state.honorActions.events[0].enabled='unknown';state.filters.honorSelected='tier_+5';await renderCrime()}")
            assert page.locator('#main input[readonly][value="unknown"]').count()>=1
            expect(page.get_by_role('checkbox',name='tier_+5 enabled',exact=True)).to_be_disabled()
            page.screenshot(path=str(tmp_path/'honor-controls.png'),full_page=True)
            page.evaluate("async()=>{state.honorActions=normalizeHonorActions(structuredClone(window.__responses['/api/honor-actions']));state.ds='vanilla';await renderCrime()}")
            assert page.locator('#main .lex-detail-field input:not([disabled]):not([readonly])').count()==0
            before=page.evaluate('window.__requests.length');page.evaluate('saveHonorActions()')
            assert page.evaluate('window.__requests.length')==before
            assert not errors,errors
        finally:browser.close()
