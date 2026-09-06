"""Behavioral shared-control regressions without installed games or machine-local tools."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/global-controls'


class FixtureServer(BaseHTTPRequestHandler):
    html = b""
    def log_message(self, *_): pass
    def do_GET(self):
        self.send_response(200 if self.path == '/' else 404)
        self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers()
        if self.path == '/': self.wfile.write(self.html)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    css = (ROOT/'ui/framework.css').read_text('utf-8')
    script = (ROOT/'ui/framework.js').read_text('utf-8').replace('</script', '<\\/script')
    html = '<html><head><base href="http://127.0.0.1/"><style>'+css+'</style></head><body><main id="main"></main><script>'+script+'</script></body></html>'
    with sync_playwright() as pw:
        exe = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        browser = pw.chromium.launch(headless=True, **({'executable_path': exe} if exe else {}), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_default_timeout(5000)
        if os.environ.get('LEXEDITOR_BROWSER_OFFLINE'):
            # The offline sandbox uses an explicit isolated test store, not a
            # claim that on-disk native preferences have been accepted.
            storage = "const store=new Map();Object.defineProperty(window,'localStorage',{value:{getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)}});"
            page.route('**/*', lambda r: r.abort())
            page.set_content(html.replace('<head>', '<head><script>'+storage+'</script>', 1))
            server = None
        else:
            FixtureServer.html = html.encode('utf-8')
            server = ThreadingHTTPServer(('127.0.0.1', 0), FixtureServer)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            page.goto(f'http://127.0.0.1:{server.server_port}/')
        page.evaluate('''() => {
          const U=LexeditorUI, e=U.el, m=document.querySelector('#main');
          window.__rows=[{id:2,name:'Beta',value:20},{id:1,name:'Alpha',value:10}];
          window.__selected=2;window.__adds=0;
          window.__table=()=>U.columnList({rows:__rows,key:r=>r.id,selected:__selected,
            select:r=>{__selected=r.id},columns:[{key:'id',label:'ID'},{key:'name',label:'Name'},{key:'value',label:'Value'}]});
          m.append(U.newButton({id:'add',title:'Add record',onclick:()=>__adds++}),__table());
        }''')
        assert page.locator('#add').get_attribute('aria-label') == 'Add record'
        page.evaluate('LexeditorUI.installControlHelp(document.body)')
        assert page.locator('#add').get_attribute('title') == 'Add record'
        page.evaluate("""()=>{const U=LexeditorUI,e=U.el;const wrap=e('label',{},'Opacity',e('input',{id:'auto-help',type:'number',min:0,max:100,step:5}));document.querySelector('#main').append(wrap)}""")
        page.wait_for_timeout(20)
        assert page.locator('#auto-help').get_attribute('title') == 'Set Opacity. Range: 0 to 100. Step: 5.'
        page.locator('#add').click()
        assert page.evaluate('__adds') == 1
        head = page.locator('[role=columnheader][data-column-key=name]')
        head.click(position={'x': 3, 'y': 3})
        assert page.locator('.lex-column-list-row [data-column-key=name]').all_text_contents() == ['Alpha','Beta']
        head.click(position={'x': 3, 'y': 3})
        assert page.locator('.lex-column-list-row [data-column-key=name]').all_text_contents() == ['Beta','Alpha']
        assert page.evaluate('__selected') == 2
        page.evaluate('''()=>{
          const U=LexeditorUI,e=U.el;
          window.__panels=()=>{let a=e('section',{},'List'),b=e('section',{},'Properties');
            const root=U.listDetail(a,b,{splitKey:'regression',defaultSplit:42,minLeft:160,minRight:240});
            root.style.height='350px';document.querySelector('#main').replaceChildren(root);};
          __panels();
        }''')
        divider = page.locator('[role=separator]').first
        divider.focus(); page.keyboard.press('ArrowRight');page.wait_for_timeout(100)
        moved = float(page.evaluate('localStorage.getItem("lexeditor:list-detail:regression")'))
        assert moved > 42, moved
        page.evaluate('__panels()');page.wait_for_timeout(100)
        restored = int(divider.get_attribute('aria-valuenow'))
        assert abs(restored-moved) <= 1, (restored,moved)
        divider.dblclick();page.wait_for_timeout(100)
        assert abs(float(page.evaluate('localStorage.getItem("lexeditor:list-detail:regression")'))-42)<.1
        divider.focus();page.keyboard.press('ArrowLeft');divider.click(button='right');page.wait_for_timeout(100)
        assert abs(float(page.evaluate('localStorage.getItem("lexeditor:list-detail:regression")'))-42)<.1
        page.set_viewport_size({'width':650,'height':800});page.wait_for_timeout(150)
        assert not divider.is_visible()
        page.set_viewport_size({'width':1280,'height':800})
        page.evaluate('''()=>{
          const U=LexeditorUI,e=U.el;window.__value=15;
          const input=e('input',{id:'quantity',type:'number',value:15,min:0,max:100,step:1,oninput:event=>__value=Number(event.target.value)});
          document.querySelector('#main').replaceChildren(U.detailField({label:'Quantity',dataType:'INT',min:0,max:100,control:U.unitField(input,'%')}));
        }''')
        number = page.locator('#quantity')
        number.fill('300');number.blur();assert number.input_value()=='100'
        number.focus();page.keyboard.press('e');assert number.input_value()=='100'
        unit=page.locator('.lex-unit').bounding_box();box=page.locator('.lex-unit-field').bounding_box()
        assert unit and box and unit['x']+unit['width']<=box['x']+box['width']+1
        page.evaluate('''()=>{
          window.__draft={setting:2,saved:1,record:99,failed:false};
          window.__save=LexeditorUI.settingsSaveControl({dirtyCount:()=>__draft.setting!==__draft.saved?1:0,
            save:async()=>{if(__draft.failed)throw Error('Fixture write denied');__draft.saved=__draft.setting;},
            discard:()=>{__draft.setting=__draft.saved;}});
          document.querySelector('#main').replaceChildren(__save);
        }''')
        save=page.locator('.lex-settings-save-control')
        save.click();page.wait_for_function('__draft.saved===2 && !document.body.inert')
        assert page.evaluate('__draft.record')==99 and save.is_disabled()
        page.evaluate('__draft.setting=3;__save.refresh()')
        save.click(button='right');page.get_by_role('button',name='Cancel',exact=True).click()
        assert page.evaluate('__draft.setting')==3
        save.click(button='right');page.get_by_role('button',name='Discard Changes',exact=True).click()
        page.wait_for_function('__draft.setting===2');assert page.evaluate('__draft.record')==99
        page.evaluate('__draft.setting=4;__draft.failed=true;__save.refresh()')
        save.click();page.get_by_role('alertdialog').wait_for()
        assert 'Fixture write denied' in page.get_by_role('alertdialog').inner_text()
        assert page.evaluate('!document.body.inert && __draft.saved===2 && __draft.setting===4 && __draft.record===99')
        page.get_by_role('button',name='Close',exact=True).click()
        result=page.evaluate('''async()=>{
          let visible='Info',mode='ok';const h=new LexeditorUI.NavigationHistory({initial:'Items',apply:async target=>{if(mode==='cancel')return false;if(mode==='error')throw Error('Navigation failed');visible=target;return true;}});
          h.visit('Effects');h.visit('Info');await h.go(-1);mode='cancel';await h.go(-1);const cancel=h.current==='Effects';
          mode='error';try{await h.go(-1)}catch(e){}const error=h.current==='Effects';
          mode='ok';await h.go(1);h.visit('Data Map');
          return {cancel,error,current:h.current,canForward:h.canForward,visible};
        }''')
        assert result['cancel'] and result['error'] and not result['canForward'] and result['current']=='Data Map',result
        assert not errors, errors
        results={'new_button':'pass','whole_header_sort':'pass','selection_retained':'pass',
          'divider_keyboard_persistence_doubleclick_contextmenu_stack':'pass','units_integer_bounds':'pass',
          'settings_save_discard_isolation_and_visible_failure':'pass','automatic_control_tooltips':'pass','history_cancellation_and_failure':'pass',
          'page_errors':errors,'storage':'in-memory test double' if server is None else 'browser localStorage',
          'note':'Shared browser fixtures; not physical mouse, native window, sound or installed-game acceptance.'}
        (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(results));browser.close()
        if server: server.shutdown(); server.server_close()


if __name__=='__main__':main()
