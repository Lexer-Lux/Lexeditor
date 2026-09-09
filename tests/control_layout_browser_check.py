"""Rendered regression checks for the reported shared-control spacing and hover defects."""
from pathlib import Path
import functools
import threading
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from global_browser_check import ROOT, Handler, STUB, load_page

OUT=ROOT/'out/control-layout'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1600,'height':1000})
            page.add_init_script(STUB)
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            load_page(page,f'http://127.0.0.1:{server.server_port}','/games/blank/editor.html')
            page.locator('.lex-detail-field').first.wait_for()
            # Both project actions work in Blank without game folders or native windows.
            page.get_by_role('button',name='Active mod project',exact=True).click()
            page.get_by_role('menuitem',name='➕ Add a Mod',exact=True).click()
            page.get_by_role('textbox',name='New mod name',exact=True).fill('Layout sample')
            page.get_by_role('button',name='Create Sample',exact=True).click()
            page.get_by_role('button',name='Active mod project',exact=True).click()
            row=page.locator('div.lex-project-menu-item').first
            box=row.locator(':scope > .lex-project-source-status').bounding_box()
            folder=row.locator('.lex-project-folder')
            f=folder.bounding_box()
            assert box['x']>=f['x']+f['width']
            for cls in ('.lex-project-folder','.lex-project-rename'):
                button=row.locator(cls)
                before=button.evaluate('(e)=>getComputedStyle(e).backgroundColor')
                button.hover()
                assert button.evaluate('(e)=>getComputedStyle(e).backgroundColor')!=before
            page.screenshot(path=str(OUT/'project-menu.png'))
            page.get_by_role('menuitem',name='🔍 Find a Mod',exact=True).click()
            page.get_by_role('button',name='Layout sample',exact=True).click()
            assert 'Layout sample' in page.get_by_role('button',name='Active mod project',exact=True).inner_text()
            for width in (1600,1000,700):
                page.set_viewport_size({'width':width,'height':1000})
                page.wait_for_timeout(150)
                tabs=page.locator('.lex-shell-header nav button[data-tab]')
                for tab in tabs.all():
                    if not tab.is_visible():continue
                    tab.hover()
                    data=tab.evaluate('''e=>{const r=e.getBoundingClientRect(),b=e.querySelector('.lex-tab-shortcut').getBoundingClientRect(),t=e.querySelector('.lex-tab-label').getBoundingClientRect();return {size:b.height,top:b.top-r.top,bottom:r.bottom-b.bottom,right:r.right-b.right,gap:b.left-t.right}}''')
                    assert data['size']>=20 and min(data['top'],data['bottom'],data['right'])>=3 and data['gap']>=4,data
                for field in page.locator('.lex-detail-field:has(.lex-copy-value)').all():
                    if not field.is_visible():continue
                    # A multi-number property gives each value its own copy
                    # button inside its item, so only the field-level button
                    # sits before the control and can be measured that way.
                    data=field.evaluate('''e=>{
                      const c=e.querySelector(':scope > .lex-detail-field-control > .lex-copy-value');
                      if(!c) return null;
                      const l=e.querySelector('.lex-detail-field-label').getBoundingClientRect();
                      const cb=c.getBoundingClientRect();
                      const v=c.nextElementSibling?.getBoundingClientRect();
                      return v?{gap:cb.left-l.right,inputGap:v.left-cb.right}:null;}''')
                    if data is not None:
                        assert data['gap']>=0 and data['inputGap']>=4,data
                    for item in field.locator('.lex-multi-number-item:has(.lex-copy-value)').all():
                        inside=item.evaluate('''e=>{const c=e.querySelector('.lex-copy-value').getBoundingClientRect();
                          const b=e.getBoundingClientRect();
                          return {left:c.left-b.left,right:b.right-c.right};}''')
                        assert inside['left']>=0 and inside['right']>=0,inside
                for arrow in page.locator('.lex-field-boolean-arrow').all():
                    assert arrow.evaluate('(e)=>getComputedStyle(e).position')=='relative'
                for tag in page.locator('.lex-reference-tag').all():
                    if not tag.is_visible():continue
                    gap=tag.evaluate('(e)=>e.nextElementSibling.getBoundingClientRect().left-e.getBoundingClientRect().right')
                    assert 0<=gap<=8,gap
                page.screenshot(path=str(OUT/f'blank-{width}.png'))
            page.set_viewport_size({'width':1600,'height':1000})
            page.locator('nav button[data-tab=two]').click()
            page.locator('[role=columnheader][data-column-key=name]').click(position={'x':3,'y':3})
            page.mouse.move(0,0);page.wait_for_timeout(150)
            sort=page.locator('[data-lex-sort] .lex-field-type-rail').first
            data=sort.evaluate("""e=>{const s=getComputedStyle(e,'::after'),r=e.getBoundingClientRect(),f=e.closest('.lex-detail-field').getBoundingClientRect();return {y:r.top+parseFloat(s.top),center:f.top+f.height/2,x:r.left-f.left}}""")
            assert abs(data['y']-data['center'])<1 and abs(data['x'])<1,data
            page.screenshot(path=str(OUT/'sorted-detail.png'))
            page.locator('nav button[data-tab=subtabs]').click()
            for tab in page.locator('.lex-subtab-button').all():
                tab.hover()
                data=tab.evaluate("""e=>{const r=e.getBoundingClientRect(),b=e.querySelector('.lex-tab-shortcut').getBoundingClientRect(),l=e.querySelector('.lex-tab-label').getBoundingClientRect();return {height:b.height,top:b.top-r.top,gap:b.left-l.right}}""")
                assert data['height']>=20 and data['top']>=3 and data['gap']>=4,data
            page.locator('.lex-detail-field:has(.lex-copy-value)').last.hover()
            page.screenshot(path=str(OUT/'tabbed-copy.png'))
            assert page.locator('.lex-field-boolean-arrow').evaluate('(e)=>getComputedStyle(e).position')=='relative'
            # A focused fixture tests a no-help sort marker and per-box help in the same production CSS.
            page.evaluate('''()=>{const U=LexeditorUI,e=U.el;document.querySelector('#main').replaceChildren(
              U.detailField({label:'Number',dataType:'INT',attrs:{'data-lex-sort':'asc'},control:e('input',{type:'number',value:102})}),
              U.toggleRow({toggles:[{key:'a',label:'Target chars',help:'Target characters.'},{key:'b',label:'Target GF',help:'Target the GF.'}]}));}''')
            page.mouse.move(0,0);page.wait_for_timeout(150)
            sort=page.locator('[data-lex-sort] .lex-field-type-rail')
            assert sort.evaluate('''e=>{const s=getComputedStyle(e,'::after');return Math.abs(parseFloat(s.top)-e.getBoundingClientRect().height/2)<1}''')
            a=page.locator('[data-lex-toggle=a]');b=page.locator('[data-lex-toggle=b]')
            assert not a.locator('.lex-info-help').is_visible()
            a.hover()
            # Each switch shows its type at rest; pointing at THAT text swaps it
            # for the help marker. Hovering the switch elsewhere changes nothing.
            assert a.locator('.lex-toggle-type').is_visible()
            a.locator('.lex-toggle-rail').hover()
            assert a.locator('.lex-info-help').is_visible()
            assert not a.locator('.lex-toggle-type').is_visible()
            assert not b.locator('.lex-info-help').is_visible()
            assert b.locator('.lex-toggle-type').is_visible()
            a.locator('input').check()
            assert a.locator('input').is_checked()
            page.screenshot(path=str(OUT/'boolean-hover.png'))
            assert not errors,errors
            browser.close()
    finally:server.shutdown()
    print('Shared layout: project actions, hover, sort, arrows, references, copy and tabs passed at 1600/1000/700 px')

if __name__=='__main__':main()
