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
    page.evaluate('''()=>{
      const U=LexeditorUI,group=U.controlGroup(['Attack animation','Target hit animation','Attack type','Spell power','Draw resist','Hit count'].map(label=>({label,control:U.el('input',{type:'number',value:10})})));
      const wrapper=U.el('div',{},group);group.style.width='500px';
      document.querySelector('main').append(wrapper);
    }''')
    for control in page.locator('.lex-detail-part-control input').all():
        assert control.bounding_box()['width']>=80
