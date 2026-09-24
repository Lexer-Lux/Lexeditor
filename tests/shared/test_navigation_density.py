# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import pytest
import tempfile
from pathlib import Path
from io import BytesIO
from PIL import Image
from test_shared_ui_feedback import ROOT, page, framework


@pytest.mark.parametrize('with_icon',[False,True])
def test_row_pointer_follows_clickable_label(page,with_icon):
    import os
    marker=Path(os.environ.get('LOCALAPPDATA',str(DEV_CACHE)))/'Lexeditor/game-data/ff8/generated/icons/0.png'
    if marker.exists():
        page.route('**/assets/icons/0.png',lambda r:r.fulfill(path=str(marker)))
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{
      document.querySelector('main').innerHTML='<div class="lex-column-list-row selected"><div class="lex-column-pointer-cell"><span class="lex-column-cell-content" style="position:relative;display:flex;justify-content:center;width:900px;height:60px"><button><span id="ability-name">HP-J</span></button></span></div></div>';
    }''')
    if with_icon:
        page.evaluate('''()=>{
          const name=document.querySelector('#ability-name'),button=name.parentElement,U=LexeditorUI;
          button.replaceChildren(U.inlineLabel(U.inlineLabel(U.el('img',{id:'ability-icon',
            src:'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><path fill="%23998ab6" d="M0 0h16v16H0z"/></svg>'})),name));
        }''')
    page.wait_for_timeout(100)
    for width in (900,600):
        page.locator('.lex-column-cell-content').evaluate('(n,w)=>n.style.width=w+"px"',width)
        page.wait_for_timeout(100)
        assert page.locator('.lex-column-cell-content').evaluate('''n=>{
          const p=getComputedStyle(n,'::before'),box=n.getBoundingClientRect();
          const range=document.createRange();range.selectNodeContents(document.querySelector('#ability-name'));
          const icon=document.querySelector('#ability-icon');
          const start=icon?icon.getBoundingClientRect().left:range.getBoundingClientRect().left;
          return Math.abs(start-(box.left+parseFloat(p.left)+parseFloat(p.width))-6)<2;
        }''')
    page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-clickable-row-pointer.png'))

@pytest.mark.parametrize('width',[700,1000,1600])
def test_tabs_stay_one_row_and_tweaks_stays_attached(page,width):
    # Main tabs and subtabs always share one row of equal lanes.
    page.set_viewport_size({'width':width,'height':900})
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.body.prepend(U.el('div',{id:'shell'}));
      U.mountShell({host:'#shell',brand:'LEXEDITOR',plugin:{id:'fixture',name:'Fixture'},
        tabs:['Abilities','Cards','Characters','Encounters','Enemies','Formulae','GFs','Items','Magic','Maps','New Game','Refine','Shops','Text','Weapons','Tweaks'].map(label=>({id:label==='Tweaks'?'settings':label,label})),activeTab:()=> 'Cards',navigate(){}});
      U.finishPluginLoading();
      document.querySelector('main').append(U.subtabBar({tabs:['Properties','Loot','Renzokuken','Defense','Text','Stats'].map(id=>({id,label:id})),active:'Properties',change(){}}));
    }''')
    page.wait_for_timeout(400)
    for selector in ['.lex-shell-header nav','.lex-subtab-bar']:
        result=page.locator(selector).first.evaluate('''n=>{
          const buttons=[...n.children],r=n.getBoundingClientRect();
          const labels=[...n.querySelectorAll('.lex-tab-label-text')];
          return {rows:new Set(buttons.map(b=>b.offsetTop)).size,
            inside:buttons.every(b=>b.getBoundingClientRect().right<=r.right+1),
            shrunk:labels.filter(l=>l.style.fontSize).map(l=>l.textContent),
            clipped:labels.filter(l=>l.scrollWidth>l.clientWidth+1).map(l=>l.textContent)};
        }''')
        assert result['inside'] and result['rows']==1,result
    nav=page.locator('.lex-shell-header nav')
    assert nav.locator('button').last.get_attribute('data-tab')=='settings'
    assert nav.locator('button').last.evaluate('n=>getComputedStyle(n).marginLeft')=='0px'
    # The pointer must fit in the existing page gutter, not indent the row.
    frame=page.locator('.lex-nav-frame')
    assert frame.evaluate('n=>getComputedStyle(n).paddingLeft===getComputedStyle(n).paddingRight')
    boxes=[b.bounding_box() for b in nav.locator('button').all()]
    page.evaluate('''()=>document.querySelectorAll('nav button[data-tab]').forEach(
      (n,i)=>n.classList.toggle('active',i===0))''')
    page.wait_for_timeout(60)
    assert [b.bounding_box() for b in nav.locator('button').all()]==boxes
    assert nav.locator('button').first.evaluate('''n=>{
      const p=getComputedStyle(n,'::before'),r=n.getBoundingClientRect();
      const left=r.left+parseFloat(getComputedStyle(n).borderLeftWidth)+parseFloat(p.left);
      const label=n.querySelector('.lex-tab-label-text'),range=document.createRange();range.selectNodeContents(label);
      return Math.abs(range.getBoundingClientRect().left-left-parseFloat(p.width)-6)<2;
    }''')
    brand=page.locator('.lex-brand-button')
    assert brand.evaluate('n=>!n.dispatchEvent(new MouseEvent("mousedown",{bubbles:true,cancelable:true}))')

