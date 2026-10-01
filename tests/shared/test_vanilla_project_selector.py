"""The explicit Vanilla selection is not presented as an editable mod."""
import os
import pytest
from test_shared_ui_feedback import page, framework, ROOT


@pytest.mark.parametrize('control', ['field', 'boolean'])
def test_vanilla_source_edit_offers_creation_without_creating_on_cancel(page, tmp_path, control):
    framework(page)
    page.evaluate('''() => {
      const U=LexeditorUI;
      window.created=[];
      window.pywebview={api:{mod_library_status:async()=>({canManage:true}),
        create_mod_project:async(...args)=>created.push(args)}};
      document.body.prepend(U.el('div',{id:'shell'}));
      U.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},tabs:[],
        activeTab:()=>'',navigate(){},readonly:()=>true,
        projectSnapshot:async()=>({canCreate:false,projects:[]}),
        projectSources:()=>[{key:'vanilla',label:'Vanilla',readOnly:true}],
        projectActiveSource:()=> 'vanilla',sourcesReplaceProjects:true});
      document.querySelector('main').append(
        U.detailField({label:'Price',control:U.el('input',{disabled:true,value:10})}),
        U.toggleRow({toggles:[{label:'Enabled',disabled:true,checked:true}]}),
        U.pager({search:{value:'',change(){}}}));
    }''')
    page.wait_for_function("document.querySelector('.lex-project-name')?.textContent==='Vanilla'")
    page.get_by_role('searchbox').fill('test')
    assert page.get_by_role('button',name='Create a mod',exact=True).count() == 0
    target = page.locator('.lex-detail-field-label' if control == 'field' else '.lex-toggle-name')
    box = target.bounding_box()
    page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
    page.get_by_role('button',name='Create a mod',exact=True).wait_for()
    assert page.evaluate('created') == []
    page.screenshot(path=str(tmp_path / 'vanilla-edit.png'))
    page.get_by_role('button',name='Cancel',exact=True).click()
    assert page.evaluate('created') == []
    assert page.locator('.lex-toggle input').is_checked()


def test_vanilla_snapshot_shows_one_locked_source(page):
    page.goto('http://fixture/?lexNoMod=1')
    page.add_style_tag(path=str(ROOT/'ui/framework.css'))
    page.evaluate('''()=>window.pywebview={api:{mod_library_status:async()=>({canManage:true})}}''')
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.body.prepend(U.el('div',{id:'shell'}));
      U.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},tabs:[],
        activeTab:()=>'',navigate(){},dirtyCount:()=>1,save:async()=>{},
        projectSnapshot:async()=>({canCreate:true,projects:[{name:'Vanilla',
          path:'C:/State/vanilla-view/fixture',valid:true,noMod:true,readOnly:true,current:true}]})});
    }''')
    page.wait_for_function("document.querySelector('.lex-project-name')?.textContent==='Vanilla'")
    assert page.locator('.lex-project-path').inner_text()=="The game's own data"
    assert page.locator('#global-save').is_disabled()
    page.locator('.lex-project-select').click()
    assert page.locator('.lex-project-menu-name').all_text_contents()==['Vanilla']
    assert page.get_by_role('button',name='Rename Vanilla',exact=True).count()==0
    assert 'vanilla-view' not in page.locator('.lex-project-menu').inner_text()
    if os.environ.get('LEX_VANILLA_SCREENSHOT'):
        page.screenshot(path=os.environ['LEX_VANILLA_SCREENSHOT'])
