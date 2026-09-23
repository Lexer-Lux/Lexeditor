"""Panel navigation must keep invalid AI drafts and stable table geometry."""
from test_shared_ui_feedback import ROOT, page, framework


def test_sort_pointer_does_not_resize_columns(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''() => {
      const U=LexeditorUI;
      document.querySelector('main').append(U.columnList({
        rows:[{id:1,name:'Accelerator',price:100},{id:2,name:'Potion',price:20}],
        columns:['id','name','price'].map(key=>({key,label:key,sortable:true}))}));
    }''')
    headers=page.locator('[role="columnheader"]')
    before=headers.evaluate_all('ns=>ns.map(n=>n.getBoundingClientRect().width)')
    for index in [0,1,2,2]:
        headers.nth(index).click()
        after=headers.evaluate_all('ns=>ns.map(n=>n.getBoundingClientRect().width)')
        assert after==before
        assert page.locator('.lex-sort-indicator').evaluate('n=>getComputedStyle(n).position')=='absolute'


def test_panel_tabs_have_no_number_badges_and_code_fills_panel(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''() => {
      const U=LexeditorUI;
      const code=U.provenanceControl({control:U.codeField(),current:()=>'',vanilla:'',internal:true});
      const panel=U.tabbedPanel({tabs:[{id:'a',label:'Init'},{id:'b',label:'Turn'}],active:'a',content:code});
      panel.style.width='600px';panel.style.height='500px';document.querySelector('main').append(panel);
    }''')
    assert page.locator('.lex-tab-shortcut').count()==0
    tab=page.get_by_role('tab',name='Init')
    before=tab.bounding_box();tab.hover()
    assert tab.bounding_box()==before
    code=page.locator('textarea').bounding_box()
    panel=page.locator('.lex-tabbed-panel').bounding_box()
    assert code['width']>=panel['width']-8
    assert abs(code['y']+code['height']-panel['y']-panel['height'])<8


def test_ai_compile_failure_blocks_navigation_and_keeps_source(page):
    framework(page)
    source=(ROOT/'plugins/ff8/party.js').read_text(encoding='utf-8')
    guard=source[source.index('  async function enemyAiApplySource('):source.index('  function enemyAiPanel(')]
    boot=(ROOT/'plugins/ff8/boot.js').read_text(encoding='utf-8')
    navigation=next(line for line in boot.splitlines() if 'async function navigate(tab)' in line)
    page.add_script_tag(content='''
      const row={id:1,name:'Enemy'},documentData={scripts:[{id:0,source:'bad draft'}]};
      const state={tab:'enemies',data:{},enemyAiDirtyRow:row};
      const enemyAiRow=()=>documentData,post=x=>x,enemyAiNormalizeScript=()=>{};
      const shell={refresh:()=>{}},setStatus=()=>{},showAlert=()=>{};
      let fail=true,requests=0,renders=0;
      const api=async()=>{requests++;if(fail)throw Error('Invalid instruction');
        return {scripts:[{id:0}],sources:['valid code']}};
      const render=()=>{renders++};
    '''+guard+navigation)
    page.evaluate("navigate('items')")
    assert page.evaluate('[state.tab,documentData.scripts[0].source,renders,requests]')==['enemies','bad draft',0,1]
    page.evaluate("fail=false;navigate('items')")
    assert page.evaluate('[state.tab,documentData.scripts[0].source,renders,requests]')==['items','valid code',1,2]
    page.evaluate("navigate('cards')")
    assert page.evaluate('requests')==2
