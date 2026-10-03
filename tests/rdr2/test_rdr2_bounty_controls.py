"""Production bounty inputs retain invalid drafts and protect global Save."""
from playwright.sync_api import sync_playwright, expect
from rdr2_browser_check import document
from rdr2_tables_browser_check import payloads


def test_bounty_drafts_hidden_save_exact_values_and_readonly(tmp_path):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 1100})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('**/*', lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            data = payloads()['/api/bounty-hunters']
            data['settings'][0]['id'] = 'response/RandomWeight'
            chance_id = 'phase/InitialRiders/random/PoliceDog/Chances'
            data['phases'][0]['groups'][0]['ids']['chance'] = chance_id
            page.evaluate('''async data=>{
              for(const info of Object.values(state.config.datasets)){info.scopes=[];info.crime=true;}
              state.config.datasets.crimeTweaks={readonly:true,crime:true,scopes:[]};
              for(const ds of ['mine','vanilla','crimeTweaks'])state.store[ds]={crime:{crimes:[]}};
              state.bountyHunters.mine=normalizeBountyHunters(data);
              state.tab='crime';state.filters.crimeSection='bounty';
              window.__responses['/api/bounty-hunters']=data;
              window.__responses['/api/bounty-hunters/save']={saved:2};
              window.__saveFailures=[];window.showSaveFailure=e=>__saveFailures.push(e.message);
              await renderCrime();
            }''', data)
            def control(identity):
                return page.get_by_role('spinbutton', name=identity, exact=True)
            for identity, value in [('response/RandomWeight', ''), ('response/RandomWeight', '-1'), (chance_id, '1.01')]:
                control(identity).fill(value)
                assert not control(identity).evaluate('e=>e.checkValidity()')
                assert page.evaluate('id=>Object.hasOwn(state.bountyHunterEdits,id)', identity)
                page.evaluate('renderCrime()')
                expect(control(identity)).to_have_value(value)
                before = page.evaluate('window.__requests.length')
                assert page.evaluate("async()=>{try{await saveBountyHunters();return ''}catch(e){return e.message}}")
                # Hidden invalid bounty values must stop earlier global writers.
                page.evaluate("state.alcoholEdits={CONSUMABLE_RUM:0.25};document.querySelector('#main').innerHTML='' ")
                page.evaluate('saveAllChanges()')
                assert page.evaluate('window.__requests.length') == before
                assert page.evaluate('state.alcoholEdits.CONSUMABLE_RUM') == 0.25
                assert page.evaluate('Object.keys(state.bountyHunterEdits).length') == 1
                page.evaluate('state.alcoholEdits={};state.bountyHunterEdits={};renderCrime()')
            control('response/RandomWeight').fill('0.123456789123456789')
            control(chance_id).fill('1')
            page.evaluate('renderCrime()')
            expect(control('response/RandomWeight')).to_have_value('0.123456789123456789')
            page.evaluate('saveBountyHunters()')
            rows = page.evaluate("window.__requests.find(row=>row.path==='/api/bounty-hunters/save').body.edits")
            assert {row['id']: row['value'] for row in rows} == {'response/RandomWeight': '0.123456789123456789', chance_id: '1'}
            page.wait_for_function('Object.keys(state.bountyHunterEdits).length===0')
            page.evaluate('''async id=>{
              state.bountyHunters.mine.readonlyIds=[id];await renderCrime();
            }''', chance_id)
            expect(control(chance_id)).to_be_disabled()
            before = page.evaluate('window.__requests.length')
            page.evaluate('id=>state.bountyHunterEdits[id]="0.5"', chance_id)
            assert page.evaluate("async()=>{try{await saveBountyHunters();return ''}catch(e){return e.message}}")
            assert page.evaluate('window.__requests.length') == before
            page.evaluate('state.bountyHunterEdits={}')
            page.evaluate("async()=>{state.bountyHunters.mine.settings[0].value='NaN';await renderCrime()}")
            expect(page.get_by_role('textbox', name='response/RandomWeight', exact=True)).to_have_value('NaN')
            expect(page.get_by_role('textbox', name='response/RandomWeight', exact=True)).to_be_disabled()
            page.screenshot(path=str(tmp_path / 'bounty-controls.png'), full_page=True)
            page.evaluate("async()=>{state.bountyHunters.vanilla=structuredClone(state.bountyHunters.mine);state.ds='vanilla';await renderCrime()}")
            expect(control(chance_id)).to_be_disabled()
            assert not errors, errors
        finally:
            browser.close()
