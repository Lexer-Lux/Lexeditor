"""The explicit Vanilla selection is not presented as an editable mod."""
import os
from test_shared_ui_feedback import page, framework, ROOT


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
