"""Browser checks for loading, hover cards and visible pagination bounds."""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def page():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True, ignore_default_args=['--hide-scrollbars'])
        page = browser.new_page(viewport={'width': 1200, 'height': 800})
        page.route('http://fixture/**', lambda r: r.fulfill(
            body='<main id="main"></main>', content_type='text/html'))
        page.goto('http://fixture/')
        page.add_style_tag(path=str(ROOT / 'ui/framework.css'))
        yield page
        browser.close()


def framework(page):
    page.add_script_tag(path=str(ROOT / 'ui/framework.js'))


def test_wrapped_property_labels_keep_vertical_space(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.querySelector('main').style.width='400px';
      document.querySelector('main').append(U.detailPanel({title:'GF',body:[
        'Boost phase 1 length (x15)','Boost total window (x15)'
      ].map(label=>U.detailField({label,help:U.infoHelp('Time available for Boost.'),
        control:U.el('input',{type:'number',min:0,max:255,value:22})}))}));
    }''')
    page.wait_for_timeout(250)
    for label in page.locator('.lex-detail-field-label').all():
        assert label.evaluate('''n=>{
          const r=n.getBoundingClientRect(),s=getComputedStyle(n),t=n.firstElementChild.getBoundingClientRect();
          return t.top>=r.top+parseFloat(s.paddingTop)-1 && t.bottom<=r.bottom-parseFloat(s.paddingBottom)+1;
        }''')
    assert page.locator('.lex-detail-panel').evaluate('''n=>{
      const heading=n.querySelector('.lex-detail-panel-heading'),field=n.querySelector('.lex-detail-field');
      return Math.abs(heading.getBoundingClientRect().left+parseFloat(getComputedStyle(heading).paddingLeft)-field.getBoundingClientRect().left)<1;
    }''')


def test_field_range_uses_grouped_numbers(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      for(const [min,max] of [[0,65535],[-100000,1000000],[0.125,10000.5],[null,9999]]) {
        const attrs={type:'number',value:0};
        if(min!==null)attrs.min=min;
        attrs.max=max;
        document.querySelector('main').append(U.detailField({label:'Amount',control:U.el('input',attrs)}));
      }
    }''')
    assert page.locator('.lex-field-type-range').all_text_contents()==[
        '(0-65,535)','(-100,000-1,000,000)','(0.125-10,000.5)','(…-9,999)']
    page.locator('input').first.focus()
    assert page.locator('input').first.get_attribute('max')=='65535'


