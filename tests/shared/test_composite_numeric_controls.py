"""Every numeric part uses the same slider behavior as a scalar property."""
from test_shared_ui_feedback import ROOT, framework, page  # noqa: F401


def test_vector_axes_have_independent_sliders_and_preserve_bounds(page, tmp_path):  # noqa: F811
    framework(page)
    page.add_style_tag(path=str(ROOT / 'plugins/ds1/editor.css'))
    page.evaluate('''() => {
      const U=LexeditorUI;
      window.changes=[];
      const axes=['X','Y','Z'].map((label,index)=>({label,control:U.el('input',{
        type:'number',min:-100,max:100,step:'any',value:10*index,
        'aria-label':`Position ${label}`,onchange:e=>changes.push([label,Number(e.target.value)])})}));
      document.querySelector('main').append(U.detailPanel({title:'Vertex 0',body:[
        U.detailField({label:'Position',control:U.multiNumberRow(axes,{columns:3,nowrap:true})}),
        U.detailField({label:'Read only',control:U.multiNumberRow([
          {label:'X',control:U.el('input',{type:'number',min:0,max:100,value:3,disabled:true})}])}),
        U.detailField({label:'Scalar',control:U.el('input',{type:'number',min:0,max:100,value:50})})]}));
    }''')
    parts=page.locator('.lex-multi-number-item').filter(has=page.locator('input:not(:disabled)'))
    assert parts.count()==3
    assert page.locator('.lex-value-fill').count()==4
    for index in range(3):
        ratio=parts.nth(index).locator('.lex-value-fill').evaluate(
            "n=>Number(n.style.getPropertyValue('--lex-value-ratio'))")
        assert abs(ratio-(100+10*index)/200)<1e-8
    box=parts.nth(1).locator('input').bounding_box()
    page.locator('main').hover()
    parts.nth(1).hover()
    handle=parts.nth(1).locator('.lex-value-handle')
    handle.hover(force=True)
    handle_box=handle.bounding_box()
    page.mouse.move(handle_box['x']+handle_box['width']/2,handle_box['y']+handle_box['height']/2)
    page.mouse.down()
    page.mouse.move(box['x']+box['width']*.75,box['y']+box['height']/2,steps=4)
    page.mouse.up()
    assert page.get_by_label('Position X',exact=True).input_value()=='0'
    assert page.get_by_label('Position Z',exact=True).input_value()=='20'
    assert 40<float(page.get_by_label('Position Y',exact=True).input_value())<60
    assert page.evaluate('changes.at(-1)[0]')=='Y'
    page.get_by_label('Position Z',exact=True).focus()
    page.keyboard.press('ArrowUp')
    assert float(page.get_by_label('Position Z',exact=True).input_value())==20.1
    page.screenshot(path=str(tmp_path/'vector-controls.png'))
