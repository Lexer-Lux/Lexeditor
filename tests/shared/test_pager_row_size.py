"""The two-digit Rows control must not shrink itself through ch sizing."""
import pytest
import tempfile
from pathlib import Path
from test_shared_ui_feedback import page, framework, ROOT


@pytest.mark.parametrize('theme',['blank','ff8'])
def test_rows_text_stays_readable_through_focus_and_refits(page,theme):
    if theme=='ff8':
        page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    framework(page)
    page.evaluate('''()=>document.querySelector('main').append(LexeditorUI.pager({
      page:0,pages:3,total:78,pageSize:26,rowControl:{value:26,defaultValue:40,change(){}}
    }))''')
    control=page.get_by_role('spinbutton',name='Rows on this page')
    page.wait_for_timeout(300)
    for value in ['5','26','80']:
        control.evaluate('(n,value)=>{n.value=value;n.dispatchEvent(new Event("input",{bubbles:true}))}',value)
        page.wait_for_timeout(150)
        size=control.evaluate('n=>parseFloat(getComputedStyle(n).fontSize)')
        assert size>=24,size
        compact=control.bounding_box()['width']
        control.focus()
        page.wait_for_timeout(200)
        assert control.bounding_box()['width']>=compact+16
        assert control.evaluate('n=>parseFloat(getComputedStyle(n).fontSize)')==size
        control.blur()
        page.wait_for_timeout(200)
        assert abs(control.bounding_box()['width']-compact)<1
    page.locator('.lex-pager').screenshot(path=str(Path(tempfile.gettempdir())/f'lex-rows-{theme}.png'))
