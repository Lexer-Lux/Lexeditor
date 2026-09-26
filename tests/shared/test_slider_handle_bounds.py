"""A hovered numeric grip remains inside its input at either endpoint."""
import os
from test_shared_ui_feedback import page, framework


def test_numeric_grip_stays_inside_during_resize(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.querySelector('main').append(U.detailField({label:'Zoom',
        control:U.el('input',{type:'number',min:1,max:65535,value:1})}));
    }''')
    field=page.locator('.lex-detail-field')
    field.hover()
    for width in [240, 263, 311, 400, 640]:
        field.evaluate('(n,w)=>n.style.width=w+"px"',width)
        for value in [1, 2, 32768, 65534, 65535]:
            page.locator('input').fill(str(value))
            assert field.evaluate('''n=>{
              const input=n.querySelector('input').getBoundingClientRect();
              const grip=n.querySelector('.lex-value-handle').getBoundingClientRect();
              return grip.left>=input.left && grip.right<=input.right;
            }'''), (width,value)
    if os.environ.get('LEX_SLIDER_SCREENSHOT'):
        page.screenshot(path=os.environ['LEX_SLIDER_SCREENSHOT'])


def test_int32_slider_drag_and_precise_entry(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.querySelector('main').append(U.detailField({label:'Position X',
        control:U.el('input',{type:'number',min:-2147483648,max:2147483647,step:1,value:0})}));
    }''')
    field=page.locator('.lex-detail-field')
    field.hover()
    handle=field.locator('.lex-value-handle')
    box=handle.bounding_box()
    page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
    page.mouse.down()
    page.mouse.move(box['x']+80,box['y']+box['height']/2,steps=5)
    page.mouse.up()
    value=page.locator('input').evaluate("n=>Number(n.value.replaceAll(',',''))")
    assert 0 < value <= 2147483647
    page.locator('input').fill('-12345')
    assert page.locator('input').evaluate("n=>Number(n.value.replaceAll(',',''))") == -12345
