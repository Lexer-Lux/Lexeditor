"""Exercise the persistent menu in WebView2 with a temporary FF7 project."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,r'C:\RDR2Mod\tools\reverse-engineering')
from render_crime_editors_55_62 import Cdp, free_port, wait_json, wait_eval
from desktop_host import HostApi, CHOOSER
from games.ff7.plugin import PLUGIN, FF7Session
from settings_manager import SettingsStore
import webview
OUT=ROOT/'_scratch'/'transition-proof'
OUT.mkdir(parents=True,exist_ok=True)
port=free_port()
os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS']=f'--remote-debugging-port={port} --remote-allow-origins=*'
temporary=tempfile.TemporaryDirectory(prefix='lexeditor-transition-')
session=FF7Session({'LEXEDITOR_FF7_PROJECT':str(Path(temporary.name)/'project')})
session.start()
class Api(HostApi):
    def lexeditor_settings(self):
        return {**self._settings.snapshot(),'loadingTransitionMinimumSeconds':.4,'soundEnabled':False,'developerMode':True}
    def plugins(self):
        return [{'id':'ff7','name':'Final Fantasy VII','status':'added','canOpen':True,'resident':self._plugin_id=='ff7','dirtyCount':self._dirty_count,'coverArt':{'state':'ready','uri':(ROOT/'ui/assets/blank-game-cover.png').as_uri()}}]
    def open_plugin(self, plugin_id):
        self._plugin_id='ff7'
        self._session=session
        return {'url':session.url+'?lexTransition=load'}
    def resume_plugin(self, plugin_id):
        return {'url':session.url+'?lexTransition=resume'}
api=Api({'ff7':PLUGIN},enforce_installations=False,auto_scan=False,settings=SettingsStore(Path(temporary.name)/'settings.json'),window_state_path=None)
window=webview.create_window('Lexeditor transition check',CHOOSER.as_uri(),js_api=api,width=1200,height=800,frameless=True,easy_drag=False,background_color='#171a1f')
api.bind_window(window)
result={'passed':False}
def run():
    cdp=None
    try:
        page=next(p for p in wait_json(f'http://127.0.0.1:{port}/json/list') if p['type']=='page')
        cdp=Cdp(page['webSocketDebuggerUrl'])
        cdp.call('Page.enable')
        cdp.call('Runtime.enable')
        wait_eval(cdp,"typeof chooser!=='undefined'&&chooser.menuReady",40)
        cdp.eval("window.__menuIdentity=document.querySelector('#chooser-surface');window.__frames=[];window.__record=true;function sample(){if(!__record)return;const m=__menuIdentity,f=document.querySelector('#lexeditor-editor');__frames.push({t:performance.now(),same:m===document.querySelector('#chooser-surface'),cards:m.querySelectorAll('.game').length,menuX:m.getBoundingClientRect().x,frameX:f?.getBoundingClientRect().x,width:innerWidth});requestAnimationFrame(sample)}sample();")
        def shot(name):
            data=cdp.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})['data']
            (OUT/f'{name}.png').write_bytes(base64.b64decode(data))
        shot('menu')
        captures=[]
        def capture_slide(prefix,count):
            for index in range(count):
                geometry=cdp.eval("({menuX:__menuIdentity.getBoundingClientRect().x,frameX:document.querySelector('#lexeditor-editor')?.getBoundingClientRect().x,width:innerWidth})")
                name=f'{prefix}-{index:02}'
                shot(name)
                captures.append({'name':name,**geometry})
        for cycle in range(3):
            cdp.eval("document.querySelector('.game').click()")
            capture_slide(f'enter-{cycle}',24)
            wait_eval(cdp,"document.querySelector('#lexeditor-editor')?.getBoundingClientRect().x===0&&loadingScreen.hidden",40)
            shot(f'editor-{cycle}')
            if cycle == 2:
                target=next(t for t in cdp.call('Target.getTargets')['targetInfos'] if t['type']=='iframe')
                attached=cdp.call('Target.attachToTarget',{'targetId':target['targetId'],'flatten':True})['sessionId']
                def child_eval(expression):
                    cdp.ident+=1
                    ident=cdp.ident
                    cdp.ws.send(json.dumps({'id':ident,'sessionId':attached,'method':'Runtime.evaluate','params':{'expression':expression,'returnByValue':True}}))
                    while True:
                        message=json.loads(cdp.ws.recv())
                        if message.get('id')==ident:
                            return message.get('result',{}).get('result',{}).get('value')
                child_eval("(()=>{const input=document.querySelector('input[type=number]');input.value=Number(input.value)+1;input.dispatchEvent(new Event('input',{bubbles:true}));})()")
                time.sleep(.2)
                assert api._dirty_count>0, 'Edited field did not reach the native host'
                cdp.eval('window.__lexeditorRequestWindowClose()')
                time.sleep(.2)
                assert child_eval("!!document.querySelector('.lex-exit-dialog')"), 'Native close missed the unsaved prompt'
                child_eval("[...document.querySelectorAll('.lex-exit-dialog button')].find(b=>/cancel/i.test(b.textContent)).click()")
                # Restore the edit in memory. No project save is used in this check.
                child_eval("(()=>{const input=document.querySelector('input[type=number]');input.value=Number(input.value)-1;input.dispatchEvent(new Event('input',{bubbles:true}));})()")
                time.sleep(.2)
                assert api._dirty_count==0
                result['nativeClosePrompt']=True
            cdp.call('Input.dispatchMouseEvent',{'type':'mousePressed','x':80,'y':20,'button':'left','clickCount':1})
            cdp.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':80,'y':20,'button':'left','clickCount':1})
            capture_slide(f'leave-{cycle}',16)
            wait_eval(cdp,"!document.querySelector('#lexeditor-editor')",40)
            shot(f'home-{cycle}')
        (OUT/'captures.json').write_text(json.dumps(captures,indent=2))
        cdp.eval('__record=false')
        frames=cdp.eval('__frames')
        (OUT/'frames.json').write_text(json.dumps(frames,indent=2))
        assert all(f['same'] and f['cards']==1 for f in frames)
        assert all(f.get('frameX') is None or abs(f['menuX']+f['width']-f['frameX'])<3 for f in frames)
        result.update(passed=True,samples=len(frames),cycles=3,url=cdp.eval('location.href'))
    except Exception:
        result['error']=traceback.format_exc()
        if cdp:
            try:
                result['state']=cdp.eval("({url:location.href,frames:document.querySelectorAll('iframe').length,loading:loadingScreen.hidden,body:document.body.innerText.slice(-1500)})")
            except Exception: pass
    finally:
        (OUT/'result.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result),flush=True)
        if cdp: cdp.close()
        window.destroy()
webview.start(run,gui='edgechromium',private_mode=False,storage_path=str(Path(temporary.name)/'webview'))
api.dispose()
session.stop()
sys.exit(0 if result['passed'] else 1)