def test_create_button_precedes_pager_search(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;window.created=0;
      document.querySelector('main').append(U.pager({page:0,pages:2,pageSize:10,total:20,
        search:{key:'create-position',change(){}},filters:[U.newButton({onclick:()=>created++})]}));
    }''')
    button=page.locator('.lex-pager-left .lex-new-button')
    search=page.locator('.lex-pager-left input')
    assert button.bounding_box()['x']+button.bounding_box()['width']<=search.bounding_box()['x']
    assert page.locator('.lex-pager-right .lex-new-button').count()==0
    button.click()
    assert page.evaluate('created')==1


def test_data_map_header_location_and_state(page):
    import tempfile
    framework(page)
    page.evaluate('''()=>{
      document.body.dataset.lexPlugin='ff8';
      window.revealed=[];
      window.pywebview={api:{game_data_location:async()=>({path:'C:/Game/data/kernel.bin'}),
        open_game_data_location:async(...args)=>{revealed=args;return {path:'C:/Game/data/kernel.bin'}}}};
      const map=LexeditorUI.dataMap({coverage:'unavailable',rows:[{filename:'kernel.bin',status:'partial',coverage:'structured',controls:'Battle data'}]});
      document.querySelector('main').append(map.content);
    }''')
    page.wait_for_function("document.querySelector('.lex-data-map-path')?.textContent==='C:/Game/data/kernel.bin'")
    assert page.get_by_label('Filter files by coverage').count()==0
    assert page.get_by_label('Filter files by integration').count()==1
    assert page.locator('.lex-detail-panel-id .lex-integration-status.partial').count()==1
    assert page.locator('.lex-detail-panel-body .lex-data-map-location').count()==0
    page.get_by_role('button',name='Open file location',exact=True).click()
    assert page.evaluate('revealed')==['ff8','kernel.bin']
    page.locator('.lex-data-map-detail').screenshot(path=str(Path(tempfile.gettempdir())/'lex-data-map-header.png'))


@pytest.mark.parametrize('theme',['blank','ff8'])
def test_property_help_is_always_beside_name(page,theme):
    import tempfile
    if theme=='ff8':
        page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI, main=document.querySelector('main');
      const box=U.el('div',{style:'width:600px'});main.append(box);
      for(const [label,type,showType,help] of [['Number','number',true,true],['Flag','checkbox',true,true],['Text','text',false,true],['No help','text',true,false]]){
        box.append(U.detailField({label,showType,control:U.el('input',{type,value:20}),
          help:help?U.infoHelp('Help for '+label):null}));
      }
    }''')
    page.wait_for_timeout(100)
    assert page.locator('.lex-field-type-rail .lex-info-help').count()==0
    assert page.locator('.lex-field-help').count()==3
    for field in page.locator('.lex-detail-field').all()[:3]:
        help=field.locator('.lex-field-help .lex-info-help')
        assert help.is_visible()
        assert help.evaluate('n=>getComputedStyle(n).opacity')=='1'
        control=field.locator('.lex-detail-field-control').bounding_box()
        label=field.locator('.lex-detail-field-label-text').bounding_box()
        assert help.bounding_box()['x']>=label['x']+label['width']-1
        assert help.bounding_box()['x']+help.bounding_box()['width']<=control['x']+1
        assert field.locator('.lex-detail-field-label .lex-field-help').count()==1
        text_right=field.locator('.lex-detail-field-label-text').evaluate('n=>{const r=document.createRange();r.selectNodeContents(n);return r.getBoundingClientRect().right}')
        assert help.bounding_box()['x']>=text_right+2
    rail=page.locator('.lex-field-type-rail').first
    rail.hover()
    assert rail.locator('.lex-field-type-name').evaluate('n=>getComputedStyle(n).opacity')=='1'
    page.locator('.lex-field-help .lex-info-help').first.hover()
    page.get_by_role('tooltip').wait_for()
    page.locator('main > div').screenshot(path=str(Path(tempfile.gettempdir())/'lex-property-help-right.png'))


def test_readonly_fields_keep_numeric_types(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.querySelector('main').append(...[12500,2.5,'0123'].map(value=>
        U.detailField({label:'Value',control:U.unitField(U.readonlyField(value),'G')})));
    }''')
    assert page.locator('.lex-field-type-name').all_text_contents()==['INT','FLT','STR']
    assert page.locator('input').first.input_value()=='12,500'


def test_grouped_number_keeps_commas_during_editing(page):
    framework(page)
    page.evaluate('''()=>{
      const input=LexeditorUI.el('input',{type:'number',min:0,max:655350,value:421400});
      input.addEventListener('input',()=>window.received=Number(input.value));
      document.querySelector('main').append(input);
    }''')
    control=page.locator('input')
    page.wait_for_function('document.querySelector("input").value==="421,400"')
    control.focus()
    assert control.input_value()=='421,400'
    control.fill('123456')
    page.wait_for_function('document.querySelector("input").value==="123,456"')
    assert page.evaluate('received')==123456
    control.evaluate('n=>n.setSelectionRange(2,2)')
    control.press('Backspace')
    page.wait_for_function('document.querySelector("input").value==="13,456"')
    assert control.evaluate('n=>n.selectionStart')==1
    assert page.evaluate('received')==13456


def test_value_fill_stays_behind_text_while_handle_can_drag(page):
    import tempfile
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{
      const U=LexeditorUI;
      const input=U.el('input',{type:'number',value:75,min:0,max:100,step:1});
      document.querySelector('main').append(U.detailField({label:'Hit rate',min:0,max:100,control:U.unitField(input,'%')}));
    }''')
    field=page.locator('.lex-detail-field')
    field.hover()
    page.wait_for_timeout(150)
    assert page.locator('.lex-value-fill').evaluate('n=>getComputedStyle(n).zIndex')=='auto'
    field.screenshot(path=str(Path(tempfile.gettempdir())/'lex-hit-rate-fill.png'))
    handle=page.locator('.lex-value-handle')
    box=handle.bounding_box()
    x,y=box['x']+box['width']/2,box['y']+box['height']/2
    assert page.evaluate('([x,y])=>document.elementFromPoint(x,y).classList.contains("lex-value-handle")',[x,y])
    page.mouse.move(x,y)
    page.mouse.down()
    page.mouse.move(x-80,y,steps=5)
    page.mouse.up()
    assert float(page.locator('input').input_value())<75


