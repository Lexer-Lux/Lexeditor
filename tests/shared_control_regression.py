"""Headless regressions for shared controls and troop source saves."""
import functools
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from global_browser_check import Handler, ThreadingHTTPServer, STUB
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from plugins.warband.troop_editor import troop_data, save_troops
from test_warband_troop_editor import SOURCE
OUT=Path(os.environ.get('LEXEDITOR_TEST_OUTPUT',str(Path(tempfile.gettempdir())/'lex-shared-review')))
OUT.mkdir(exist_ok=True,parents=True)
class Assets(Handler):
    def translate_path(self,path):
        if path.startswith('/warband/'):path='/games'+path
        return super().translate_path(path)

def main():
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Assets,directory=str(ROOT)))
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True)
   page=browser.new_page(viewport={'width':1440,'height':900});errors=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.add_init_script(STUB+"window.pywebview.api.github_repository=async()=>({repository:'Lexer-Lux/Lexeditor',login:'Lexer-Lux'});window.pywebview.api.open_plugin_repository=async id=>{window.__calls.push({openRepository:id});return{opened:true};};")
   # Blank's tabs are the component catalogue; its demonstration views are opened by name.
   page.goto(f'http://127.0.0.1:{server.server_port}/plugins/blank/editor.html')
   page.wait_for_selector('nav button[data-tab]');page.wait_for_timeout(400)
   page.locator('#plugin-data-map').click();page.wait_for_timeout(300)
   divider=page.locator('.lex-data-map-view .lex-panel-layout-divider')
   box=divider.bounding_box();x=box['x']+box['width']*.25;y=box['y']+box['height']/2
   page.mouse.move(x,y);page.mouse.down()
   for delta in (10,40,80,120,80,40,10,0,-40,0):
    page.mouse.move(x+delta,y);page.wait_for_timeout(40)
    moved=divider.bounding_box()['x']-box['x']
    assert abs(moved-delta)<2,{'pointer':delta,'divider':moved}
   page.mouse.up()
   page.evaluate("navigate('two')")
   page.evaluate("window.pywebview.api.ui_scale=async percent=>{window.__calls.push({scale:percent});return{percent};}")
   scale=page.get_by_role('slider',name='UI scale',exact=True)
   assert scale.get_attribute('min')=='50' and scale.get_attribute('max')=='150'
   for percent in (50,150,100):
    scale.fill(str(percent))
    assert page.locator('.lex-ui-scale output').inner_text()==f'{percent}%'
    assert page.evaluate('window.__calls.at(-1).scale')==percent
   calls_before=page.evaluate('window.__calls.filter(c=>c.scale!==undefined).length')
   bounds=scale.bounding_box()
   page.mouse.move(bounds['x']+bounds['width']/2,bounds['y']+bounds['height']/2)
   page.mouse.down();page.mouse.move(bounds['x']+bounds['width']-3,bounds['y']+bounds['height']/2,steps=6)
   assert page.evaluate('window.__calls.filter(c=>c.scale!==undefined).length')==calls_before
   assert page.locator('.lex-ui-scale output').inner_text()!='100%'
   page.mouse.up()
   assert page.evaluate('window.__calls.filter(c=>c.scale!==undefined).length')==calls_before+1
   scale.click(button='right')
   assert page.locator('.lex-ui-scale output').inner_text()=='100%'
   assert page.evaluate('window.__calls.at(-1).scale')==100
   assert page.evaluate("!document.dispatchEvent(new WheelEvent('wheel',{ctrlKey:true,deltaY:100,bubbles:true,cancelable:true}))")
   assert page.evaluate("document.dispatchEvent(new WheelEvent('wheel',{deltaY:100,bubbles:true,cancelable:true}))")
   # Restart is a developer control (issue #29): shown with Developer Mode on,
   # gone with it off.
   assert page.locator('#plugin-restart').is_visible()
   page.evaluate("dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{developerMode:false}}))")
   assert not page.locator('#plugin-restart').is_visible()
   page.evaluate("dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{developerMode:true}}))")
   assert page.locator('#plugin-restart').is_visible()
   assert page.get_by_role('button',name='Editable Table',exact=True).count()==0
   page.locator('#plugin-github').click(button='right');assert page.evaluate('window.__calls.some(row=>row.openRepository==="blank")')
   page.evaluate("navigate('three')");page.wait_for_timeout(400)
   divider=page.locator('.lex-panel-layout-divider:visible').first
   box=divider.bounding_box();start=divider.get_attribute('aria-valuenow')
   page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
   page.mouse.down();page.mouse.move(box['x']+100,box['y']+box['height']/2,steps=30);page.mouse.up()
   page.wait_for_timeout(200)
   assert not page.evaluate('document.body.classList.contains("lex-panel-layout-dragging")')
   assert divider.get_attribute('aria-valuenow')!=start
   assert divider.evaluate('e=>getComputedStyle(e,"::before").height')=='32px'
   divider.click(button='right');page.wait_for_timeout(200)
   field=page.locator('.lex-boolean-field').first;checkbox=field.locator('input[type=checkbox]')
   geometry=field.evaluate("""e=>{const box=e.querySelector('input[type=checkbox]').getBoundingClientRect(),arrow=e.querySelector('.lex-field-boolean-arrow').getBoundingClientRect();return{height:e.getBoundingClientRect().height,boxY:box.y+box.height/2,arrowY:arrow.y+arrow.height/2}}""")
   # Include the reserved reference row beneath the checkbox.
   assert geometry['height']<=48 and abs(geometry['boxY']-geometry['arrowY'])<=1,geometry
   before=field.bounding_box();checkbox.set_checked(not checkbox.is_checked());page.wait_for_timeout(250)
   assert abs(field.bounding_box()['height']-before['height'])<.5
   marks=field.locator('.lex-reference-values')
   assert marks.count()==1
   assert marks.evaluate('(e)=>e.scrollWidth<=e.clientWidth+2')
   assert field.locator('.lex-column-pin').bounding_box()['y']<checkbox.bounding_box()['y']
   text=field.locator('.lex-detail-field-label-text').bounding_box();arrow=field.locator('.lex-field-boolean-arrow').bounding_box();box=checkbox.bounding_box()
   assert arrow['x']-text['x']-text['width']>=12
   assert abs(box['x']-arrow['x']-arrow['width']-10)<.6
   page.screenshot(path=str(OUT/'three-panels.png'),animations='disabled')
   for width in (900,1600):
    page.set_viewport_size({'width':width,'height':900});page.wait_for_timeout(250)
    size=field.bounding_box()['height'];checkbox.set_checked(not checkbox.is_checked());page.wait_for_timeout(150)
    assert abs(field.bounding_box()['height']-size)<.5
    name=field.locator('.lex-detail-field-label-text').bounding_box()
    assert name['x']>=field.bounding_box()['x']
   page.set_viewport_size({'width':1440,'height':900});page.wait_for_timeout(250)
   positions=page.evaluate("""async()=>{
    const top=()=>[...document.querySelectorAll('.blank-table .lex-column-list-row')].slice(0,5).flatMap(e=>[e.getBoundingClientRect().top,e.querySelector('.lex-column-cell-content').getBoundingClientRect().top]);
    const samples=[top()];document.querySelector('.blank-table input[type=checkbox]').click();samples.push(top());
    for(let i=0;i<8;i++){await new Promise(requestAnimationFrame);samples.push(top());}
    return samples;
   }""")
   assert all(len(row)==len(positions[0]) and all(abs(a-b)<1 for a,b in zip(row,positions[0])) for row in positions),positions
   # A table toggle must not hide the new rows while their height is measured.
   page.locator('.blank-table input[type=checkbox]').first.click()
   assert page.locator('.blank-table .lex-column-list-row').evaluate_all('(rows)=>rows.every(r=>getComputedStyle(r).visibility!=="hidden")')
   page.keyboard.down('Control')
   assert page.locator('html').evaluate('(e)=>e.classList.contains("lex-control-held")')
   assert page.locator('#global-save').get_attribute('data-shortcut-key')=='S'
   assert page.locator('#plugin-data-map').get_attribute('data-shortcut-key')=='M'
   assert page.locator('#global-save svg').evaluate('(e)=>getComputedStyle(e).visibility')=='hidden'
   assert page.locator('nav button:not(.active) .lex-tab-shortcut').evaluate_all('(nodes)=>nodes.every(e=>getComputedStyle(e).visibility==="visible")')
   page.screenshot(path=str(OUT/'shortcut-keys.png'),animations='disabled')
   page.keyboard.press('m');page.keyboard.up('Control')
   assert page.locator('#plugin-data-map').evaluate('(e)=>e.classList.contains("active")')
   page.evaluate("navigate('one')");page.wait_for_timeout(400)
   # Parked on the brand, where no switch can ever sit; a point inside the
   # page lands on a switch whenever the layout shifts a few pixels.
   page.mouse.move(8,8)
   page.wait_for_timeout(180)
   rails=page.locator('.lex-toggle-rail')
   assert rails.count()>1
   assert rails.evaluate_all('nodes=>nodes.every(e=>getComputedStyle(e).opacity==="0")')
   flag=page.locator('.lex-toggle').first
   flag.scroll_into_view_if_needed()
   original=flag.bounding_box()
   flag.locator('input').hover();page.wait_for_timeout(180)
   assert rails.first.evaluate('e=>getComputedStyle(e).opacity')=='1'
   assert rails.nth(1).evaluate('e=>getComputedStyle(e).opacity')=='0'
   rail=rails.first
   rail.hover();page.wait_for_timeout(180)
   assert rail.locator('.lex-info-help').evaluate('e=>getComputedStyle(e).display')!='none'
   assert rail.locator('.lex-toggle-type').evaluate('e=>getComputedStyle(e).display')=='none'
   flag.locator('input').click()
   page.mouse.move(8,8);page.wait_for_timeout(180)
   assert rails.evaluate_all('nodes=>nodes.every(e=>getComputedStyle(e).opacity==="0")')
   assert flag.bounding_box()==original
   page.keyboard.press('Tab');flag.locator('input').focus();page.wait_for_timeout(180)
   assert rail.evaluate('e=>getComputedStyle(e).opacity')=='1'
   page.locator('nav button[data-tab]').first.focus();page.wait_for_timeout(180)
   assert rails.evaluate_all('nodes=>nodes.every(e=>getComputedStyle(e).opacity==="0")')
   gaps=page.locator('.lex-toggle').evaluate_all("""nodes=>nodes.map(e=>{const box=e.getBoundingClientRect(),rail=e.querySelector('.lex-toggle-rail')?.getBoundingClientRect(),name=e.querySelector('.lex-toggle-name');if(!rail||!name)return null;const range=document.createRange();range.selectNodeContents(name);const right=Math.max(...[...range.getClientRects()].map(r=>r.right));return {left:rail.left-box.left,right:box.right-right}}).filter(Boolean)""")
   # Every switch's box starts the same distance into its cell, whatever the
   # length of its name - the way every property's box starts at one edge.
   assert gaps and max(row['left'] for row in gaps)-min(row['left'] for row in gaps)<1,gaps
   copy_edges=page.evaluate("""()=>{
    const multi=document.querySelector('.lex-multi-number');
    const field=multi.closest('.lex-detail-field');
    const sibling=[...field.parentElement.querySelectorAll('.lex-detail-field')].find(e=>e!==field&&e.querySelector(':scope > .lex-detail-field-control > .lex-copy-value'));
    return [multi.querySelector('.lex-copy-value').getBoundingClientRect().left,sibling.querySelector(':scope > .lex-detail-field-control > .lex-copy-value').getBoundingClientRect().left];
   }""")
   assert abs(copy_edges[0]-copy_edges[1])<1,copy_edges
   page.screenshot(path=str(OUT/'controls.png'),animations='disabled')
   marker=page.locator('.lex-info-help').first
   marker.click(force=True);page.mouse.move(1400,880)
   page.wait_for_timeout(250)
   assert page.locator('.lex-help-popover').count()==0
   page.evaluate("navigate('graphs')");page.wait_for_timeout(350)
   assert page.locator('.lex-curve-svg').first.get_attribute('preserveAspectRatio')=='xMidYMid meet'
   page.screenshot(path=str(OUT/'graphs.png'),animations='disabled')
   # Exercise the real source reader/writer through the rendered troop controls.
   with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);(root/'module_troops.py').write_text(SOURCE)
    (root/'header_troops.py').write_text('tf_male=0\ntf_female=1\ntf_hero=16\nstr_4=4\nagi_4=1024\nint_4=262144\ncha_4=67108864\n')
    (root/'ID_factions.py').write_text('fac_commoners=0\nfac_other=1\n')
    (root/'ID_items.py').write_text('itm_sword=0\nitm_shield=1\n')
    calls=[]
    def route_api(route):
     path=urlparse(route.request.url).path
     payload={'rows':[]}
     if path=='/api/troops':payload=troop_data(root)
     elif path=='/api/troops/save':
      request=json.loads(route.request.post_data);payload=save_troops(root,request['sha256'],request['edits']);calls.append(path)
     elif path=='/api/dashboard':payload={'paths':{},'problems':[]}
     elif path=='/api/modules':payload={'modules':[]}
     elif path=='/api/warband-font':payload={'available':False}
     elif path=='/api/build/start':payload={'started':True};calls.append(path)
     elif path=='/api/build/status':payload={'cursor':1,'lines':['Build verified: fixture only'],'running':False,'returnCode':0}
     route.fulfill(content_type='application/json',body=json.dumps(payload))
    page.route('**/api/**',route_api)
    page.goto(f'http://127.0.0.1:{server.server_port}/plugins/warband/editor.html')
    page.wait_for_function('!state.booting')
    page.evaluate('state.selectedTroop="soldier";navigate("troops")')
    page.get_by_role('textbox',name='name',exact=True).fill('Edited soldier')
    page.locator('input[aria-label=level]').fill('23')
    assert page.evaluate('state.troopEdits.soldier?.stats.level')==23, page.evaluate('JSON.stringify(state.troopEdits)')
    page.get_by_role('combobox',name='Faction',exact=True).select_option('fac_other')
    page.locator('#global-save').click();page.wait_for_function('state.status==="Saved and build verified" && Object.keys(state.troopEdits).length===0')
    updated=troop_data(root)['rows'][0]
    assert updated['name']=='Edited soldier' and updated['stats']['level']==23 and updated['faction']=='fac_other', (updated,calls,page.evaluate('state.troopEdits'))
    assert calls==['/api/troops/save','/api/build/start']
    page.wait_for_function('!document.body.classList.contains("lex-save-busy")')
    page.screenshot(path=str(OUT/'troops.png'),animations='disabled')
   assert not errors,errors
   browser.close()
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
 print('Shared control interactions and troop save/reload passed. Build invocation used a fixture.')
if __name__=='__main__':main()
