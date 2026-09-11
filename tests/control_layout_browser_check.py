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
                # The copy button's drawing fills its button, and the air on
                # each side of it is equal.
                for field in page.locator('.lex-detail-field:has(> .lex-detail-field-control > .lex-copy-value)').all():
                    if not field.is_visible():continue
                    air=field.evaluate('''e=>{
                      const copy=e.querySelector(':scope > .lex-detail-field-control > .lex-copy-value');
                      const ink=copy.querySelector('svg');
                      const label=e.querySelector(':scope > .lex-detail-field-label');
                      // The thing in the lane's other column, whatever it is:
                      // a nested grid of its own starts where its column does,
                      // not where its first input happens to sit.
                      const box=copy.nextElementSibling;
                      if(!ink||!box)return null;
                      const ib=ink.getBoundingClientRect();
                      return [Math.round(ib.left-label.getBoundingClientRect().right),
                              Math.round(box.getBoundingClientRect().left-ib.right),
                              Math.round(copy.getBoundingClientRect().width-ib.width)];}''')
                    if air is not None:
                        assert abs(air[0]-air[1])<=1,air
                        assert air[2]<=1,air
                # The fill behind a value is the height of that value's box,
                # never the height of the property row around it.
                for field in page.locator('.lex-has-value-fill').all():
                    if not field.is_visible():continue
                    fill=field.evaluate('''e=>{
                      const f=e.querySelector('.lex-value-fill');
                      const box=e.querySelector('input,select,textarea');
                      if(!f||!box)return null;
                      return [Math.round(f.getBoundingClientRect().height),
                              Math.round(box.getBoundingClientRect().height)];}''')
                    if fill is not None:
                        assert fill[0]<=fill[1]+3,fill
                # A boolean's pin annotates the row, so it never lands on the
                # checkbox it annotates.
                for field in page.locator('.lex-boolean-field:has(.lex-column-pin)').all():
                    if not field.is_visible():continue
                    clear=field.evaluate('''e=>{
                      const pin=e.querySelector('.lex-column-pin').getBoundingClientRect();
                      const box=e.querySelector('input[type=checkbox]').getBoundingClientRect();
                      return (pin.right<box.left||pin.left>box.right||
                              pin.bottom<box.top||pin.top>box.bottom)?pin.left-box.right:null;}''')
                    assert clear is not None and clear>=4,clear
                # A wrapped tab bar splits its tabs as evenly as the count allows.
                spread=page.evaluate('''()=>{
                  const bar=document.querySelector('.lex-shell-header nav');
                  const tabs=[...bar.children].filter(n=>n.offsetParent!==null);
                  const rows={};
                  for(const t of tabs){const k=Math.round(t.offsetTop);rows[k]=(rows[k]||0)+1;}
                  return Object.values(rows);}''')
                assert max(spread)-min(spread)<=1,spread
                for arrow in page.locator('.lex-field-boolean-arrow').all():
                    assert arrow.evaluate('(e)=>getComputedStyle(e).position')=='relative'
                # A reference stack reads as two columns: every tag starts on one
                # edge and every value on another, so a stack mixing "V" with
                # "R1" no longer steps its numbers sideways. The stack also
                # stays inside the property row rather than making it taller.
                for stack in page.locator('.lex-reference-values').all():
                    if not stack.is_visible():continue
                    data=stack.evaluate('''e=>{
                      const rows=[...e.querySelectorAll('.lex-reference-value')].map(v=>({
                        tag:v.querySelector('.lex-reference-tag').getBoundingClientRect(),
                        text:v.querySelector('.lex-reference-text').getBoundingClientRect()}));
                      const field=e.closest('.lex-detail-field')||e.closest('.lex-column-list-cell');
                      return {tags:rows.map(r=>Math.round(r.tag.left)),
                              texts:rows.map(r=>Math.round(r.text.left)),
                              indent:Math.max(...rows.map(r=>r.text.left-r.tag.left)),
                              height:e.getBoundingClientRect().height,
                              row:field?field.getBoundingClientRect().height:Infinity};}''')
                    assert len(set(data['tags']))<=1,data
                    assert len(set(data['texts']))<=1,data
                    # The tag column is as wide as the widest tag on the panel,
                    # so a lone "V" holds the same column an "R1" would.
                    assert 0<=data['indent']<=30,data
                    assert data['height']<=data['row']+1,data
                # A value box is square, and a panel ends where the pagination
                # bar begins - no band of dead ground between them, and the
                # same on every page that has a bar.
                for box in page.locator('.lex-detail-field[data-lex-type] input:not([type=checkbox])').all():
                    if not box.is_visible():continue
                    assert box.evaluate("e=>getComputedStyle(e).borderRadius")=='0px',                        box.evaluate("e=>[e.className,getComputedStyle(e).borderRadius]")
                # Measured from the last row a reader can SEE, not from the
                # box around it: the pane reached the bar while its content
                # stopped a pager's height short, which is the band that was
                # reported three times and measured away twice.
                seat=page.evaluate('''()=>{
                  const bar=document.querySelector('.lex-pager');
                  if(!bar)return null;
                  const rows=[...document.querySelectorAll('#main .lex-column-list-row')]
                    .map(n=>n.getBoundingClientRect()).filter(r=>r.height>2);
                  if(!rows.length)return null;
                  return Math.round(bar.getBoundingClientRect().top-Math.max(...rows.map(r=>r.bottom)));}''')
                if seat is not None:
                    assert -2<=seat<=6,seat
                page.screenshot(path=str(OUT/f'blank-{width}.png'))
            page.set_viewport_size({'width':1600,'height':1000})
            page.locator('nav button[data-tab=two]').click()
            page.locator('[role=columnheader][data-column-key=name]').click(position={'x':3,'y':3})
            page.mouse.move(0,0);page.wait_for_timeout(150)
            sort=page.locator('[data-lex-sort] .lex-field-type-rail').first
            data=sort.evaluate("""e=>{const s=getComputedStyle(e,'::after'),r=e.getBoundingClientRect(),f=e.closest('.lex-detail-field').getBoundingClientRect();return {y:r.top+parseFloat(s.top),center:f.top+f.height/2,x:r.left-f.left}}""")
            assert abs(data['y']-data['center'])<1 and abs(data['x'])<1,data
            page.screenshot(path=str(OUT/'sorted-detail.png'))
            page.locator('nav button[data-tab=one]').click()
            page.locator('.lex-detail-field').first.wait_for()
            page.mouse.move(0,0);page.wait_for_timeout(250)
            # A reference pillar reserves its room in advance. Nothing the
            # reader types may move a value box: not a rail appearing, not one
            # disappearing as an edit lands on vanilla, not a longer number.
            edges = lambda: page.evaluate('''() => [...document.querySelectorAll(
                '.lex-source-control > :is(input,select,.lex-unit-field)')]
                .map(e => Math.round(e.getBoundingClientRect().right))''')
            settled = edges()
            value = page.locator('.lex-detail-field',has_text='1-REF VALUE').locator('input[type=number]')
            for sample in ('25','7','255','40'):
                value.fill(sample);page.wait_for_timeout(200)
                assert edges()==settled,(sample,settled,edges())
            # A property holds variables. A multi-variable property gives each
            # of them its own copy button; a row of switches is one stored word
            # and copies that word, not the first switch on it.
            multi = page.locator('.lex-detail-field',has_text='MULTI-NUMBER').first
            assert multi.locator(':scope > .lex-detail-field-control > .lex-copy-value').count()==0
            items = multi.locator('.lex-multi-number-item')
            assert items.count()>1 and multi.locator('.lex-multi-number-item > .lex-copy-value').count()==items.count()
            copied = page.evaluate('''() => {
              const f = [...document.querySelectorAll('.lex-detail-field')].find(
                f => f.textContent.includes('USE FLAGS'));
              const row = f.querySelector('.lex-toggle-row');
              return typeof row.lexCopyValue === 'function' ? row.lexCopyValue() : null;}''')
            assert copied==5,copied
            # A flag box is as wide as the flag in it, so its two insets match.
            for toggle in page.locator('.lex-toggle').all():
                if not toggle.is_visible():continue
                inset=toggle.evaluate('''e=>{
                  const b=e.getBoundingClientRect();
                  const rail=e.querySelector('.lex-toggle-rail');
                  const name=e.querySelector('.lex-toggle-name');
                  if(!rail||!name)return null;
                  return [Math.round(rail.getBoundingClientRect().left-b.left),
                          Math.round(b.right-name.getBoundingClientRect().right)];}''')
                if inset is not None:
                    assert abs(inset[0]-inset[1])<=1,inset
            # A value box painted the way a player reads it - "50,000" - is
            # still a number to its own slider. Read with a bare Number() it is
            # NaN, which pinned the fill and the handle to the left edge.
            grouped=page.evaluate('''() => {
              const U=LexeditorUI,e=U.el;
              const input=e("input",{type:"text",inputmode:"decimal",value:U.formatNumber(50000),
                "data-min":0,"data-max":655350,"data-step":10});
              const field=U.detailField({label:"BUY PRICE",dataType:"INT",min:0,max:655350,step:10,
                control:U.unitField(input,"G")});
              document.querySelector('#main').replaceChildren(field);
              return new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(()=>{
                const fill=field.querySelector('.lex-value-fill');
                done(fill?Number(getComputedStyle(fill).getPropertyValue('--lex-value-ratio')):null);})));}''')
            assert grouped is not None and abs(grouped-50000/655350)<.001,grouped
            # The unit belongs to the number, so it sits just after the last
            # digit and moves with it, and it never crosses into whatever the
            # box reserves on its right for an internal reference.
            for sample in ('50,000','7','655,350'):
                unit=page.evaluate('''(text)=>{
                  const U=LexeditorUI,el=U.el;
                  const input=el("input",{type:"text",inputmode:"decimal",value:text,
                    "data-min":0,"data-max":655350,"data-step":10});
                  const control=U.provenanceControl({control:U.unitField(input,"G"),
                    current:()=>Number(String(input.value).replaceAll(",","")),vanilla:30000,
                    references:[],internal:true,apply:v=>{input.value=String(v);}});
                  document.querySelector('#main').replaceChildren(
                    U.detailField({label:"BUY PRICE",dataType:"INT",min:0,max:655350,step:10,control}));
                  return new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(()=>{
                    const field=document.querySelector('.lex-unit-field-boxed');
                    const mark=field.querySelector(':scope > .lex-unit');
                    const box=field.querySelector('input');
                    const fb=field.getBoundingClientRect(),mb=mark.getBoundingClientRect();
                    const cs=getComputedStyle(box);
                    const pen=document.createElement('canvas').getContext('2d');
                    pen.font=`${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
                    const digitsEnd=fb.left+(parseFloat(cs.borderLeftWidth)||0)+
                      (parseFloat(cs.paddingLeft)||0)+pen.measureText(box.value).width;
                    const reserved=parseFloat(getComputedStyle(field)
                      .getPropertyValue('--lex-unit-reserve'))||0;
                    done({gap:Math.round(mb.left-digitsEnd),
                          clear:Math.round(fb.right-reserved-mb.right)});})));}''',sample)
                assert 0<=unit['gap']<=14,(sample,unit)
                assert unit['clear']>=-1,(sample,unit)
            page.reload();page.evaluate("dispatchEvent(new Event('pywebviewready'))")
            page.locator('.lex-detail-field').first.wait_for()
            page.wait_for_timeout(300)
            # Ticking a box may not cost more on a big panel than a small one.
            # Re-fitting every label in the document on every DOM change made
            # a four-hundred-property page take a third of a second to respond.
            timings={}
            for size in (40,400):
                page.evaluate('''(count)=>{
                  const U=LexeditorUI,e=U.el,rows=[];
                  for(let i=0;i<count;i++){
                    const input=e("input",{type:"number",min:0,max:255,value:40+(i%60)});
                    rows.push(U.detailField({label:`PROPERTY NUMBER ${i}`,dataType:"INT",min:0,max:255,
                      control:U.provenanceControl({control:input,current:()=>Number(input.value),
                        vanilla:25,references:[{name:"Reference Mod 1",shortName:"R1",value:30}],
                        apply:v=>{input.value=v;}})}));}
                  document.querySelector('#main').replaceChildren(
                    U.detailSection({title:"STRESS",body:rows}));}''',size)
                page.wait_for_timeout(500)
                timings[size]=page.evaluate('''async()=>{
                  const input=document.querySelector('.lex-detail-field input[type=number]');
                  const runs=[];
                  for(let i=0;i<5;i++){
                    const start=performance.now();
                    input.value=String(30+i);
                    input.dispatchEvent(new Event('input',{bubbles:true}));
                    input.dispatchEvent(new Event('change',{bubbles:true}));
                    await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
                    runs.push(performance.now()-start);}
                  return Math.min(...runs);}''')
            assert timings[400]<timings[40]*3+40,timings
            page.reload();page.evaluate("dispatchEvent(new Event('pywebviewready'))")
            page.locator('.lex-detail-field').first.wait_for()
            page.wait_for_timeout(400)
            # Every row of the mod menu puts its name, description, buttons and
            # status in the same columns.
            page.get_by_role('button',name='Active mod project',exact=True).click()
            page.wait_for_timeout(250)
            columns=page.evaluate('''() => [...document.querySelectorAll('.lex-project-menu-item')].map(row => {
              const at = s => { const e = row.querySelector(s);
                return e ? Math.round(e.getBoundingClientRect().left) : null; };
              return [at('.lex-project-source-mode'), at('.lex-project-menu-name'),
                      at('.lex-project-menu-path'), at('.lex-project-source-status')];})''')
            assert len(columns)>1 and all(row==columns[0] for row in columns),columns
            assert page.locator('.lex-project-menu-item .lex-project-about').count()>0
            assert page.locator('.lex-project-remove').count()==0
            page.keyboard.press('Escape')
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
            # Park the pointer first: an earlier step can leave it over this
            # switch, which makes the at-rest state look like the hover state.
            page.mouse.move(0,0);page.wait_for_timeout(150)
            # One rail contract for flags and for every other property:
            # pointing at the SWITCH shows its type code, and only pointing at
            # the RAIL swaps that code for its help mark.
            assert not a.locator('.lex-info-help').is_visible()
            assert a.locator('.lex-toggle-type').is_visible()
            a.hover()
            assert a.locator('.lex-toggle-type').is_visible() and not a.locator('.lex-info-help').is_visible()
            a.locator('.lex-toggle-rail').hover()
            assert a.locator('.lex-info-help').is_visible() and not a.locator('.lex-toggle-type').is_visible()
            page.mouse.move(0,0);page.wait_for_timeout(150)
            assert not b.locator('.lex-info-help').is_visible() and b.locator('.lex-toggle-type').is_visible()
            # Every property's rail sits just left of the name it annotates,
            # whether or not that property also carries a help mark.
            for field in page.locator('.lex-detail-field').all():
                if not field.is_visible():continue
                offset=field.evaluate('''e=>{
                  // A sorted property flies its sort arrow in the gutter
                  // instead, which is its own contract.
                  if(e.hasAttribute('data-lex-sort'))return null;
                  const rail=e.querySelector(':scope > .lex-field-type-rail');
                  const label=e.querySelector(':scope > .lex-detail-field-label');
                  if(!rail||!label||getComputedStyle(rail).display==='none')return null;
                  const holder=label.querySelector(':scope > .lex-detail-field-label-text')||label;
                  const node=[...holder.childNodes].find(n=>n.nodeType===3&&n.textContent.trim());
                  if(!node)return null;
                  const range=document.createRange();range.selectNodeContents(node);
                  return range.getBoundingClientRect().left-rail.getBoundingClientRect().right;}''')
                if offset is not None:
                    assert 0<=offset<=10,(field.inner_text()[:20],offset)
            # Clicking the help mark must not leave the swap held open once
            # the pointer has gone: the mark is focusable, and :focus-within
            # kept it up for as long as focus sat there.
            a.locator('.lex-toggle-rail').hover()
            page.mouse.down();page.mouse.up()
            page.mouse.move(0,0);page.wait_for_timeout(150)
            assert not a.locator('.lex-info-help').is_visible() and a.locator('.lex-toggle-type').is_visible()
            a.locator('input').check()
            assert a.locator('input').is_checked()
            page.screenshot(path=str(OUT/'boolean-hover.png'))
            assert not errors,errors
            browser.close()
    finally:server.shutdown()
    print('Shared layout: project actions, hover, sort, arrows, references, copy and tabs passed at 1600/1000/700 px')

if __name__=='__main__':main()