def test_refresh_loading_blocks_input_and_uses_shared_quote(page):
    page.evaluate('''() => {
      document.body.insertAdjacentHTML('afterbegin','<div id="lexeditor-shell"></div>');
      window.pywebview={api:{loading_quote:async()=>({quote:'A shared loading message'}),
        lexeditor_settings:async()=>({loadingTransitionMinimumSeconds:0})}};
      window.touched=0;
    }''')
    framework(page)
    page.evaluate('''() => {
      LexeditorUI.mountShell({host:'#lexeditor-shell',plugin:{id:'fixture',name:'Fixture'},tabs:[],activeTab:()=>'',navigate:()=>{}});
      const button=document.createElement('button');button.textContent='Test action';
      button.onclick=()=>touched++;document.querySelector('main').append(button);
    }''')
    page.wait_for_function("document.querySelector('.lex-plugin-loading-quote').textContent==='A shared loading message'")
    page.get_by_role('button',name='Test action').dispatch_event('click')
    assert page.evaluate('touched') == 0
    page.evaluate('LexeditorUI.finishPluginLoading()')
    page.wait_for_selector('.lex-plugin-loading-screen',state='detached')
    page.get_by_role('button',name='Test action').click()
    assert page.evaluate('touched') == 1


def test_late_quote_cannot_replace_closing_screen(page):
    page.evaluate('''()=>{
      sessionStorage.setItem('lex-loading-quote','Keep this quote');
      document.body.prepend(Object.assign(document.createElement('div'),{id:'lexeditor-shell'}));
      window.pywebview={api:{loading_quote:()=>new Promise(resolve=>window.resolveQuote=resolve),
        lexeditor_settings:async()=>({loadingTransitionMinimumSeconds:0})}};
    }''')
    framework(page)
    page.evaluate('''()=>LexeditorUI.mountShell({host:'#lexeditor-shell',plugin:{id:'fixture',name:'Fixture'},tabs:[],activeTab:()=>'',navigate(){}})''')
    page.wait_for_function('typeof resolveQuote === "function"')
    page.evaluate('''()=>{
      window.quoteNode=document.querySelector('.lex-plugin-loading-quote');
      LexeditorUI.finishPluginLoading();
      resolveQuote({quote:'Late replacement'});
    }''')
    page.wait_for_function('sessionStorage.getItem("lex-loading-quote")==="Late replacement"')
    assert page.evaluate('quoteNode.textContent')=='Keep this quote'


@pytest.mark.parametrize('zoom', [1, 1.25])
def test_table_never_extends_under_fixed_pager(page, zoom):
    framework(page)
    page.evaluate('''zoom => {
      const U=LexeditorUI, rows=Array.from({length:80},(_,id)=>({id,name:'Row '+id}));
      document.body.style.zoom=zoom;
      const view=U.pagedListDetail({rows,key:r=>r.id,selected:0,pageSize:15,
        fit:{minRowHeight:34},master:v=>U.columnList({rows:v.rows,key:r=>r.id,
          selected:v.selected,columns:[{key:'name',label:'Name'}]}),
        detail:r=>U.detailPanel({title:r.name})});
      document.querySelector('main').append(view);
      view.style.height=(800/zoom)+'px';
      Object.assign(view.querySelector('.lex-pager').style,{position:'fixed',bottom:'0',height:'52px'});
    }''', zoom)
    page.wait_for_timeout(650)
    bounds=page.evaluate('''() => {
      const rows=[...document.querySelectorAll('.lex-column-list-row')];
      return {bottom:rows.at(-1).getBoundingClientRect().bottom,
        pager:document.querySelector('.lex-pager').getBoundingClientRect().top};
    }''')
    assert bounds['bottom'] <= bounds['pager'] + 1, bounds


