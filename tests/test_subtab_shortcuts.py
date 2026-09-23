"""Subtab shortcuts target the visible bar and show the Shift modifier."""
from test_shared_ui_feedback import page, framework


def test_visible_subtab_shortcuts(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;window.chosen='';window.mainChosen='';
      document.body.prepend(U.el('div',{id:'shell'}));
      U.mountShell({host:'#shell',plugin:{id:'fixture',name:'Fixture'},
        tabs:['One','Two','Three'].map(id=>({id,label:id})),activeTab:()=> 'One',navigate:id=>mainChosen=id});
      U.finishPluginLoading();
      const tabs=['General','Characters','Inventory'].map(id=>({id,label:id}));
      document.querySelector('main').append(
        U.el('div',{hidden:true},U.subtabBar({tabs,change:()=>chosen='hidden'})),
        U.subtabBar({tabs,shortcuts:false,change:()=>chosen='disabled'}),
        U.subtabBar({tabs,label:'Starting data',change:id=>chosen=id}));
    }''')
    page.keyboard.press('Control+Shift+Digit2')
    assert page.evaluate('chosen')=='Characters'
    page.keyboard.press('Control+Digit3')
    assert page.evaluate('mainChosen')==page.locator('nav button[data-tab]').nth(2).get_attribute('data-tab')
    assert page.get_by_role('tablist',name='Starting data').locator('.lex-tab-shortcut').all_text_contents()==['⇧1','⇧2','⇧3']
