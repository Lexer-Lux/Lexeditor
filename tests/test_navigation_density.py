import pytest
from io import BytesIO
from PIL import Image
from test_shared_ui_feedback import ROOT, page, framework

@pytest.mark.parametrize('width',[700,1000,1600])
def test_tabs_keep_full_size_names_and_tweaks_stays_attached(page,width):
    # Tabs share equal lanes, as many to a row as fit with their names at
    # full size. Forcing one row shrank sixteen FF8 names to a few pixels in a
    # 700px window; a second row is the readable answer. Tweaks stays the last
    # lane of the grid rather than floating off on its own.
    page.set_viewport_size({'width':width,'height':900})
    framework(page)
    page.add_style_tag(path=str(ROOT/'games/ff8/editor.css'))
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
        assert result['inside'] and not result['shrunk'] and not result['clipped'],result
        # A wide window keeps the one row it has room for.
        if width>=1600 and selector=='.lex-subtab-bar':
            assert result['rows']==1,result
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

def test_help_scales_with_its_heading(page):
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;document.querySelector('main').append(U.el('div',{style:'font-size:30px'},U.infoHelp('Help')))}''')
    help=page.locator('.lex-info-help')
    assert help.bounding_box()['width']>=30
    assert help.evaluate('n=>getComputedStyle(n).backgroundColor')=='rgb(255, 255, 255)'


def test_tab_pointer_is_painted_above_neighbouring_tabs(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'games/ff8/editor.css'))
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
