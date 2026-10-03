"""The real shell toggle validates before direct/global unrelated writers."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from playwright.sync_api import sync_playwright,expect
from rdr2_browser_check import document
from plugins.rdr2 import server as s
from test_rdr2_shell_vfx_publication import shell,snapshot


def test_shell_toggle_real_validation_save_reload_and_failure(shell,tmp_path,monkeypatch):
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
                def call(_source,endpoint,body):
                    assert endpoint in {'/api/weapons','/api/weapons/validate','/api/weapons/save','/api/weapons/shell-vfx/validate','/api/weapons/shell-vfx/save'}
                    requests.append((endpoint,body))
                    request=Request(f'http://127.0.0.1:{http.server_port}'+endpoint,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
                    try:
                        with urlopen(request,timeout=5) as response:return {'status':response.status,'body':json.load(response)}
                    except HTTPError as error:return {'status':error.code,'body':json.load(error)}
                page.expose_binding('realShell',call)
                page.evaluate('''async()=>{
                  const original=window.fetch;
                  window.fetch=async(url,options)=>{
                    const endpoint=new URL(url,document.baseURI).pathname;
                    if(endpoint.startsWith('/api/weapons')&&endpoint!=='/api/weapons-reference'){
                      const result=await realShell(endpoint,options?.body?JSON.parse(options.body):null);
                      return new Response(JSON.stringify(result.body),{status:result.status,headers:{'Content-Type':'application/json'}});
                    }return original(url,options);
                  };
                  state.tab='weapons';state.filters.weaponSection='weapons';state.filters.weapon='WEAPON_ALPHA_0';
                  state.weaponData.vanilla={weapons:[],ammo:[]};state.weaponReference={weapons:[],ammo:[]};
                  window.__saveFailures=[];window.showSaveFailure=e=>__saveFailures.push(e.message);
                  await render();
                }''')
                toggle=page.get_by_role('checkbox',name='Blank vanilla shell VFX (collectible casings)',exact=True)
                expect(toggle).to_be_checked()
                toggle.uncheck();toggle.check()
                assert page.evaluate('state.weaponShellVfxEdit') is None
                toggle.uncheck();page.evaluate('renderWeapons()');expect(toggle).not_to_be_checked()
                install=shell.mine/'install.xml';original=install.read_bytes();install.write_text('<LML/>')
                before=snapshot(shell.mine)
                page.evaluate("state.localizationEdits={LABEL:'pending'};state.alcoholEdits={CONSUMABLE_RUM:0.25}")
                assert 'Resources' in page.evaluate("async()=>{try{await saveWeapons();return ''}catch(e){return e.message}}")
                page.evaluate("document.querySelector('#main').innerHTML='';saveAllChanges()")
                page.wait_for_function("__saveFailures.some(error=>error.includes('Resources'))")
                assert snapshot(shell.mine)==before
                assert page.evaluate('state.weaponShellVfxEdit') is False
                assert page.evaluate('state.localizationEdits.LABEL')=='pending'
                assert page.evaluate('state.alcoholEdits.CONSUMABLE_RUM')==0.25
                assert not page.evaluate("__requests.some(row=>row.path==='/api/localization/save'||row.path==='/api/alcohol-strengths/save')")
                install.write_bytes(original)
                page.evaluate("async()=>{state.localizationEdits={};state.alcoholEdits={};await renderWeapons()}")
                before=snapshot(shell.mine);actual=s._commit_xml_roots
                def fail(*args,**kwargs):raise OSError('injected shell publication failure')
                monkeypatch.setattr(s,'_commit_xml_roots',fail)
                assert 'injected' in page.evaluate("async()=>{try{await saveWeapons();return ''}catch(e){return e.message}}")
                assert snapshot(shell.mine)==before and page.evaluate('state.weaponShellVfxEdit') is False
                monkeypatch.setattr(s,'_commit_xml_roots',actual)
                page.evaluate('saveWeapons()');page.wait_for_function('state.weaponShellVfxEdit===null&&state.weaponData.mine')
                expect(toggle).not_to_be_checked()
                assert s.get_weapon_shell_vfx_status()['blank']==0
                validations=[body for endpoint,body in requests if endpoint=='/api/weapons/shell-vfx/validate']
                saves=[body for endpoint,body in requests if endpoint=='/api/weapons/shell-vfx/save']
                assert saves[-1]==validations[-1]=={'blanked':False}
                toggle.check();expect(page.locator('#global-save')).to_be_enabled();page.locator('#global-save').click();page.wait_for_function('state.weaponShellVfxEdit===null')
                page.evaluate('renderWeapons()');expect(toggle).to_be_checked()
                assert s.get_weapon_shell_vfx_status()['blanked']
                page.screenshot(path=str(tmp_path/'shell-vfx-controls.png'),full_page=True)
                page.evaluate("async()=>{state.ds='vanilla';state.weaponData.vanilla=structuredClone(state.weaponData.mine);await renderWeapons()}")
                expect(toggle).to_be_disabled()
                before=len(requests);page.evaluate('saveWeaponShellVfx()');assert len(requests)==before
                assert not errors,errors
            finally:browser.close()
    finally:http.shutdown();http.server_close();worker.join()
