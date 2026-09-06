"""Portable rendered fixtures for shared controls, helper versions and offline credits."""
from __future__ import annotations
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
from pathlib import Path
import shutil
import sys
import threading
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('LEXEDITOR_TEST_OUTPUT',str(ROOT/'out/global-browser')))
SETTINGS=json.loads((ROOT/'ui/default_settings.json').read_text())|{'lexerMode':True,'lexerAuthorized':True,'lexerLogin':'Lexer-Lux','viewPreferences':{},'defaultValues':{},'updateCheckChoices':[], 'loadingTransitionMinimumSeconds':0}
HELPERS=[{'pluginId':'ff8','plugin':'Final Fantasy 8','helper':'FFNx','pinned':'1.0','installed':True,'installedVersion':'1.1','latest':'1.2','behind':True,'published':'2026-09-01T00:00:00Z','releaseNotes':'https://github.com/julianxhokaxhiu/FFNx/releases/tag/example'},
{'pluginId':'ff9','plugin':'Final Fantasy 9','helper':'Memoria','installed':False,'error':'Offline: cannot read the upstream release'}]
STUB='''
window.__calls=[];
window.pywebview={api:new Proxy({
 lexeditor_settings:async()=>SETTINGS,
 plugins:async()=>[],
 helper_versions:async refresh=>{window.__calls.push(refresh);return {helpers:HELPERS};},
 window_state:async()=>({maximized:false}),
 loading_quote:async()=>({quote:"A game-specific line"}),
 game_process_status:async()=>({running:false}),
 theme_sounds:async()=>({rows:[]}),
 project_info:async()=>({canCreate:false,projects:[]})
},{get:(target,name)=>target[name]|| (async()=>false)})};
'''.replace('SETTINGS','('+json.dumps(SETTINGS)+')').replace('HELPERS','('+json.dumps(HELPERS)+')')
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*_):pass
    def translate_path(self,path):
        path=urlparse(path).path
        if path.startswith('/shared/'):path='/ui/'+path[len('/shared/'):]
        return super().translate_path(path)


def load_page(page, base, path):
    if not os.environ.get("LEXEDITOR_BROWSER_OFFLINE"):
        page.goto(base+path)
        page.evaluate("dispatchEvent(new Event('pywebviewready'))")
        return
    # An offline fixture renders the exact source files without attempting any
    # network access. CI additionally exercises normal local HTTP routes.
    page.route("**/*",lambda route: route.abort())
    html=(ROOT/path.lstrip('/')).read_text('utf-8')
    folder=(ROOT/path.lstrip('/')).parent
    def asset(name):
        return ROOT/'ui'/name.removeprefix('/shared/') if name.startswith('/shared/') else folder/name
    html=re.sub(r'<link rel="stylesheet" href="([^"]+)">',lambda m:'<style>'+asset(m[1]).read_text('utf-8')+'</style>',html)
    html=re.sub(r'<script src="([^"]+)"></script>',lambda m:'<script>'+asset(m[1]).read_text('utf-8').replace('</script','<\\/script')+'</script>',html)
    data=json.loads((ROOT/'ui/credits.json').read_text('utf-8'))
    init=STUB+"\nfor(const k of [\"replaceState\",\"pushState\"]){const f=history[k].bind(history);history[k]=(s,t)=>f(s,t);};window.fetch=async url=>({ok:!String(url).includes('distribution-notices'),json:async()=>("+json.dumps(data)+")});"
    html=html.replace('<head>','<head><base href="https://offline.invalid/shared/"><script>'+init+'</script>',1)
    page.set_content(html,wait_until='domcontentloaded')
    page.evaluate("dispatchEvent(new Event('pywebviewready'))")


