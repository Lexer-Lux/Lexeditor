"""G14: digits in a number property grow to fill its box; the box does not grow.

Asked for bigger numbers in the same box, an earlier pass let the fitter's
ceiling follow the box's own height. The box is sized from its text, so larger
digits made a taller box, which raised the ceiling again: every numeric
property got taller instead of fuller.
"""
import pytest
from test_shared_ui_feedback import ROOT, page, framework  # noqa: F401

MEASURE = '''(fit)=>{const U=LexeditorUI,main=document.querySelector('main');main.replaceChildren();
  const input=U.el('input',{type:'number',min:0,max:9999,value:255});
  if(!fit)input.dataset.lexAutofit='false';
  main.append(U.detailField({label:'Strength',control:input}),U.detailField({label:'Name',control:U.el('input',{value:'Cloud'})}));
  return new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>setTimeout(()=>{
    const s=getComputedStyle(input),box=input.getBoundingClientRect(),row=input.closest('.lex-detail-field').getBoundingClientRect();
    const inner=input.clientHeight-parseFloat(s.paddingTop)-parseFloat(s.paddingBottom);
    r({box:box.height,row:row.height,font:parseFloat(s.fontSize),inner});},300))));}'''


@pytest.mark.parametrize('theme', ['blank', 'ff8', 'ff7r2', 'rdr2'])
def test_number_digits_fill_box_without_growing_it(page, theme):  # noqa: F811
    framework(page)
    page.add_style_tag(path=str(ROOT / f'plugins/{theme}/editor.css'))
    page.locator('main').evaluate('n=>n.style.width="700px"')
    plain = page.evaluate(MEASURE, False)
    fitted = page.evaluate(MEASURE, True)
    # The box and its property row keep the size they have without fitting.
    assert abs(fitted['box'] - plain['box']) <= 1, (plain, fitted)
    assert abs(fitted['row'] - plain['row']) <= 1, (plain, fitted)
    # And the digits use that box: a short number is not left floating in air.
    assert fitted['font'] >= plain['font'], (plain, fitted)
    assert fitted['font'] >= fitted['inner'] * .72, (plain, fitted)
