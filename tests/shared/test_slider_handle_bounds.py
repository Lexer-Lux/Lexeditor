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
