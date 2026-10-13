"""Production AI controls use real validation/save APIs and retain raw drafts."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright, expect
from rdr2_browser_check import document
from plugins.rdr2 import server as s
from test_rdr2_ai_batch_validation import ai
from test_rdr2_catalog_numeric_validation import fixture, snapshot


def test_ai_controls_preflight_save_reload_and_readonly(ai, tmp_path):
    root, path, source, install = ai
    http=s.create_server(0)
    worker=threading.Thread(target=http.serve_forever,daemon=True)
    worker.start()
    try:
        with sync_playwright() as play:
            browser=play.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1400,'height':1100})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.route('**/*',lambda route:route.abort())
                page.set_content(document().replace('<head>','<head><base href="https://lexeditor.test/">',1))
                page.wait_for_function('!state.booting&&state.catalog?.items?.length')
                page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
                requests=[]
                def real_ai(_source,endpoint,body=None):
                    assert endpoint in {f'/api/ai/{s.PED_PERCEPTION_FILE}'+suffix for suffix in ['', '/save', '/validate']}
                    requests.append((endpoint,body))
                    request=Request(f'http://127.0.0.1:{http.server_port}'+endpoint,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
                    try:
                        with urlopen(request,timeout=5) as response:return {'status':response.status,'body':json.load(response)}
                    except HTTPError as error:return {'status':error.code,'body':json.load(error)}
                page.expose_binding('realAI',real_ai)
                page.evaluate('''async()=>{
                  const original=window.fetch;
                  window.fetch=async(url,options)=>{
                    const endpoint=new URL(url,document.baseURI).pathname;
                    if(endpoint.startsWith('/api/ai/')){
                      const result=await realAI(endpoint,options?.body?JSON.parse(options.body):null);
                      return new Response(JSON.stringify(result.body),{status:result.status,headers:{'Content-Type':'application/json'}});
                    }
                    return original(url,options);
                  };
                  state.datamap={sections:[]};state.tab='ai';state.filters.aiLayer='profiles';state.filters.aiFile='ai/pedperception.meta';
                  state.aiRefs={'ai/pedperception.meta':{fields:[]}};
                  state.filters.aiSelected={'ai/pedperception.meta':'1'};
                  window.__saveFailures=[];window.showSaveFailure=e=>__saveFailures.push(e.message);
                  await renderAI();
                }''')
                def amount():return page.get_by_role('spinbutton',name='Amount',exact=True)
                assert page.locator('.ai-field-table input,.ai-field-table select').count()==0
                expect(amount()).to_have_value('1')
                amount().fill('')
                assert not amount().evaluate('e=>e.checkValidity()')
                page.evaluate('renderAI()')
                expect(amount()).to_have_value('')
                before=len(requests)
                assert 'finite' in page.evaluate("async()=>{try{await saveAI();return ''}catch(e){return e.message}}")
                page.evaluate("state.alcoholEdits={CONSUMABLE_RUM:0.25};document.querySelector('#main').innerHTML='';saveAllChanges()")
                assert len(requests)==before
                assert page.evaluate("state.aiEdits['ai/pedperception.meta']['1'].value") == ''
                assert page.evaluate('state.alcoholEdits.CONSUMABLE_RUM')==0.25
                page.evaluate('state.alcoholEdits={};renderAI()')
                amount().fill('0.125')
                page.evaluate('renderAI()')
                expect(amount()).to_have_value('0.125')
                assert page.evaluate("state.aiEdits['ai/pedperception.meta']['1'].value")=='0.125'
                amount().fill('9007199254740993')
                before=snapshot(root)
                original_install=install.read_bytes()
                install.write_text('<Install/>')
                assert 'Resources' in page.evaluate("async()=>{try{await saveAI();return ''}catch(e){return e.message}}")
                assert not path.exists()
                assert page.evaluate("state.aiEdits['ai/pedperception.meta']['1'].value")=='9007199254740993'
                page.evaluate("state.alcoholEdits={CONSUMABLE_RUM:0.25};document.querySelector('#main').innerHTML='';saveAllChanges()")
                page.wait_for_function("__saveFailures.some(error=>error.includes('Resources'))")
                assert not page.evaluate("window.__requests.some(row=>row.path==='/api/alcohol/save')")
                assert page.evaluate('state.alcoholEdits.CONSUMABLE_RUM')==0.25
                assert not path.exists()
                page.evaluate('state.alcoholEdits={}')
                install.write_bytes(original_install)
                assert snapshot(root)==before
                page.evaluate('saveAI()')
                page.wait_for_function("Object.keys(state.aiEdits['ai/pedperception.meta']).length===0")
                page.evaluate("async()=>{delete state.aiData['ai/pedperception.meta'];await renderAI()}")
                expect(amount()).to_have_value('9007199254740993')
                writes=[body for endpoint,body in requests if endpoint.endswith('/save')]
                validations=[body for endpoint,body in requests if endpoint.endswith('/validate')]
                assert writes[-1]==validations[-1]=={'edits':[{'path':[1],'kind':'attr','value':'9007199254740993'}]}
                assert s.parse_with_comments(path).find('Amount').get('value')=='9007199254740993'
                page.locator('.ai-field-table').get_by_text('Enabled',exact=True).click()
                page.get_by_role('checkbox',name='Enabled',exact=True).uncheck()
                page.get_by_role('checkbox',name='Enabled',exact=True).check()
                assert page.evaluate("Object.keys(state.aiEdits['ai/pedperception.meta']).length")==0
                page.get_by_role('checkbox',name='Enabled',exact=True).uncheck()
                page.evaluate('saveAI()')
                page.wait_for_function("Object.keys(state.aiEdits['ai/pedperception.meta']).length===0")
                page.evaluate("async()=>{delete state.aiData['ai/pedperception.meta'];await renderAI()}")
                expect(page.get_by_role('checkbox',name='Enabled',exact=True)).not_to_be_checked()
                page.locator('.ai-field-table').get_by_text('Mode',exact=True).first.click()
                page.get_by_role('combobox',name='Mode',exact=True).select_option('B')
                page.evaluate('saveAI()')
                page.wait_for_function("Object.keys(state.aiEdits['ai/pedperception.meta']).length===0")
                page.evaluate("async()=>{delete state.aiData['ai/pedperception.meta'];await renderAI()}")
                expect(page.get_by_role('combobox',name='Mode',exact=True)).to_have_value('B')
                page.locator('.ai-field-table').get_by_text('Opaque',exact=True).click()
                expect(page.get_by_role('textbox',name='Value',exact=True)).to_be_disabled()
                page.screenshot(path=str(tmp_path/'ai-controls.png'),full_page=True)
                page.evaluate("async()=>{state.aiData['ai/pedperception.meta'].fields[0].value='NaN';state.filters.aiSelected['ai/pedperception.meta']='1';await renderAI()}")
                expect(page.get_by_role('textbox',name='Value',exact=True)).to_be_disabled()
                expect(page.get_by_role('textbox',name='Value',exact=True)).to_have_value('NaN')
                page.evaluate("delete state.aiData['ai/pedperception.meta']")
                page.evaluate("async()=>{state.ds='vanilla';state.filters.aiSelected['ai/pedperception.meta']='1';await renderAI()}")
                expect(amount()).to_be_disabled()
                before=len(requests)
                page.evaluate('saveAI()')
                assert len(requests)==before
                assert not errors,errors
            finally:browser.close()
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
