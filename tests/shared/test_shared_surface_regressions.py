"""Rendered checks for the shared controls that failed in FF8 screens."""
import pytest
from test_shared_ui_feedback import ROOT, page, framework


@pytest.mark.parametrize('platform', [False, True])
def test_boolean_label_arrow_and_mark_share_a_row(page, platform):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''platform=>{
      const U=LexeditorUI,input=U.el('input',{type:'checkbox',checked:true});
      input.style.fontSize='60px';
      const field=U.detailField({label:'Bilinear',className:platform?'lex-platform-config-field':'',
        control:platform?input:U.provenanceControl({control:input,current:true,vanilla:false,apply(){},internal:true})});
      field.style.width='400px';document.querySelector('main').append(field);
    }''',platform)
    bounds=page.locator('.lex-boolean-field').evaluate('''n=>{
      const input=n.querySelector('input'),arrow=n.querySelector('.lex-field-boolean-arrow'),label=n.querySelector('.lex-detail-field-label-text');
      const cy=n=>{const r=n.getBoundingClientRect();return (r.top+r.bottom)/2};
      const mark=getComputedStyle(input,'::before');
      return {label:cy(label),arrow:cy(arrow),box:cy(input),markWidth:parseFloat(mark.width),boxWidth:input.clientWidth};
    }''')
    assert abs(bounds['label']-bounds['box'])<2,bounds
    assert abs(bounds['arrow']-bounds['box'])<2,bounds
    assert bounds['markWidth']<bounds['boxWidth'],bounds


def test_scrollbars_take_space_only_when_needed(page):
    page.evaluate('''()=>{
      const box=document.createElement('div');box.id='scroll';
      Object.assign(box.style,{width:'200px',height:'100px',overflow:'auto'});
      box.innerHTML='<div style="height:300px">Content</div>';
      const wrapper=document.createElement('div');wrapper.append(box);
      document.querySelector('main').append(wrapper);
    }''')
    gutter=page.locator('#scroll').evaluate('n=>n.offsetWidth-n.clientWidth')
    assert 0<gutter<=12,page.locator('#scroll').evaluate('n=>({gutter:n.offsetWidth-n.clientWidth,height:n.clientHeight,scroll:n.scrollHeight,css:getComputedStyle(n).cssText,child:n.firstChild.getBoundingClientRect().height})')
    page.locator('#scroll > div').evaluate("n=>n.style.height='30px'")
    assert page.locator('#scroll').evaluate('n=>n.offsetWidth-n.clientWidth')==0


def test_unlabelled_field_uses_label_space_and_flag_group_spans_grid(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      const grid=U.tileGrid([U.detailField({label:'Other',control:U.el('input')}),
        U.detailField({label:'Starting status',control:U.toggleRow({toggles:['Death','Poison','Petrify','Darkness','Silence','Berserk','Zombie'].map(label=>({label}))})})]);
      document.querySelector('main').append(grid,U.detailField({label:'',control:U.el('input',{'aria-label':'Price'})}));
    }''')
    grid=page.locator('.lex-tile-grid').bounding_box()
    flags=page.locator('.lex-tile-grid > .lex-detail-field').last.bounding_box()
    assert abs(grid['width']-flags['width'])<1
    for label in page.locator('.lex-toggle-name').all():
        assert label.evaluate('n=>n.getBoundingClientRect().right<=n.parentElement.getBoundingClientRect().right')
    price=page.get_by_role('textbox',name='Price')
    assert price.evaluate('n=>n.getBoundingClientRect().width/n.closest(".lex-detail-field").getBoundingClientRect().width')>.9


