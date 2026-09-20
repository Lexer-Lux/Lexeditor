import pytest
from test_shared_ui_feedback import ROOT, page, framework

@pytest.mark.parametrize('width',[700,1000,1600])
def test_tabs_share_one_row_and_tweaks_stays_attached(page,width):
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
          return {rows:new Set(buttons.map(b=>b.offsetTop)).size,
            inside:buttons.every(b=>b.getBoundingClientRect().right<=r.right+1)};
        }''')
        assert result=={'rows':1,'inside':True},result
    nav=page.locator('.lex-shell-header nav')
    for label in nav.locator('.lex-tab-label-text').all():
        assert label.evaluate('n=>n.scrollWidth<=n.clientWidth+1'),label.text_content()
    assert nav.locator('button').last.get_attribute('data-tab')=='settings'
    assert nav.locator('button').last.evaluate('n=>getComputedStyle(n).marginLeft')=='0px'
    brand=page.locator('.lex-brand-button')
    assert brand.evaluate('n=>!n.dispatchEvent(new MouseEvent("mousedown",{bubbles:true,cancelable:true}))')

def test_help_scales_with_its_heading(page):
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;document.querySelector('main').append(U.el('div',{style:'font-size:30px'},U.infoHelp('Help')))}''')
    help=page.locator('.lex-info-help')
    assert help.bounding_box()['width']>=30
    assert help.evaluate('n=>getComputedStyle(n).backgroundColor')=='rgb(255, 255, 255)'
