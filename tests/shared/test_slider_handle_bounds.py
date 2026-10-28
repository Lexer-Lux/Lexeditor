"""A hovered numeric grip remains inside its input at either endpoint."""
import os
from test_shared_ui_feedback import page, framework
import pytest


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
    page.wait_for_timeout(180)
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


def test_slider_stops_when_project_locks_during_drag(page):
    framework(page)
    page.evaluate('''()=>{const U=LexeditorUI;
      document.querySelector('main').append(U.detailField({label:'Amount',
        control:U.el('input',{type:'number',min:0,max:100,value:50})}));}''')
    field=page.locator('.lex-detail-field')
    field.hover()
    handle=field.locator('.lex-value-handle')
    box=handle.bounding_box()
    page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
    page.mouse.down()
    page.evaluate("document.documentElement.dataset.lexProjectReadonly='true'")
    page.mouse.move(box['x']+80,box['y']+box['height']/2,steps=3)
    page.mouse.up()
    assert page.locator('input').input_value() == '50'
    assert handle.evaluate("e=>getComputedStyle(e).pointerEvents") == 'none'
    assert handle.evaluate("e=>getComputedStyle(e).opacity") == '0'


@pytest.mark.parametrize('attrs,start,delta,want', [
    ({'min': 0}, 50, 100, 150),
    ({'min': 0}, 2, -100, 0),
    ({'min': 1}, 24, -100, 1),
    ({'max': 100}, 50, 100, 100),
    ({}, 0, -100, -100),
    ({'min': 0}, 10000, 100, 20000),
])
def test_uncapped_slider_drag_respects_only_declared_bounds(page, attrs, start, delta, want):
    framework(page)
    page.evaluate('''({attrs,start})=>{const U=LexeditorUI;
      window.commits=0;
      document.querySelector('main').append(U.detailField({label:'Recovery',
        control:U.unitField(U.el('input',{type:'number',step:1,value:start,...attrs,
          onchange:()=>commits++}),'/s')}));}''', {'attrs': attrs, 'start': start})
    field=page.locator('.lex-detail-field')
    field.hover()
    page.wait_for_timeout(180)
    handle=field.locator('.lex-value-handle')
    box=handle.bounding_box()
    x,y=round(box['x']+box['width']/2),round(box['y']+box['height']/2)
    page.mouse.move(x,y)
    page.mouse.down()
    page.mouse.move(x+delta,y,steps=5)
    page.mouse.up()
    assert page.locator('input').evaluate("n=>Number(n.value.replaceAll(',',''))")==want
    assert page.evaluate('commits')==1
    # Exact entry remains uncapped and moves the fill as well.
    page.locator('input').fill('0' if 'max' in attrs else '100000')
    assert page.locator('input').evaluate("n=>Number(n.value.replaceAll(',',''))")== (0 if 'max' in attrs else 100000)
    if os.environ.get('LEX_SLIDER_SCREENSHOT') and start == 50 and 'min' in attrs:
        page.screenshot(path=os.environ['LEX_SLIDER_SCREENSHOT'])
