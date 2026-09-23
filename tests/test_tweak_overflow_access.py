"""A rejected tweak layout must not make its controls unreachable."""
from test_shared_ui_feedback import page, framework
import pytest


@pytest.mark.parametrize('height',[150,1000])
def test_tweak_controls_remain_reachable(page,height):
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    framework(page)
    page.evaluate('''height=>{
      const U=LexeditorUI;
      window.bottomClicked=false;
      const card=U.detailSection({title:'Oversized fixture',body:U.stack({fill:false},
        U.el('div',{style:`height:${height}px`},'Settings'),
        U.el('button',{onclick:()=>bottomClicked=true},'Last setting'))});
      const host=document.querySelector('main');host.style.cssText='height:500px;flex:none';
      host.append(U.paginateSettings(U.el('div',{},card),{strictColumns:true,splitOversized:false}));
    }''',height)
    scroll=page.locator('.lex-tweaks-scroll')
    page.wait_for_timeout(300)
    if height>500:
        assert any('Tweak cannot fit one column' in error for error in errors), errors
    else:
        assert not errors,errors
    scroll.hover()
    page.mouse.wheel(0,2000)
    page.wait_for_timeout(300)
    assert (scroll.evaluate('n=>n.scrollTop')>0)==(height>500)
    last=page.get_by_role('button',name='Last setting',exact=True)
    box=scroll.bounding_box(); end=last.bounding_box()
    assert end['y']>=box['y'] and end['y']+end['height']<=box['y']+box['height']+1
    last.click()
    assert page.evaluate('bottomClicked')