def test_platform_pages_fit_below_tabs(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI,config={available:true,runtime:'FFNx',sections:[{label:'Display',fields:Array.from({length:40},(_,i)=>({
        id:'setting'+i,label:'Setting '+i,key:'setting'+i,kind:'boolean',value:i%2===0,description:'Change this setting.'}))}]};
      const panel=U.platformConfigView({config,showHeader:false,change(){},search(){},tabs:[{id:'gameplay',label:'Gameplay'},{id:'platform',label:'FFNx'}],activeTab:'platform'});
      panel.style.setProperty('--lex-panel-gap','24px');
      panel.style.fontSize='20px';
      panel.style.height='560px';document.querySelector('main').append(panel);
    }''')
    page.wait_for_timeout(250)
    for _ in range(15):
        result=page.locator('.lex-tweaks-paged').evaluate('''n=>{
          const tabs=n.querySelector('.lex-subtab-bar').getBoundingClientRect(),scroll=n.querySelector('.lex-tweaks-scroll');
          return {gap:scroll.getBoundingClientRect().top-tabs.bottom,extra:scroll.scrollHeight-scroll.clientHeight};
        }''')
        assert result['gap']>=0,result
        assert result['extra']<=1,result
        next_page=page.get_by_role('button',name='Next page',exact=True)
        if next_page.count()==0 or next_page.is_disabled():break
        next_page.click();page.wait_for_timeout(60)
    else:
        pytest.fail('Pager did not reach the last page')


def test_grouped_controls_keep_usable_width_in_a_narrow_panel(page):
    framework(page)
    page.evaluate("""()=>{
        const U=LexeditorUI,group=U.controlGroup(['Attack animation','Target hit animation','Attack type','Spell power','Draw resist','Hit count'].map(label=>({label,control:U.el('input',{type:'number',value:10})})));
      const wrapper=U.el('div',{},group);group.style.width='500px';
      document.querySelector('main').append(wrapper);
    }""")
    for control in page.locator('.lex-detail-part-control input').all():
        assert control.bounding_box()['width']>=80


@pytest.mark.parametrize('width', [600, 650, 900])
def test_shell_header_fits_the_window(page, width):
    """The command row keeps its controls usable in a small window.

    A 900 px window at 150% UI scale is 600 CSS px, which is the smallest the
    row has to survive. The three groups used to need about 620 there, so the
    window grew a horizontal scrollbar and the window buttons sat off-screen.
    """
    framework(page)
    page.set_viewport_size({"width": width, "height": 413})
    page.evaluate("""()=>{
      // The row a real plugin page builds: brand, project picker, history and
      // save, the scale slider, the settings rail and the window buttons.
      window.pywebview={api:{lexeditor_settings:async()=>({developerMode:true}),
        github_repository:async()=>({repository:'Lexer-Lux/Lexeditor'}),
        mod_library_status:async()=>({canManage:false}),
        mod_projects:async()=>({pluginId:'fixture',current:'C:/Mods/Example',canCreate:true,
          projects:[{path:'C:/Mods/Example',name:'Example',version:'',valid:true,current:true,
            readOnly:false}]})}};
      document.body.insertAdjacentHTML('afterbegin','<div id="shell"></div>');
      window.shell=LexeditorUI.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},
        tabs:[],activeTab:()=>'',navigate(){},
        dirtyCount:()=>1,save:async()=>{},
        history:{capture:()=>({}),restore(){},enabled:()=>true,limit:50},
        pendingChanges:()=>[{label:'Weight',before:1,after:2}],
        help(){},info(){}});
    }""")
    page.wait_for_timeout(250)
    fit = page.evaluate("""()=>{
      const row=document.querySelector('.lex-shell-command-row');
      const box=row.getBoundingClientRect();
      const controls=[...row.querySelectorAll('button, .lex-ui-scale, input')]
        .filter(node=>node.offsetWidth>0)
        .map(node=>node.getBoundingClientRect().right);
      return {right:box.right, innerWidth:innerWidth,
        bodyWidth:document.body.scrollWidth,
        furthest:Math.max(...controls,0),
        groups:Object.fromEntries(['lex-shell-start','lex-shell-center-actions','lex-shell-end']
          .map(name=>[name,Math.round(document.querySelector('.'+name).getBoundingClientRect().width)])),
        scaleVisible:!!document.querySelector('.lex-ui-scale')?.offsetWidth};
    }""")
    assert fit["bodyWidth"] <= width + 2, fit
    assert fit["furthest"] <= width + 1, fit
    # The scale slider is kept wherever there is room for it; a window that
    # cannot hold the whole rail drops it rather than overflowing.
    assert fit["scaleVisible"] or width <= 650, fit


TOAST = "The selected file did not load, so nothing was saved."


def toast_box(page):
    return page.locator(".lex-toast").last.evaluate("""n=>{
      const box=n.getBoundingClientRect();
      const range=document.createRange();
      range.selectNodeContents(n);
      const lines=range.getClientRects();
      return {left:Math.round(box.left), top:Math.round(box.top),
        right:Math.round(box.right), bottom:Math.round(box.bottom),
        width:Math.round(box.width), height:Math.round(box.height),
        lineCount:lines.length, position:getComputedStyle(n).position,
        innerWidth:innerWidth, innerHeight:innerHeight};
    }""")


def test_a_toast_is_placed_by_its_stack_and_stays_on_screen(page):
    """A message must be readable wherever a game seats it.

    FF8 seats its messages under the window bar with the stack's own tokens.
    The toast used to position itself fixed, and inside the stack's transform
    that meant a box laid out against no width and no height: a couple of
    characters wide, most of it above the top of the window.
    """
    framework(page)
    page.evaluate("""(message)=>{
      document.documentElement.style.setProperty('--lex-toast-top','120px');
      document.documentElement.style.setProperty('--lex-toast-bottom','auto');
      document.documentElement.style.setProperty('--lex-toast-right','auto');
      document.documentElement.style.setProperty('--lex-toast-left','50%');
      document.documentElement.style.setProperty('--lex-toast-shift','-50% 0');
      document.documentElement.style.setProperty('--lex-toast-align','center');
      document.documentElement.style.setProperty('--lex-toast-font-size','26px');
      document.documentElement.style.setProperty('--lex-toast-padding','14px 28px');
      LexeditorUI.showToast(message);
    }""", TOAST)
    page.wait_for_timeout(200)
    box = toast_box(page)
    assert box["position"] != "fixed", box
    assert box["top"] >= 0 and box["bottom"] <= box["innerHeight"] + 1, box
    assert box["left"] >= 0 and box["right"] <= box["innerWidth"] + 1, box
    # Under the bar, centred, and wide enough for the sentence rather than one
    # character per line.
    assert abs(box["top"] - 120) <= 6, box
    assert abs((box["left"] + box["right"]) / 2 - box["innerWidth"] / 2) <= 6, box
    assert box["lineCount"] <= 2, box
    assert box["width"] >= 260, box


def test_a_toast_with_no_game_tokens_sits_in_the_corner(page):
    framework(page)
    page.evaluate("(message)=>LexeditorUI.showToast(message)", TOAST)
    page.wait_for_timeout(200)
    box = toast_box(page)
    assert box["bottom"] <= box["innerHeight"] + 1 and box["top"] >= 0, box
    assert box["right"] <= box["innerWidth"] + 1, box
    assert box["left"] > box["innerWidth"] * 0.35, box
    assert box["bottom"] > box["innerHeight"] * 0.6, box
    assert box["lineCount"] <= 2, box