def test_save_preview_and_native_tooltips(page):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      document.body.insertAdjacentHTML('afterbegin','<div id="shell"></div>');
      U.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},tabs:[],activeTab:()=>'',navigate:()=>{}});
      const save=U.settingsSaveControl({dirtyCount:()=>2,pendingChanges:()=>[
        {label:'Sell price',before:200,after:300},{label:'Item name',before:'Old',after:'New'}]});
      save.style.marginLeft='500px';document.querySelector('main').append(save);
      const help=U.infoHelp('This card explains the effect of the setting.');
      document.querySelector('main').append(help);
      window.save=save;
    }''')
    page.wait_for_timeout(100)
    assert page.locator('[title]').count() == 0
    page.evaluate("save.title='Changed native tooltip'")
    page.wait_for_timeout(80)
    assert page.locator('[title]').count() == 0
    page.locator('.lex-settings-save-control').hover()
    popup=page.locator('.lex-save-preview')
    assert popup.is_visible()
    assert 'Pending changes' not in popup.inner_text()
    box=popup.bounding_box();button=page.locator('.lex-settings-save-control').bounding_box()
    assert abs(box['x']+box['width']/2-button['x']-button['width']/2)<2
    assert popup.locator('li').evaluate_all("rows=>rows.every(n=>getComputedStyle(n).whiteSpace==='nowrap')")
    assert popup.evaluate("n=>getComputedStyle(n,'::before').content") == 'none'
    page.locator('.lex-info-help').last.hover()
    card=page.locator('.lex-help-popover:not(.lex-save-preview)')
    assert card.is_visible()
    page.wait_for_timeout(150)
    assert card.evaluate("n=>getComputedStyle(n).opacity") == '1'
    assert card.evaluate("n=>getComputedStyle(n).backgroundColor") != 'rgba(0, 0, 0, 0)'


def test_save_preview_does_not_cover_bottom_save_button(page):
    framework(page)
    page.evaluate('''() => {
      window.saved=0;
      const button=LexeditorUI.settingsSaveControl({dirtyCount:()=>1,
        pendingChanges:()=>[{label:'Panel spacing',before:.25,after:.85}],
        save:async()=>{window.saved++}});
      Object.assign(button.style,{position:'fixed',right:'20px',bottom:'10px'});
      document.body.append(button);
    }''')
    button=page.locator('.lex-settings-save-control')
    button.hover()
    page.wait_for_timeout(120)
    popup=page.locator('.lex-save-preview')
    box=popup.bounding_box()
    target=button.bounding_box()
    assert box['y']+box['height'] <= target['y']-7
    button.click(timeout=1500)
    assert page.evaluate('window.saved')==1


def test_save_preview_dismisses_when_button_disables(page):
    framework(page)
    page.evaluate('''() => {
      const button=LexeditorUI.settingsSaveControl({dirtyCount:()=>1,
        pendingChanges:()=>[{label:'Panel spacing',before:.25,after:.85}]});
      document.body.append(button);window.saveButton=button;
    }''')
    button=page.locator('.lex-settings-save-control')
    button.hover()
    page.locator('.lex-save-preview').wait_for(state='visible')
    page.evaluate('saveButton.disabled=true')
    page.wait_for_function("!document.querySelector('.lex-save-preview')")
    button.hover()
    page.wait_for_timeout(150)
    assert page.locator('.lex-save-preview').count()==0


def test_readonly_pin_does_not_cover_lock(page):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI,pin=U.el('button',{class:'lex-column-pin pinned'},'📌');
      document.querySelector('main').append(U.detailPanel({title:'Example',body:[
        U.detailField({label:'Sell price',pin,control:U.unitField(U.el('input',{
          type:'text',readOnly:true,value:'190,000'}),'G')})]}));
    }''')
    page.wait_for_timeout(200)
    assert page.evaluate('''() => {
      const p=document.querySelector('.lex-column-pin').getBoundingClientRect();
      const l=document.querySelector('.lex-field-readonly-lock').getBoundingClientRect();
      return p.right<=l.left||p.left>=l.right||p.bottom<=l.top||p.top>=l.bottom;
    }''')


