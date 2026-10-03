"""Mobs uses shared detail controls and real validation/publication endpoints."""
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright, expect
from rdr2_browser_check import document
from plugins.rdr2 import server as s
from test_rdr2_mobs_batch_validation import mobs
from test_rdr2_catalog_numeric_validation import fixture, snapshot


def test_mobs_controls_real_save_reload_failure_and_hidden_preflight(mobs,tmp_path,monkeypatch):
    root,paths,_,install=mobs
    http=s.create_server(0)
    worker=threading.Thread(target=http.serve_forever,daemon=True)
    worker.start()
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
                def real_mobs(_source,endpoint,body=None):
                    assert endpoint in {'/api/mobs','/api/mobs/validate','/api/mobs/save'}
                    requests.append((endpoint,body))
                    request=Request(f'http://127.0.0.1:{http.server_port}'+endpoint,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
                    try:
                        with urlopen(request,timeout=5) as response:return {'status':response.status,'body':json.load(response)}
                    except HTTPError as error:return {'status':error.code,'body':json.load(error)}
                page.expose_binding('realMobs',real_mobs)
                page.evaluate('''async()=>{
                  const original=window.fetch;
                  window.fetch=async(url,options)=>{
                    const endpoint=new URL(url,document.baseURI).pathname;
                    if(endpoint==='/api/mobs'||endpoint.startsWith('/api/mobs/')){
                      const result=await realMobs(endpoint,options?.body?JSON.parse(options.body):null);
                      return new Response(JSON.stringify(result.body),{status:result.status,headers:{'Content-Type':'application/json'}});
                    }
                    return original(url,options);
                  };
                  state.tab='mobs';state.filters.mobView='archetypes';state.filters.mobLayer='combat';state.filters.mobGroup='humans';state.mobs=null;
                  window.__saveFailures=[];window.showSaveFailure=e=>__saveFailures.push(e.message);
                  await renderMobs();
                }''')
                def accuracy():return page.get_by_role('spinbutton',name='GANG_FIXTURE Accuracy',exact=True)
                expect(accuracy()).to_have_value('1')
                assert page.locator('.mob-table input,.mob-table select').count()==0
                assert page.get_by_role('combobox',name='GANG_FIXTURE Name',exact=True).count()==0
                accuracy().fill('')
                assert not accuracy().evaluate('e=>e.checkValidity()')
                page.evaluate('renderMobs()');expect(accuracy()).to_have_value('')
                before=len(requests)
                assert 'finite' in page.evaluate("async()=>{try{await saveMobs();return ''}catch(e){return e.message}}")
                page.evaluate("state.alcoholEdits={CONSUMABLE_RUM:0.25};document.querySelector('#main').innerHTML='';saveAllChanges()")
                assert len(requests)==before
                assert page.evaluate("state.mobEdits['combat|1.1.1'].value")==''
                assert page.evaluate('state.alcoholEdits.CONSUMABLE_RUM')==0.25
                page.evaluate("async()=>{state.alcoholEdits={};await renderMobs()}")
                accuracy().fill('0.125')
                page.evaluate('renderMobs()');expect(accuracy()).to_have_value('0.125')
                accuracy().fill('9007199254740993')
                page.get_by_role('checkbox',name='GANG_FIXTURE Enabled',exact=True).uncheck()
                page.get_by_role('checkbox',name='GANG_FIXTURE Enabled',exact=True).check()
                assert page.evaluate("Object.keys(state.mobEdits)")==['combat|1.1.1']
                page.get_by_role('checkbox',name='GANG_FIXTURE Enabled',exact=True).uncheck()
                page.get_by_role('combobox',name='GANG_FIXTURE Ref',exact=True).first.select_option('B')
                page.evaluate("async()=>{state.filters.mobLayer='health';state.filters.mobGroup='other';await renderMobs()}")
                energy=page.get_by_role('spinbutton',name='FIXTURE Energy',exact=True)
                energy.fill('12.3456789')
                before=snapshot(root)
                old_loader=install.read_bytes();install.write_text('<Install/>')
                assert 'Resources' in page.evaluate("async()=>{try{await saveMobs();return ''}catch(e){return e.message}}")
                page.evaluate("state.alcoholEdits={CONSUMABLE_RUM:0.25};document.querySelector('#main').innerHTML='';saveAllChanges()")
                page.wait_for_function("__saveFailures.some(error=>error.includes('Resources'))")
                assert not page.evaluate("window.__requests.some(row=>row.path==='/api/alcohol/save')")
                assert page.evaluate('state.alcoholEdits.CONSUMABLE_RUM')==0.25
                assert not any(path.exists() for path in paths)
                install.write_bytes(old_loader)
                assert snapshot(root)==before
                page.evaluate("async()=>{state.alcoholEdits={};await renderMobs()}")
                original_replace=s.os.replace;failed=False
                def fail_health(source,target):
                    nonlocal failed
                    if Path(target)==paths[1] and not failed:
                        failed=True;raise OSError('injected mobs browser write failure')
                    return original_replace(source,target)
                monkeypatch.setattr(s.os,'replace',fail_health)
                assert 'injected mobs browser write failure' in page.evaluate("async()=>{try{await saveMobs();return ''}catch(e){return e.message}}")
                assert failed and snapshot(root)==before
                assert page.evaluate("state.mobEdits['combat|1.1.1'].value")=='9007199254740993'
                assert page.evaluate("state.mobEdits['health|1.0.0'].value")=='12.3456789'
                expect(energy).to_have_value('12.3456789')
                page.evaluate('saveMobs()')
                page.wait_for_function('Object.keys(state.mobEdits).length===0')
                page.evaluate("async()=>{state.mobs=null;await renderMobs()}")
                expect(energy).to_have_value('12.3456789')
                bodies=[body for endpoint,body in requests if endpoint.endswith('/save')]
                validations=[body for endpoint,body in requests if endpoint.endswith('/validate')]
                assert bodies[-1]==validations[-1]
                assert len(bodies[-1]['edits'])==4
                assert s.parse_with_comments(paths[0]).find('.//Accuracy').get('value')=='9007199254740993'
                assert s.parse_with_comments(paths[1]).find('.//Energy').get('value')=='12.3456789'
                page.evaluate("async()=>{state.filters.mobLayer='combat';state.filters.mobGroup='humans';await renderMobs()}")
                expect(accuracy()).to_have_value('9007199254740993')
                expect(page.get_by_role('checkbox',name='GANG_FIXTURE Enabled',exact=True)).not_to_be_checked()
                expect(page.get_by_role('combobox',name='GANG_FIXTURE Ref',exact=True).first).to_have_value('B')
                expect(page.get_by_role('textbox',name='Opaque',exact=True)).to_be_disabled()
                page.locator('.mob-table').get_by_text('GANG_FIXTURE',exact=True).click()
                expect(accuracy()).to_have_value('9007199254740993')
                page.screenshot(path=str(tmp_path/'mobs-controls.png'),full_page=True)
                # Reuse one identity in every supported section: index paths,
                # not display names, must keep the five profiles independent.
                source=paths[1].read_bytes()
                extra=b''.join(f'<{section}><Item key="FIXTURE"><Energy value="{index+20}"/><Enabled>true</Enabled></Item></{section}>'.encode() for index,section in enumerate(s.PEDHEALTH_SECTIONS[1:]))
                paths[1].write_bytes(source.replace(b'</Root>',extra+b'</Root>'))
                s._files.clear()
                page.evaluate("async()=>{state.mobs=null;state.filters.mobLayer='health';state.filters.mobGroup='other';await renderMobs()}")
                selector=page.get_by_role('combobox',name='Section',exact=True)
                assert selector.locator('option').count()==5
                expect(selector).to_have_value('HealthConfig')
                for index,section in enumerate(s.PEDHEALTH_SECTIONS[1:]):
                    selector.select_option(section)
                    field=page.get_by_role('spinbutton',name='FIXTURE Energy',exact=True)
                    expect(field).to_have_value(str(index+20))
                    field.fill(f'{index+30}.125')
                selector.select_option('HealthConfig')
                expect(page.get_by_role('spinbutton',name='FIXTURE Energy',exact=True)).to_have_value('12.3456789')
                assert page.evaluate('Object.keys(state.mobEdits).length')==4
                page.evaluate('saveMobs()')
                page.wait_for_function('Object.keys(state.mobEdits).length===0')
                page.evaluate("async()=>{state.mobs=null;await renderMobs()}")
                for index,section in enumerate(s.PEDHEALTH_SECTIONS[1:]):
                    selector.select_option(section)
                    expect(page.get_by_role('spinbutton',name='FIXTURE Energy',exact=True)).to_have_value(f'{index+30}.125')
                    assert s.parse_with_comments(paths[1]).find(f'{section}/Item/Energy').get('value')==f'{index+30}.125'
                assert s.parse_with_comments(paths[1]).find('HealthConfig/Item/Energy').get('value')=='12.3456789'
                page.screenshot(path=str(tmp_path/'mobs-health-sections.png'),full_page=True)
                # Observed HP candidates always link to HealthConfig even if
                # the reader was last editing a resource section of that name.
                target=page.evaluate('''()=>{
                  const original=rdrHoverable;let spec;
                  rdrHoverable=value=>{spec=value;return document.createElement('span')};
                  const previous=navigate;let destination;
                  navigate=(tab,filters)=>destination={tab,filters};
                  try{mobArchetypeLink('health','FIXTURE');spec.activate();return destination;}
                  finally{rdrHoverable=original;navigate=previous;}
                }''')
                assert target['tab']=='mobs' and target['filters']['mobHealthSection']=='HealthConfig'
                page.evaluate("async()=>{state.filters.mobLayer='combat';state.filters.mobGroup='humans';await renderMobs()}")
                page.evaluate("async()=>{state.mobs.combat.records[0].fields.find(row=>row.field==='Accuracy').value='NaN';await renderMobs()}")
                expect(page.get_by_role('textbox',name='Accuracy',exact=True)).to_be_disabled()
                page.evaluate("async()=>{state.mobs=null;state.ds='vanilla';await renderMobs()}")
                expect(accuracy()).to_be_disabled()
                before=len(requests);page.evaluate('saveMobs()');assert len(requests)==before
                assert not errors,errors
            finally:browser.close()
    finally:
        http.shutdown();http.server_close();worker.join()
