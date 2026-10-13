"""Wide integer bounds and stepping retain every digit in native controls."""
from test_shared_ui_feedback import page, framework


def test_wide_integer_control_preserves_bounds_and_steps(page):
    framework(page)
    page.evaluate("""()=>{
      const U=LexeditorUI;window.changes=[];
      document.querySelector('main').append(U.detailField({label:'Count',dataType:'INT',
        control:U.unitField(U.exactIntegerInput({value:'18446744073709551615',min:1,max:'18446744073709551615',
          label:'Count',change:value=>changes.push(value)}),'units')}));
    }""")
    count = page.get_by_label('Count', exact=True)
    page.wait_for_timeout(100)
    assert count.get_attribute('type') == 'number'
    assert count.input_value() == '18446744073709551615'
    assert page.locator('.lex-unit').evaluate("""unit=>{
      const input=unit.parentElement.querySelector('input'),style=getComputedStyle(input);
      const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
      ctx.font=`${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      const end=input.getBoundingClientRect().left+parseFloat(style.paddingLeft)+ctx.measureText(input.value).width;
      return unit.getBoundingClientRect().left>=end-1;
    }""")
    count.press('ArrowDown')
    assert count.input_value() == '18446744073709551614'
    page.get_by_role('button', name='Increase', exact=True).click()
    assert count.input_value() == '18446744073709551615'
    count.press('ArrowUp')
    assert page.evaluate('changes') == ['18446744073709551614', '18446744073709551615']
    for invalid in ['18446744073709551616', '0', '1.5', '']:
        count.fill(invalid)
        count.blur()
        assert not count.evaluate('input=>input.checkValidity()')
        assert len(page.evaluate('changes')) == 2
    count.fill('9007199254740993')
    count.press('ArrowUp')
    assert page.evaluate('changes.at(-1)') == '9007199254740994'
    assert count.input_value() == '9007199254740994'
    assert page.evaluate("LexeditorUI.formatNumber('18446744073709551615')") == '18,446,744,073,709,551,615'
    assert page.locator('.lex-value-handle').count() == 0


def test_disabled_exact_integer_cannot_step(page):
    framework(page)
    page.evaluate("""()=>{
      const U=LexeditorUI;window.changes=[];
      const control=U.exactIntegerInput({value:5,min:1,max:10,label:'Locked',change:value=>changes.push(value)});
      control.querySelector('input').disabled=true;document.querySelector('main').append(control);
    }""")
    page.get_by_role('button', name='Increase', exact=True).click()
    assert page.get_by_label('Locked').input_value() == '5'
    assert page.evaluate('changes') == []
