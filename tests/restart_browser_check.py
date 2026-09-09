"""Restart the real Blank child from its rendered unsaved-changes dialog."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import sys
import threading
import tempfile
from dataclasses import replace
from unittest.mock import Mock
from playwright.sync_api import sync_playwright
from global_browser_check import STUB,ROOT
sys.path.insert(0,str(ROOT))
from desktop_host import HostApi
from games.blank.plugin import PLUGIN, BlankSession

class Bridge(BaseHTTPRequestHandler):
    host=None
    def log_message(self,*args):pass
    def do_GET(self):
        try:result=self.host.restart_plugin('blank');code=200
        except Exception as error:result={'error':str(error)};code=500
        self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Access-Control-Allow-Origin','*');self.end_headers();self.wfile.write(json.dumps(result).encode())

def main():
    temporary=tempfile.TemporaryDirectory(prefix='lexeditor-restart-')
    project_path=str(Path(temporary.name)/'samples.json')
    plugin=replace(PLUGIN,session_factory=lambda:BlankSession(extra_env={'LEXEDITOR_BLANK_PROJECTS':project_path}))
    host=HostApi.__new__(HostApi)
    host._lock=threading.RLock();host._plugins={'blank':plugin};host._enforce_installations=False
    host._session=None;host._session_identity=None;host._plugin_id=None;host._dirty_count=0
    host.download_fonts=Mock(return_value={'errors':[]})
    Bridge.host=host;bridge=ThreadingHTTPServer(('127.0.0.1',0),Bridge)
    threading.Thread(target=bridge.serve_forever,daemon=True).start()
    out=ROOT/'out/restart';out.mkdir(parents=True,exist_ok=True)
    try:
      opened=host.open_plugin('blank');previous=host._session
      with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1400,'height':900})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.add_init_script(STUB+f'''
window.__restartCalls=0;
window.pywebview.api.restart_plugin=async()=>{{window.__restartCalls++;const r=await fetch('http://127.0.0.1:{bridge.server_port}/restart');const v=await r.json();if(!r.ok)throw Error(v.error);return v;}};
// A loading quote is optional. Its failed bridge must never block restart.
window.pywebview.api.loading_quote=()=>new Promise(()=>{{}});
''')
        page.goto(opened['url']);page.evaluate("dispatchEvent(new Event('pywebviewready'))")
        page.locator('.lex-detail-field').first.wait_for()
        page.get_by_role('button',name='Active mod project',exact=True).click()
        page.get_by_role('menuitem',name='➕ Add a Mod',exact=True).click()
        page.get_by_role('textbox',name='New mod name',exact=True).fill('Restart sample')
        page.get_by_role('button',name='Create Sample',exact=True).click()
        page.get_by_role('button',name='Active mod project',exact=True).get_by_text('Restart sample',exact=True).wait_for()
        page.locator('nav button[data-tab=subtabs]').click()
        number=page.locator('.lex-detail-field[data-lex-type=INT] input[type=number]').first
        number.fill('102');number.dispatch_event('change')
        page.locator('#plugin-restart').click()
        page.get_by_role('button',name='Cancel',exact=True).click()
        assert number.input_value()=='102' and host._session is previous
        page.locator('#plugin-restart').click()
        page.get_by_role('button',name='Restart Without Saving',exact=True).click()
        page.wait_for_url(lambda url:str(url).startswith(host._session.url) and host._session is not previous,timeout=20000)
        page.locator('.lex-detail-field').first.wait_for()
        assert previous.wait_closed() and host._session.process.poll() is None
        page.locator('nav button[data-tab=subtabs]').click()
        assert page.locator('.lex-detail-field[data-lex-type=INT] input[type=number]').first.input_value()=='25'
        # A clean restart failure must be visible, not an unhandled rejection.
        page.evaluate("window.__realRestart=window.pywebview.api.restart_plugin;window.pywebview.api.restart_plugin=async()=>{throw Error('Test restart failed')};void 0")
        page.locator('#plugin-restart').click()
        page.get_by_role('alertdialog').get_by_text('Test restart failed',exact=True).wait_for()
        page.get_by_role('button',name='Close',exact=True).click()
        page.evaluate("window.pywebview.api.restart_plugin=window.__realRestart;void 0")
        # Saving must survive the replacement service's different origin.
        number=page.locator('.lex-detail-field[data-lex-type=INT] input[type=number]').first
        number.fill('103');number.dispatch_event('change')
        previous=host._session
        page.locator('#plugin-restart').click()
        page.get_by_role('button',name='Save and Restart',exact=True).click()
        page.wait_for_url(lambda url:str(url).startswith(host._session.url) and host._session is not previous,timeout=20000)
        page.locator('.lex-detail-field').first.wait_for()
        page.locator('nav button[data-tab=subtabs]').click()
        assert page.locator('.lex-detail-field[data-lex-type=INT] input[type=number]').first.input_value()=='103'
        assert json.loads(Path(project_path).read_text())['projects']['Restart sample']['demo']['value']==103
        page.get_by_role('button',name='Active mod project',exact=True).get_by_text('Restart sample',exact=True).wait_for()
        # Once saved, a later unsaved edit must return to 103, not the default.
        number=page.locator('.lex-detail-field[data-lex-type=INT] input[type=number]').first
        number.fill('104');number.dispatch_event('change');previous=host._session
        page.locator('#plugin-restart').click();page.get_by_role('button',name='Restart Without Saving',exact=True).click()
        page.wait_for_url(lambda url:str(url).startswith(host._session.url) and host._session is not previous,timeout=20000)
        page.locator('.lex-detail-field').first.wait_for();page.locator('nav button[data-tab=subtabs]').click()
        assert page.locator('.lex-detail-field[data-lex-type=INT] input[type=number]').first.input_value()=='103'
        # A failed disk save cannot clear the dirty edit or start a replacement.
        page.route('**/api/projects',lambda route:route.fulfill(status=500,json={'error':'Test disk full'}))
        number=page.locator('.lex-detail-field[data-lex-type=INT] input[type=number]').first
        number.fill('105');number.dispatch_event('change');previous=host._session
        page.locator('#plugin-restart').click();page.get_by_role('button',name='Save and Restart',exact=True).click()
        page.get_by_text('Save failed: Test disk full',exact=True).wait_for()
        assert host._session is previous and number.input_value()=='105'
        assert page.get_by_role('button',name='Cancel',exact=True).is_enabled()
        page.get_by_role('button',name='Cancel',exact=True).click()
        assert json.loads(Path(project_path).read_text())['projects']['Restart sample']['demo']['value']==103
        page.unroute('**/api/projects')
        # Escape and outside clicks cannot dismiss an in-progress operation.
        page.evaluate("LexeditorUI.confirmUnsavedExit({dirtyCount:()=>1},()=>new Promise(resolve=>window.__finishExit=resolve))")
        page.get_by_role('button',name='Exit Without Saving',exact=True).click()
        page.keyboard.press('Escape');page.locator('.lex-dialog-backdrop').click(position={'x':2,'y':2})
        assert page.locator('.lex-exit-dialog').is_visible()
        page.evaluate('window.__finishExit(false)')
        page.get_by_role('button',name='Cancel',exact=True).click()
        # A completed save followed by restart failure must not be called a save failure.
        page.evaluate("window.__dirty=1;LexeditorUI.confirmUnsavedExit({dirtyCount:()=>__dirty,save:async()=>{__dirty=0}},async()=>{throw Error('restart unavailable')},{exitError:'Could not restart'})")
        page.get_by_role('button',name='Save and Exit',exact=True).click()
        page.get_by_text('Could not restart: restart unavailable',exact=True).wait_for()
        page.get_by_role('button',name='Cancel',exact=True).click()
        # Missing and cancelled responses must leave a usable dialog and explain the result.
        page.evaluate('''()=>{window.__discardExit=()=>false;LexeditorUI.confirmUnsavedExit({dirtyCount:()=>1,save:async()=>{}},()=>__discardExit(),{discardLabel:'Restart Without Saving'});}''')
        page.get_by_role('button',name='Restart Without Saving',exact=True).click()
        page.get_by_text('The action did not complete. Try again or cancel.',exact=True).wait_for()
        assert page.get_by_role('button',name='Cancel',exact=True).is_enabled()
        page.get_by_role('button',name='Cancel',exact=True).click()
        page.evaluate("window.pywebview.api.restart_plugin=async()=>null")
        number=page.locator('.lex-detail-field[data-lex-type=INT] input[type=number]').first
        number.fill('102');number.dispatch_event('change');page.locator('#plugin-restart').click()
        page.get_by_role('button',name='Restart Without Saving',exact=True).click()
        page.get_by_text('The desktop host did not return a restart address.',exact=False).wait_for()
        assert page.get_by_role('button',name='Cancel',exact=True).is_enabled()
        page.screenshot(path=str(out/'recoverable-error.png'))
        assert not errors,errors
        browser.close()
    finally:
      host.stop();bridge.shutdown();bridge.server_close();temporary.cleanup()
    print('PASS: real service save/discard restart persistence, cancel, pending dialog guard, clean/dirty failure recovery, hung quote cannot block')
if __name__=='__main__':main()
