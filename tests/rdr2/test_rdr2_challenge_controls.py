"""Challenge drafts retain raw input and source indices include unsupported slots."""
from playwright.sync_api import sync_playwright, expect
from rdr2_browser_check import document


def test_challenge_target_drafts_source_slots_and_readonly(tmp_path):
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
            page.evaluate('''async()=>{
              for(const info of Object.values(state.config.datasets)){info.scopes=[];info.challenges=true;}
              const known=[{base:'BASE',permutation:'PERM'},{base:'SECOND',permutation:''}];
              const goal={name:'GOAL',description:'NAME_TOBACCO',conditions:[{index:0,type:'CAIConditionGoalContext',fields:{ContextHash:'FUTURE_CONTEXT'}}],
                requirements:[{index:0,value:'10',readonly:false,role:'target',sources:[{index:0,base:'',permutation:'',readonly:true},{index:1,base:'BASE',permutation:'PERM'},{index:2,base:'FUTURE_SOURCE',permutation:''}]}]};
              const data={goals:[goal],strands:[{key:'FIXTURE',name:'ROOT',nameLabel:'NAME_TOBACCO',descriptionLabel:'NAME_TOBACCO',ranks:[{rank:1,goals:['GOAL'],rewards:[],descriptionLabel:'NAME_TOBACCO'}]}],
                allowedSourcePairs:known,allowedRewards:[],allowedConditionValues:[{type:'CAIConditionGoalContext',field:'ContextHash',values:['CHAL_CTX_ON_MOVING_TRAIN']}]};
              state.store.mine.challenges=data;state.store.vanilla.challenges=structuredClone(data);
              state.store.vanilla.challenges.goals[0].requirements[0].value='5';
              state.tab='challenges';state.filters.challengeStrand='FIXTURE';state.filters.challengeRank=1;
              window.__responses['/api/challenges/save']={saved:1};window.__responses['/api/challenges']=data;
              await renderChallenges();
            }''')
            control = page.get_by_role('spinbutton', name='GOAL target 0', exact=True)
            expect(page.get_by_role('textbox', name='GOAL score source 0', exact=True)).to_have_value('(empty score source)')
            expect(page.get_by_role('textbox', name='GOAL score source 2', exact=True)).to_have_value('FUTURE_SOURCE')
            expect(page.locator('#main select').filter(has=page.locator('option[value="FUTURE_CONTEXT"]'))).to_be_disabled()
            control.fill('')
            page.evaluate('renderChallenges()')
            expect(control).to_have_value('')
            assert page.evaluate("state.challengeEdits['GOAL|0']") == ''
            result = page.evaluate('''async()=>{window.__requests=[];try{await saveChallenges();return 'saved'}catch(error){return error.message}}''')
            assert 'finite number' in result
            assert page.evaluate('window.__requests.length') == 0
            control.fill('9007199254740993.125')
            page.evaluate('renderChallenges()')
            expect(control).to_have_value('9007199254740993.125')
            page.locator('#main select').filter(has=page.locator('option[value="SECOND::"]')).select_option('SECOND::')
            assert page.evaluate("state.challengeSourceEdits['GOAL|0|1'].index") == 1
            page.evaluate('''async()=>{window.__requests=[];await saveChallenges()}''')
            requests = page.evaluate("window.__requests.filter(row=>row.path==='/api/challenges/save')")
            assert len(requests) == 1
            assert requests[0]['body']['edits'] == [{'name': 'GOAL', 'index': 0, 'value': '9007199254740993.125',
                                                   'sources': [{'index': 1, 'base': 'SECOND', 'permutation': ''}]}]
            page.evaluate('''async()=>{
              const data=state.store.mine.challenges;
              data.goals[0].conditions[0].fields.ContextHash='TRAIN';
              data.allowedConditionValues=[{type:'CAIConditionGoalContext',field:'ContextHash',values:['TRAIN','WATER']}];
              state.store.vanilla.challenges=structuredClone(data);
              state.store.vanilla.challenges.goals[0].requirements[0].value='5';
              window.__responses['/api/challenges']=data;
              await renderChallenges();
            }''')
            condition = page.get_by_role('combobox', name='GOAL condition 0 ContextHash', exact=True)
            condition.select_option('WATER')
            assert page.evaluate("state.challengeConditionEdits['GOAL|0|ContextHash'].value") == 'WATER'
            page.evaluate("state.challengeSourceEdits={'GOAL|0|1':{index:1,base:'UNKNOWN',permutation:''}}")
            result = page.evaluate('''async()=>{window.__requests=[];try{await saveChallenges();return 'saved'}catch(error){return error.message}}''')
            assert 'challenge score source' in result
            assert page.evaluate('window.__requests.length') == 0
            assert page.evaluate("state.challengeConditionEdits['GOAL|0|ContextHash'].value") == 'WATER'
            page.evaluate("state.challengeSourceEdits={};state.challengeConditionEdits['GOAL|0|ContextHash'].value='UNKNOWN'")
            result = page.evaluate('''async()=>{window.__requests=[];try{await saveChallenges();return 'saved'}catch(error){return error.message}}''')
            assert 'challenge condition' in result
            assert page.evaluate('window.__requests.length') == 0
            condition.select_option('TRAIN')
            condition.select_option('WATER')
            page.evaluate('''async()=>{window.__requests=[];await saveChallenges()}''')
            requests = page.evaluate("window.__requests.filter(row=>row.path==='/api/challenges/save')")
            assert len(requests) == 1
            assert requests[0]['body']['conditions'] == [{'goal': 'GOAL', 'index': 0,
                'type': 'CAIConditionGoalContext', 'field': 'ContextHash', 'value': 'WATER'}]
            assert page.evaluate('Object.keys(state.challengeConditionEdits).length') == 0
            page.evaluate("async()=>{state.store.mine.challenges.goals[0].requirements[0].readonly=true;await renderChallenges()}")
            expect(control).to_be_disabled()
            before = page.evaluate('JSON.stringify(state.challengeEdits)')
            page.get_by_text('V 5', exact=True).click()
            assert page.evaluate('JSON.stringify(state.challengeEdits)') == before
            page.screenshot(path=str(tmp_path / 'readonly-challenge.png'), full_page=True)
            page.evaluate("async()=>{state.ds='vanilla';await renderChallenges()}")
            expect(control).to_be_disabled()
            for select in page.locator('#main select').all():
                expect(select).to_be_disabled()
            assert errors == []
        finally:
            browser.close()