def test_help_keeps_its_one_size_beside_a_large_heading(page):
    # G3 replaced heading-scaled help with one shared 16px size everywhere
    # (tests/shared/test_info_help_size.py); a large heading must not inflate it.
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;document.querySelector('main').append(U.el('div',{style:'font-size:30px'},U.infoHelp('Help')))}''')
    help=page.locator('.lex-info-help')
    assert round(help.bounding_box()['width'])==16
    assert help.evaluate('n=>getComputedStyle(n).backgroundColor')=='rgb(255, 255, 255)'


def test_tab_pointer_is_painted_above_neighbouring_tabs(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{const U=LexeditorUI;document.body.prepend(U.el('div',{id:'shell'}));
      U.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},
        tabs:['Abilities','Cards','Items'].map(id=>({id,label:id})),activeTab:()=> 'Cards',navigate(){}});
      U.finishPluginLoading();
      document.documentElement.style.setProperty('--lex-tab-marker-image','linear-gradient(#ff00ff,#ff00ff)');
    }''')
    page.wait_for_timeout(200)
    for selected in [0,1,2]:
        page.evaluate('''selected=>document.querySelectorAll('nav button[data-tab]').forEach((n,i)=>n.classList.toggle('active',i===selected))''',selected)
        page.wait_for_timeout(60)
        point=page.evaluate('''selected=>{
          const tabs=[...document.querySelectorAll('nav button[data-tab]')];
          tabs.forEach((n,i)=>n.classList.toggle('active',i===selected));
          const n=tabs[selected],r=n.getBoundingClientRect(),p=getComputedStyle(n,'::before');
          const width=parseFloat(p.width),border=parseFloat(getComputedStyle(n).borderLeftWidth);
          return {x:r.left+border+(parseFloat(p.left)+width/2),y:r.top+r.height/2};
        }''',selected)
        pixels=Image.open(BytesIO(page.screenshot())).convert('RGB')
        assert pixels.getpixel((round(point['x']),round(point['y'])))==(255,0,255)


@pytest.mark.parametrize('surface',['plugin','home'])
def test_brand_pointer_gestures_never_select_text(page,surface):
    framework(page)
    page.evaluate('''surface=>{
      const U=LexeditorUI;window.brandClicks=0;
      if(surface==='plugin') {
        document.body.prepend(U.el('div',{id:'shell'}));
        U.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},tabs:[],
          activeTab:()=>'',navigate(){}});U.finishPluginLoading();
      } else document.querySelector('main').append(
        U.el('div',{class:'chooser-title'},U.el('h1',{},'LEXEDITOR')));
      const brand=document.querySelector('.lex-brand-button,.chooser-title');
      brand.onclick=()=>brandClicks++;
      // Test the event protection even when host CSS enables selection.
      brand.style.userSelect='text';brand.querySelector('h1').style.userSelect='text';
      document.querySelector('main').append(U.el('input',{id:'editable',value:'Keep this selectable'}));
    }''',surface)
    brand=page.locator('.lex-brand-button,.chooser-title')
    brand.click();brand.dblclick()
    assert page.evaluate('brandClicks')==3
    assert page.evaluate('getSelection().toString()')==''
    box=brand.locator('h1').bounding_box()
    page.mouse.move(box['x']+2,box['y']+box['height']/2);page.mouse.down()
    page.mouse.move(box['x']+box['width']-2,box['y']+box['height']/2,steps=12);page.mouse.up()
    assert page.evaluate('getSelection().toString()')==''
    page.locator('#editable').click();page.locator('#editable').press('Control+A')
    assert page.locator('#editable').evaluate('n=>n.selectionEnd-n.selectionStart')==20


