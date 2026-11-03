"""Native dropdowns must not reserve the arrow space twice."""
import os
from pathlib import Path
import pytest
from test_shared_ui_feedback import ROOT, page, framework


@pytest.mark.parametrize('generated_font', [False, True], ids=['fallback', 'ff8-font'])
def test_ai_dropdown_labels_fit(page, generated_font):
    font=Path(os.environ['LOCALAPPDATA'])/'Lexeditor/game-data/ff8/generated/ff8-menu.ttf'
    if generated_font and not font.is_file():
        pytest.skip('The generated FF8 menu font is unavailable')
    if generated_font:
        page.route('**/assets/ff8-menu.ttf*', lambda route: route.fulfill(path=str(font)))
    else:
        page.route('**/assets/ff8-menu.ttf*', lambda route: route.abort())
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    framework(page)
    page.evaluate('''async generatedFont=>{
      const loaded=await document.fonts.load('17px "FF8 Menu"').catch(()=>[]);
      if(generatedFont&&!loaded.length)throw new Error('FF8 menu font did not load');
      const U=LexeditorUI;
      document.querySelector('main').style.display='block';
      for(const text of ['Attacker','Difficulty','Random value']){
        const select=U.autoFitControlText(U.el('select',{},U.el('option',{},text)));
        const source=U.provenanceControl({control:select,current:()=>1,vanilla:1,internal:true});
        document.querySelector('main').append(U.el('label',{class:'lex-instruction-operand'},'Test',source));
      }
    }''', generated_font)
    for width in [90,110,140]:
        page.locator('.lex-instruction-operand').evaluate_all('(nodes,w)=>nodes.forEach(n=>n.style.width=w+"px")',width)
        page.wait_for_timeout(100)
        results=page.locator('select').evaluate_all('''nodes=>nodes.map(n=>{
          const s=getComputedStyle(n),c=document.createElement('canvas').getContext('2d');
          c.font=`${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
          // Corrected reserve: pad-left plus the measured 15px arrow zone
          // (plus a live inner rail), never padding plus 22.
          const rail=parseFloat(s.getPropertyValue('--lex-internal-reference-width'))||0;
          return {padding:parseFloat(s.paddingRight),space:n.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.borderLeftWidth)-parseFloat(s.borderRightWidth)-15-rail,
            ink:c.measureText(n.selectedOptions[0].textContent).width};
        })''')
        assert all(r['padding']<=7 and r['ink']<=r['space']+1 for r in results),results
