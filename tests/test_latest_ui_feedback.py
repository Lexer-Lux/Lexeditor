"""Shared layout regressions reported from the FF8 editor."""
from test_shared_ui_feedback import ROOT, page, framework


def test_pager_controls_stay_centered_with_unequal_sides(page):
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;document.querySelector('main').append(
      U.pager({inline:true,page:2,pages:20,total:400,pageSize:20,
        search:{value:'',change(){}},filters:[U.pagerToggle({label:'A long filter',checked:true})]}))}''')
    bar=page.locator('.lex-pager').bounding_box()
    controls=page.locator('.lex-pager-controls').bounding_box()
    assert abs(controls['x']+controls['width']/2-bar['x']-bar['width']/2)<1
    summary=page.locator('.lex-page-summary').bounding_box()
    assert abs(summary['x']+summary['width']-(bar['x']+bar['width']-12))<2


def test_three_pane_divider_can_use_room_beyond_narrow_middle(page):
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;document.querySelector('main').append(
      U.panelLayout([U.detailPanel({title:'AI'}),U.detailPanel({title:'List'}),U.detailPanel({title:'Detail'})],
        {defaultSizes:[400,200,560],minSizes:[200,200,250]}))}''')
    page.wait_for_timeout(100)
    divider=page.locator('[role=separator]').first
    box=divider.bounding_box();x=box['x']+box['width']/2;y=box['y']+50
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+180,y,steps=12);page.mouse.up()
    assert divider.bounding_box()['x']>box['x']+150
    new=divider.bounding_box();x=new['x']+new['width']/2
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-180,y,steps=12);page.mouse.up()
    assert abs(divider.bounding_box()['x']-box['x'])<2


def test_tab_hover_does_not_move_or_resize_label(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{const U=LexeditorUI;document.body.prepend(U.el('div',{id:'shell'}));
      U.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},
      tabs:['Items','Characters','Enemies'].map(id=>({id,label:id})),activeTab:()=> 'Items',navigate(){}});
      U.finishPluginLoading()}''')
    page.wait_for_timeout(200)
    label=page.locator('nav button.active .lex-tab-label-text')
    before=label.bounding_box();font=label.evaluate('n=>getComputedStyle(n).fontSize')
    label.hover();page.wait_for_timeout(100)
    assert label.bounding_box()==before
    assert label.evaluate('n=>getComputedStyle(n).fontSize')==font
    assert page.locator('nav button.active').evaluate('''n=>{
      const p=getComputedStyle(n,'::before'),range=document.createRange();
      range.selectNodeContents(n.querySelector('.lex-tab-label-text'));
      const tip=n.getBoundingClientRect().left+parseFloat(getComputedStyle(n).borderLeftWidth)+parseFloat(p.left)+parseFloat(p.width);
      return Math.abs(range.getBoundingClientRect().left-tip-6)<2
    }''')


def test_instruction_wheel_turns_page_without_scrolling_footer(page):
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;document.querySelector('main').append(U.instructionList({
      rows:Array.from({length:40},(_,id)=>({id})),describe:r=>'Step '+r.id,controls:()=>U.el('input',{value:'1'})}))}''')
    page.wait_for_timeout(200)
    footer=page.locator('.lex-instruction-footer').bounding_box()
    page.locator('.lex-instruction-description').first.hover();page.mouse.wheel(0,180)
    page.wait_for_timeout(100)
    assert page.locator('.lex-page-number').input_value()=='2'
    assert page.locator('.lex-instruction-footer').bounding_box()==footer