def test_brand_has_no_pressed_text_highlight(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.body.prepend(U.el('div',{id:'shell'}));
      U.mountShell({host:'#shell',plugin:{id:'blank',name:'Blank'},tabs:[],activeTab:()=>'',navigate(){}});
      U.finishPluginLoading();
      document.documentElement.style.setProperty('--lex-accent','#72ff1e');
    }''')
    brand=page.locator('.lex-brand-button')
    page.wait_for_timeout(200)
    before=brand.evaluate('n=>({bg:getComputedStyle(n,"::before").backgroundColor,fg:getComputedStyle(n).color})')
    brand.hover()
    hover=brand.evaluate('n=>({bg:getComputedStyle(n,"::before").backgroundColor,fg:getComputedStyle(n).color})')
    assert hover['bg']!=before['bg'] and hover['fg']==before['fg']
    bounds=brand.bounding_box()
    text=brand.locator('h1').bounding_box()
    assert abs(text['x']-bounds['x'])<1
    assert brand.locator('h1').evaluate('n=>n.scrollWidth<=n.clientWidth+1'),brand.locator('h1').evaluate('n=>({w:n.clientWidth,s:n.scrollWidth,font:getComputedStyle(n).fontSize,inline:n.style.fontSize,parent:n.parentElement.clientWidth})')
    page.mouse.down()
    assert page.evaluate('String(window.getSelection())')==''
    page.mouse.move(1000,700)
    page.mouse.up()
    brand.evaluate('n=>n.classList.add("lex-command-pressed")')
    pressed=brand.evaluate('n=>({bg:getComputedStyle(n,"::before").backgroundColor,fg:getComputedStyle(n).color})')
    assert pressed['bg']!=hover['bg'] and pressed['fg']==before['fg']
    assert brand.bounding_box()==bounds
    page.locator('.lex-shell-command-row').screenshot(path=str(Path(tempfile.gettempdir())/'lex-brand-header.png'))


def test_brand_real_return_action_and_scriptless_snapshot(page):
    page.evaluate('''()=>{
      window.homeCalls=0;
      window.pywebview={api:{transition_snapshot:async()=>null,
        return_to_main_menu:async()=>{homeCalls++;return {hostNavigates:true}},
        set_dirty_count:async()=>true,lexeditor_settings:async()=>({})}};
    }''')
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;document.body.prepend(U.el('div',{id:'shell'}));
      U.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},tabs:[],
        activeTab:()=>'',navigate(){},dirtyCount:()=>0});U.finishPluginLoading();
    }''')
    brand=page.locator('.lex-brand-button')
    assert brand.locator('h1').evaluate("n=>getComputedStyle(n,'::before').content")=='"LEXEDITOR"'
    assert brand.locator('h1').bounding_box()['width']>50
    brand.click()
    page.wait_for_function('homeCalls===1')
    assert page.evaluate('getSelection().toString()')==''
    # A snapshot has CSS but no JavaScript selection guards. Exercise that too.
    markup=brand.evaluate('n=>n.outerHTML')
    page.set_content('<style>'+ (ROOT/'ui/framework.css').read_text(encoding='utf-8')+
                     '</style>'+markup)
    brand=page.locator('.lex-brand-button')
    brand.dblclick()
    assert page.evaluate('getSelection().toString()')==''
    assert brand.evaluate("n=>{const r=document.createRange();r.selectNodeContents(n);return r.toString()}")==''