def focus_help(page, selector='[aria-label="Test help"]'):
    """Focus help deterministically; Chromium can occasionally drop one synthetic focus during heavy CI startup."""
    marker=page.locator(selector)
    marker.focus()
    try:
        page.wait_for_selector('.lex-help-popover',timeout=750)
    except PlaywrightTimeoutError:
        marker.blur();page.wait_for_timeout(20);marker.focus()
        page.wait_for_selector('.lex-help-popover',timeout=3000)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    results=[]
    try:
        with sync_playwright() as pw:
            executable=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
            browser=pw.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}),args=['--no-sandbox'])
            for width,height in [(900,620),(1600,900)]:
                page=browser.new_page(viewport={'width':width,'height':height});errors=[]
                page.set_default_timeout(5000);page.on('pageerror',lambda e:(errors.append(str(e)),print('PAGE ERROR',e,flush=True)));page.add_init_script(STUB)
                print('Loading Blank',width,flush=True);load_page(page,base,'/games/blank/editor.html');page.wait_for_function('!!window.LexeditorUI?.creditsPanel')
                page.wait_for_timeout(300)
                # Actual Blank Info action mounts one shared credits panel, even after refresh.
                print('Clicking info',flush=True);page.get_by_role('button',name='Open Blank setup and runtime information',exact=True).click()
                page.wait_for_selector('.lex-plugin-credits h3')
                assert page.locator('.lex-plugin-credits').count()==1
                assert page.locator('.lex-plugin-credits').inner_text().find('Shared application')>=0
                for plugin in json.loads((ROOT/'ui/credits.json').read_text())['plugins']:
                    page.evaluate('id=>{document.querySelector("#main").replaceChildren(LexeditorUI.creditsPanel(id));}',plugin)
                    page.wait_for_selector('.lex-plugin-credits h3')
                    assert not page.locator('.lex-plugin-credits [role=alert]').count(),plugin
                    if page.locator('.lex-plugin-credits details').count():
                        page.locator('.lex-plugin-credits summary').first.click()
                        assert len(page.locator('.lex-plugin-credits pre').first.inner_text())>50
                    overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
                    assert not overflow,(plugin,width,'horizontal overflow')
                page.screenshot(path=str(OUT/f'credits-{width}.png'))
                # Help is reachable from keyboard and remains within the viewport.
                page.evaluate('''()=>{let m=document.querySelector('#main');m.replaceChildren(LexeditorUI.infoHelp('Signed stamina points per second. Positive restores; negative drains.',{'aria-label':'Test help'}));}''')
                focus_help(page)
                box=page.locator('.lex-help-popover').bounding_box()
                assert box and box['x']>=0 and box['y']>=0 and box['x']+box['width']<=width+1
                page.keyboard.press('Escape');assert page.locator('.lex-help-popover').count()==0
                assert not errors,errors
                results.append({'size':[width,height],'credits_plugins':8,'keyboard_help':'pass','page_errors':errors})
                page.close()
            page=browser.new_page(viewport={'width':1200,'height':800});errors=[]
            page.set_default_timeout(5000);page.on('pageerror',lambda e:(errors.append(str(e)),print('PAGE ERROR',e,flush=True)));page.add_init_script(STUB)
            load_page(page,base,'/ui/chooser.html');page.wait_for_selector('#chooser-lexer:visible');page.locator('#chooser-lexer').click()
            page.wait_for_selector('.lexer-helper-versions')
            text=page.locator('#lexer-panel').inner_text()
            assert all(t in text for t in ['Pinned: 1.0','Installed: 1.1','Latest upstream: 1.2','Installed: Not detected','2026-09-01','Offline']),text
            release=page.locator('#lexer-panel .lexer-helper-source').first
            assert release.count()==1 and release.evaluate("e=>e.tagName==='BUTTON'&&!e.hasAttribute('href')")
            page.get_by_role('button',name='Check Again',exact=False).click();page.wait_for_timeout(100)
            assert page.evaluate('window.__calls.includes(true)')
            page.screenshot(path=str(OUT/'helper-versions.png'));assert not errors,errors
            results.append({'helper_versions':'pass','offline_rows_preserved':True,'refresh':'pass'})
            browser.close()
    finally:server.shutdown();server.server_close();thread.join(timeout=2)
    (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results))

if __name__=='__main__':main()