def test_subtab_selection_and_hover_preserve_all_boxes(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{const U=LexeditorUI;
      document.querySelector('main').append(U.subtabBar({
        tabs:[{id:'gameplay',label:'Gameplay'},{id:'ffnx',label:'FFNx'}],
        active:'gameplay',change(){}}))}''')
    page.wait_for_timeout(200)
    tabs=page.locator('.lex-subtab-button')
    before=[tabs.nth(i).bounding_box() for i in range(2)]
    labels=[tabs.nth(i).locator('.lex-tab-label').bounding_box() for i in range(2)]
    for selected in [1,0,1]:
        tabs.nth(selected).hover()
        page.evaluate('''selected=>document.querySelectorAll('.lex-subtab-button')
          .forEach((n,i)=>n.classList.toggle('active',i===selected))''',selected)
        page.wait_for_timeout(100)
        assert [tabs.nth(i).bounding_box() for i in range(2)]==before
        assert [tabs.nth(i).locator('.lex-tab-label').bounding_box() for i in range(2)]==labels


def test_mod_menu_has_live_toggles_and_drag_order(page):
    page.evaluate('''()=>window.pywebview={api:{mod_library_status:async()=>({canManage:true})}}''')
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;document.body.prepend(U.el('div',{id:'shell'}));
      window.modChanges=[];U.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},tabs:[],
        activeTab:()=>'',navigate(){},projectSnapshot:async()=>({canCreate:false,projects:[]}),
        projectSources:()=>[{key:'vanilla',label:'Vanilla',readOnly:true},
          {key:'a',label:'First mod',managed:true,enabled:false},{key:'b',label:'Second mod',managed:true}],
        projectActiveSource:()=> 'a',sourcesReplaceProjects:true,addProjectSource(){},
        changeProjectSource:async(key,change)=>modChanges.push([key,change])});U.finishPluginLoading()}''')
    page.locator('.lex-project-select').click()
    rows=page.locator('.lex-project-reference')
    assert rows.first.locator('input[type=checkbox],.lex-project-source-status').count()==0
    toggle=page.get_by_role('checkbox',name='Enable First mod')
    assert toggle.is_enabled()
    assert toggle.evaluate('n=>getComputedStyle(n).opacity')=='1'
    assert page.locator('.lex-project-select .lex-project-source-status').is_hidden()
    actions=page.locator('.lex-project-menu-actions > button:visible')
    assert actions.count()==2
    assert abs(actions.nth(0).bounding_box()['width']-actions.nth(1).bounding_box()['width'])<1
    assert actions.first.inner_text()=='➕ Add a Mod'
    assert page.locator('.lex-mod-drag-handle').count()==0
    rows.nth(1).locator('.lex-project-menu-name').drag_to(rows.nth(2))
    assert page.evaluate('modChanges')==[['a',{'move':1}]]
    page.get_by_role('checkbox',name='Enable First mod').click()
    assert page.evaluate('modChanges.at(-1)')==['a',{'enabled':True}]


def test_platform_settings_use_six_columns_without_scrolling(page):
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;document.querySelector('main').append(U.platformConfigView({config:{
      available:true,runtime:'Example',sections:[{label:'Main',fields:Array.from({length:80},(_,i)=>({
        id:i,key:'value'+i,label:'Setting '+String(i).padStart(2,'0'),kind:i%2?'boolean':'integer',value:32768,minimum:0,maximum:99999}))}]
    },change(){},search(){},showHeader:false}))}''')
    page.wait_for_timeout(200)
    assert page.locator('.lex-tweak-column').count()==6
    assert page.locator('.lex-tweaks-scroll').evaluate('n=>n.scrollHeight<=n.clientHeight+1')
    widths=page.locator('.lex-tweak-column').evaluate_all('ns=>ns.map(n=>n.clientWidth)')
    assert max(widths)-min(widths)<=1
    for _ in range(20):
        assert page.locator('.lex-tweaks-scroll').evaluate('n=>n.scrollHeight<=n.clientHeight+1')
        next=page.get_by_role('button',name='Next page',exact=True)
        if next.count()==0 or next.is_disabled():
            break
        next.click()
        page.wait_for_timeout(100)
    else:
        raise AssertionError('Settings pages did not end')
