"""Weapon scalar drafts and Save ordering against the real isolated service."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright, expect
from rdr2_browser_check import document
from plugins.rdr2 import server as s
from test_rdr2_weapon_batch_publication import weapon
from test_rdr2_catalog_numeric_validation import fixture, snapshot


def test_weapon_drafts_validation_save_reload_and_locks(weapon,tmp_path,monkeypatch):
    root,path,install,entry=weapon
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
                def real_weapon(_source,endpoint,body=None):
                    assert endpoint in {'/api/weapons','/api/weapons/validate','/api/weapons/save'}
                    requests.append((endpoint,body))
                    request=Request(f'http://127.0.0.1:{http.server_port}'+endpoint,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
                    try:
                        with urlopen(request,timeout=5) as response:return {'status':response.status,'body':json.load(response)}
                    except HTTPError as error:return {'status':error.code,'body':json.load(error)}
                page.expose_binding('realWeapon',real_weapon)
                page.evaluate('''async()=>{
                  const original=window.fetch;
                  window.fetch=async(url,options)=>{
                    const endpoint=new URL(url,document.baseURI).pathname;
                    if(['/api/weapons','/api/weapons/validate','/api/weapons/save'].includes(endpoint)){
                      const result=await realWeapon(endpoint,options?.body?JSON.parse(options.body):null);
                      return new Response(JSON.stringify(result.body),{status:result.status,headers:{'Content-Type':'application/json'}});
                    }return original(url,options);
                  };
                  state.tab='weapons';state.filters.weapon='WEAPON_TEST';state.filters.weaponSection='weapons';state.filters.weaponFieldQ='Damage';
                  state.weaponData.vanilla={weapons:[],ammo:[]};state.weaponReference={weapons:[],ammo:[]};
                  window.__saveFailures=[];window.showSaveFailure=e=>__saveFailures.push(e.message);
                  await renderWeapons();
                }''')
                def damage():return page.get_by_role('spinbutton',name='Damage',exact=True)
                expect(damage()).to_have_value('37')
                assert page.locator('.lex-master input[type=number]').count()==0
                before=snapshot(root);count=len(requests)
                damage().fill('')
                assert not damage().evaluate('e=>e.checkValidity()')
                page.evaluate('renderWeapons()');expect(damage()).to_have_value('')
                assert 'finite' in page.evaluate("async()=>{try{await saveWeapons();return ''}catch(e){return e.message}}")
                page.evaluate("state.alcoholEdits={CONSUMABLE_RUM:0.25};state.localizationEdits={LABEL:'pending'};state.filters.weapon='OTHER';renderWeapons()")
                page.evaluate('saveAllChanges()')
                page.wait_for_function("__saveFailures.some(error=>error.includes('finite'))")
                assert len(requests)==count and snapshot(root)==before
                assert page.evaluate("state.weaponEdits['weapons|WEAPON_TEST']['weapons|WEAPON_TEST|1'].value")==''
                assert page.evaluate('state.alcoholEdits.CONSUMABLE_RUM')==0.25
                assert page.evaluate('state.localizationEdits.LABEL')=='pending'
                page.evaluate("state.alcoholEdits={};state.localizationEdits={};state.filters.weapon='WEAPON_TEST';renderWeapons()")
                damage().fill('0.125');page.evaluate('renderWeapons()');expect(damage()).to_have_value('0.125')
                damage().fill('9007199254740993');page.evaluate('renderWeapons()');expect(damage()).to_have_value('9007199254740993')
                original_install=install.read_bytes();install.write_text('<Install/>')
                invalid_snapshot=snapshot(root)
                assert 'Resources' in page.evaluate("async()=>{try{await saveWeapons();return ''}catch(e){return e.message}}")
                assert snapshot(root)==invalid_snapshot
                expect(damage()).to_have_value('9007199254740993')
                install.write_bytes(original_install)
                original_commit=s._commit_xml_roots
                def fail(*args,**kwargs):raise OSError('injected weapon publication failure')
                monkeypatch.setattr(s,'_commit_xml_roots',fail)
                assert 'injected' in page.evaluate("async()=>{try{await saveWeapons();return ''}catch(e){return e.message}}")
                assert snapshot(root)==before
                expect(damage()).to_have_value('9007199254740993')
                monkeypatch.setattr(s,'_commit_xml_roots',original_commit)
                page.evaluate('saveWeapons()')
                page.wait_for_function("Object.keys(state.weaponEdits['weapons|WEAPON_TEST']||{}).length===0&&state.weaponData.mine")
                page.evaluate('renderWeapons()');expect(damage()).to_have_value('9007199254740993')
                saves=[body for endpoint,body in requests if endpoint.endswith('/save')]
                validations=[body for endpoint,body in requests if endpoint.endswith('/validate')]
                assert saves[-1]==validations[-1]
                assert s.parse_with_comments(path).findall('Item')[0].find('Damage').get('value')=='9007199254740993'
                page.evaluate("state.filters.weaponFieldQ='Enabled';renderWeapons()")
                enabled=page.get_by_role('checkbox',name='Enabled',exact=True)
                enabled.check();enabled.uncheck()
                assert not page.evaluate("Object.keys(state.weaponEdits['weapons|WEAPON_TEST']).length")
                enabled.check();page.evaluate('saveWeapons()')
                page.wait_for_function("Object.keys(state.weaponEdits['weapons|WEAPON_TEST']||{}).length===0&&state.weaponData.mine")
                expect(page.get_by_role('checkbox',name='Enabled',exact=True)).to_be_checked()
                page.evaluate("state.filters.weaponFieldQ='Opaque';renderWeapons()")
                expect(page.locator('.weapon-value')).to_be_disabled()
                page.evaluate("state.filters.weaponFieldQ='';renderWeapons()")
                page.locator('details').evaluate_all('elements=>elements.forEach(element=>element.open=true)')
                page.screenshot(path=str(tmp_path/'weapon-controls.png'),full_page=True)
                page.evaluate("state.ds='vanilla';state.weaponData.vanilla=structuredClone(state.weaponData.mine);state.filters.weaponFieldQ='Damage';renderWeapons()")
                expect(damage()).to_be_disabled()
                count=len(requests);page.evaluate('saveWeapons()');assert len(requests)==count
                assert not errors,errors
            finally:browser.close()
    finally:http.shutdown();http.server_close();worker.join()
