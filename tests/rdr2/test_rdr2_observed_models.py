"""Read-only MobProbe evidence uses the production shared master/detail view."""
import json
import threading
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect
from rdr2_browser_check import document
from plugins.rdr2 import server as s
from test_rdr2_mobs_batch_validation import mobs
from test_rdr2_catalog_numeric_validation import fixture, snapshot


def test_observed_models_distinguish_candidates_without_writes(mobs,tmp_path_factory,monkeypatch):
    root,_,sources,_=mobs
    sources[1].write_text('<Root><HealthConfig>'+''.join(f'<Item key="PROFILE_{name}"><DefaultEnergy value="{hp}"/><DefaultArmour value="{armour}"/></Item>' for name,hp,armour in [('A',10,1),('B',10,2),('C',17,3)])+'</HealthConfig></Root>')
    roster=root/'roster.csv';roster.write_text('model,hash,group\nMODEL_A,1,gang\nMODEL_C,2,gang\nMODEL_UNKNOWN,3,gang\nMODEL_UNSEEN,4,gang\nOTHER_GROUP,5,ambient\n')
    probe=root/'probe.csv';probe.write_text('model,max_health,status\nMODEL_A,10,ok\nMODEL_C,17,ok\nMODEL_UNKNOWN,123,ok\nOTHER_GROUP,10,ok\n')
    monkeypatch.setattr(s,'MOB_ROSTER_FILE',roster);monkeypatch.setattr(s,'MOB_PROBE_FILE',probe);monkeypatch.setattr(s,'MOB_DISCOVERED_FILE',root/'discovered.csv')
    before=snapshot(root)
    screenshots=tmp_path_factory.mktemp('observed-models-visual')
    http=s.create_server(0);worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
    try:
        with sync_playwright() as play:
            browser=play.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1400,'height':1100})
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.route('**/*',lambda route:route.abort())
                page.set_content(document().replace('<head>','<head><base href="https://lexeditor.test/">',1))
                page.wait_for_function('!state.booting&&state.catalog?.items?.length')
                page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
                requests=[]
                def read(_source,endpoint):
                    assert endpoint in {'/api/mobs','/api/mob-models'}
                    requests.append(endpoint)
                    with urlopen(f'http://127.0.0.1:{http.server_port}'+endpoint,timeout=5) as response:return json.load(response)
                page.expose_binding('readModels',read)
                page.evaluate('''async()=>{
                  const original=window.fetch;
                  window.fetch=async(url,options)=>{
                    const endpoint=new URL(url,document.baseURI).pathname;
                    if(['/api/mobs','/api/mob-models'].includes(endpoint)){
                      if(options?.method&&options.method!=='GET')throw Error('Observed view tried to write');
                      return new Response(JSON.stringify(await readModels(endpoint)),{headers:{'Content-Type':'application/json'}});
                    }return original(url,options);
                  };
                  state.tab='mobs';state.filters.mobView='models';state.filters.mobModelGroup='gang';state.filters.mobModelSelected='MODEL_A';
                  await render();
                }''')
                table=page.get_by_role('table',name='Mob models',exact=True)
                expect(table.get_by_text('MODEL_A',exact=True)).to_be_visible()
                assert table.get_by_text('MODEL_UNSEEN',exact=True).count()==0
                assert table.get_by_text('OTHER_GROUP',exact=True).count()==0
                assert table.locator('input,select').count()==0
                assert page.locator('#main input:not(:disabled),#main select:not(:disabled)').count()==0
                assert page.locator('#main .lex-notice').count()==0
                assert 'MobProbe lists 4 models.' in page.locator('#main .lex-info-help').first.get_attribute('aria-label')
                assert 'does not prove' in page.locator('#main .lex-info-help').first.get_attribute('aria-label')
                for name,armour in [('A','1'),('B','2')]:
                    section=page.locator('.lex-detail-section').filter(has_text=f'Candidate: PROFILE_{name}')
                    expect(section).to_be_visible()
                    assert armour in section.locator('input').evaluate_all('elements=>elements.map(element=>element.value)')
                page.screenshot(path=str(screenshots/'observed-models.png'),full_page=True)
                table.get_by_text('MODEL_C',exact=True).click()
                expect(page.get_by_text('Candidate: PROFILE_C',exact=True)).to_be_visible()
                assert page.get_by_text('Candidate: PROFILE_A',exact=True).count()==0
                table.get_by_text('MODEL_UNKNOWN',exact=True).click()
                assert 'No exact HP match' in page.locator('#main input').evaluate_all('elements=>elements.map(element=>element.value)')
                page.evaluate("async()=>{state.filters.mobModelQ='MISSING';await renderMobs()}")
                expect(page.get_by_text('No observed models match this group and filter.',exact=True)).to_be_visible()
                page.evaluate("async()=>{state.filters.mobModelQ='';state.mobModels.probeAvailable=false;await renderMobs()}")
                expect(page.get_by_text('No model observations are available. Run MobProbe in the game to collect them.',exact=True)).to_be_visible()
                assert requests==['/api/mobs','/api/mob-models']
                assert snapshot(root)==before and not errors,errors
            finally:browser.close()
    finally:http.shutdown();http.server_close();worker.join()