def test_mod_actions_use_one_dropdown(page):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;window.changes=[];let secondEnabled=true;
      document.body.insertAdjacentHTML('afterbegin','<div id="shell"></div>');
      U.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},tabs:[],activeTab:()=>'',navigate:()=>{},
        projectSnapshot:async()=>({canCreate:false,projects:[]}),sourcesReplaceProjects:true,
        projectSources:()=>[{key:'mine',label:'First mod',managed:true,enabled:true},
          {key:'second',label:'Second mod',managed:true,enabled:secondEnabled,removable:true}],
        changeProjectSource:async(key,change)=>{changes.push({key,...change});if(change.enabled!==undefined)secondEnabled=change.enabled},
        addProjectSource:async()=>changes.push({add:true})});
    }''')
    page.get_by_role('button',name='Active mod project',exact=True).click()
    page.get_by_role('checkbox',name='Enable Second mod').uncheck()
    page.locator('.lex-project-reference').nth(1).press('Alt+ArrowUp')
    page.get_by_role('button',name='Remove Second mod',exact=True).click()
    page.get_by_role('button',name='Remove',exact=True).click()
    page.wait_for_timeout(100)
    assert page.evaluate('changes') == [
        {'key':'second','enabled':False},{'key':'second','move':-1},{'key':'second','remove':True}]
    assert page.get_by_text('Mod library…',exact=True).count()==0
    assert page.get_by_text('Featured',exact=True).count()==0


def test_ff8_dropdown_preserves_options_when_reordering(page):
    source=(ROOT/'plugins/ff8/boot.js').read_text(encoding='utf-8')
    change=source[source.index('  async function changeProjectSource('):source.index('  function addProjectSource(')]
    page.add_script_tag(content='''
      let db={rows:[{id:'a',selected:true,enabled:true,folderOptions:{quality:2}},
        {id:'b',enabled:false,folderOptions:{music:1}}]};
      const state={activeSource:'mine'},shell={refresh(){}},clone=structuredClone;
      let sent;
      const post=body=>({body});
      async function api(path,request){
        if(path==='/api/mods')return structuredClone(db);
        sent=request.body;
        db.rows=sent.order.map(id=>({...db.rows.find(r=>r.id===id),
          enabled:sent.enabled[id],folderOptions:sent.folderOptions[id]}));
        return structuredClone(db);
      }
    '''+change)
    page.evaluate("changeProjectSource('mod:b',{move:-1})")
    assert page.evaluate('sent') == {'order':['b','a'],'enabled':{'a':True,'b':False},
        'folderOptions':{'a':{'quality':2},'b':{'music':1}}}
    page.evaluate("changeProjectSource('mod:b',{enabled:true})")
    assert page.evaluate('sent.enabled.b') is True
    page.evaluate("changeProjectSource('mod:b',{option:'music',value:0})")
    assert page.evaluate('sent.folderOptions') == {'a':{'quality':2},'b':{'music':0}}


def test_find_project_does_not_require_package_adapter():
    from unittest.mock import Mock
    from core.desktop_host import HostApi
    api=object.__new__(HostApi)
    api._projects=Mock()
    api._projects.snapshot.return_value={'current':'C:/old'}
    api._projects.select.return_value={'current':'C:/chosen'}
    api._projects.contents.return_value={'files':[]}
    api._choose_folder=Mock(return_value='C:/chosen')
    api._restart_for_project=Mock(return_value={'url':'http://fixture'})
    api.mod_library_status=Mock(side_effect=AssertionError('Package adapter must not gate projects'))
    assert api.browse_mod_project('ff8')['url']=='http://fixture'
    api._projects.select.assert_called_once_with('ff8','C:/chosen')

