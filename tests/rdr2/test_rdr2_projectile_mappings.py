"""Inactive cartridge speed support exposes only real read-only mappings."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from playwright.sync_api import sync_playwright,expect
from rdr2_browser_check import document
from plugins.rdr2 import server as s
from test_rdr2_weapon_batch_publication import weapon
from test_rdr2_catalog_numeric_validation import fixture,snapshot


def test_projectile_mappings_are_readonly_without_settings_or_multiplier_claims(weapon,monkeypatch,tmp_path_factory):
    root,path,_,_=weapon
    path.write_bytes(path.read_bytes().replace(b'Variants',b'DamageModes').replace(b'<Name>WEAPON_TEST</Name>',b'<Name>WEAPON_TEST</Name><FireType>PROJECTILE</FireType>'))
    s._files.clear()
    def forbidden(*args,**kwargs):raise AssertionError('inactive runtime consulted settings or multipliers')
    monkeypatch.setattr(s,'get_gameplay_settings',forbidden);monkeypatch.setattr(s,'_load_speed_multipliers',forbidden)
    legacy=root/'legacy-multipliers.csv';legacy.write_text('unread unsupported previous data')
    monkeypatch.setattr(s,'PROJECTILE_SPEED_FILE',legacy)
    before=snapshot(root)
    result=s.get_projectile_speeds()
    assert result['runtimeSwitching'] is False and result['cartridges']==[{'ammo':'AMMO_TEST','uses':[{'weapon':'WEAPON_TEST','damageMode':'MODE','fireType':'PROJECTILE'}]}]
    assert 'baseSpeed' not in result and 'multiplier' not in result['cartridges'][0] and 'effectiveSpeed' not in result['cartridges'][0]
    assert snapshot(root)==before
    http=s.create_server(0);worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
    screenshots=tmp_path_factory.mktemp('projectile-mapping-visual')
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
                    assert endpoint in {'/api/weapons','/api/weapons/projectile-speeds'}
                    requests.append(endpoint)
                    with urlopen(f'http://127.0.0.1:{http.server_port}'+endpoint,timeout=5) as response:return json.load(response)
                page.expose_binding('readMappings',read)
                page.evaluate('''async()=>{
                  const original=window.fetch;
                  window.fetch=async(url,options)=>{
                    const endpoint=new URL(url,document.baseURI).pathname;
                    if(['/api/weapons','/api/weapons/projectile-speeds'].includes(endpoint)){
                      if(options?.method&&options.method!=='GET')throw Error('Mapping view attempted a write');
                      return new Response(JSON.stringify(await readMappings(endpoint)),{headers:{'Content-Type':'application/json'}});
                    }return original(url,options);
                  };
                  state.tab='weapons';state.filters.weaponSection='velocity';state.weaponData.vanilla={weapons:[],ammo:[]};state.weaponReference={weapons:[],ammo:[]};
                  await render();
                }''')
                expect(page.get_by_role('table',name='Cartridge mappings',exact=True).get_by_text('AMMO_TEST',exact=True)).to_be_visible()
                assert page.locator('#main input[type=number],#main select').count()==0
                search=page.get_by_role('searchbox',name='Search cartridges or weapons',exact=False)
                assert page.locator('#main input:not(:disabled)').count()==1 and search.is_enabled()
                assert 'MODE' in page.locator('#main input').evaluate_all('elements=>elements.map(element=>element.value)')
                assert 'PROJECTILE' in page.locator('#main input').evaluate_all('elements=>elements.map(element=>element.value)')
                help_text=page.locator('#main .lex-info-help').first.get_attribute('aria-label')
                assert '1 cartridge.' in help_text and 'unavailable' in help_text
                assert page.get_by_text('Multiplier (inactive)',exact=True).count()==0
                assert page.get_by_text('Current runtime speed',exact=True).count()==0
                page.screenshot(path=str(screenshots/'projectile-mappings.png'),full_page=True)
                search.fill('MISSING')
                expect(page.get_by_text('No cartridge mappings match the filter.',exact=True)).to_be_visible()
                search.fill('')
                expect(page.get_by_role('table',name='Cartridge mappings',exact=True).get_by_text('AMMO_TEST',exact=True)).to_be_visible()
                assert snapshot(root)==before and not errors,errors
                assert requests==['/api/weapons','/api/weapons/projectile-speeds']
            finally:browser.close()
        request=Request(f'http://127.0.0.1:{http.server_port}/api/weapons/projectile-speeds/save',data=json.dumps({'entries':[{'ammo':'AMMO_TEST','multiplier':2}]}).encode(),headers={'Content-Type':'application/json'})
        try:urlopen(request,timeout=5);raise AssertionError('inactive runtime save succeeded')
        except HTTPError as error:assert error.code==400 and 'not installed' in json.load(error)['error']
        assert snapshot(root)==before
    finally:http.shutdown();http.server_close();worker.join()
