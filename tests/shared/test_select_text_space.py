"""Native dropdowns must not reserve the arrow space twice."""
import os
from pathlib import Path
from test_shared_ui_feedback import ROOT, page, framework


def test_ai_dropdown_labels_fit(page):
    font=Path(os.environ['LOCALAPPDATA'])/'Lexeditor/game-data/ff8/generated/ff8-menu.ttf'
    page.route('**/assets/ff8-menu.ttf*',lambda route:route.fulfill(path=str(font)))
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    framework(page)
    page.evaluate('''async()=>{
      await document.fonts.load('17px "FF8 Menu"');
      const U=LexeditorUI;
      document.querySelector('main').style.display='block';
      for(const text of ['Attacker','Difficulty','Random value']){
        const select=U.autoFitControlText(U.el('select',{},U.el('option',{},text)));
        const source=U.provenanceControl({control:select,current:()=>1,vanilla:1,internal:true});
        document.querySelector('main').append(U.el('label',{class:'lex-instruction-operand'},'Test',source));
      }
    }''')
    for width in [90,110,140]:
        page.locator('.lex-instruction-operand').evaluate_all('(nodes,w)=>nodes.forEach(n=>n.style.width=w+"px")',width)
        page.wait_for_timeout(100)
        results=page.locator('select').evaluate_all('''nodes=>nodes.map(n=>{
          const s=getComputedStyle(n),c=document.createElement('canvas').getContext('2d');
          c.font=`${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
          return {padding:parseFloat(s.paddingRight),space:n.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)-22,
            ink:c.measureText(n.selectedOptions[0].textContent).width};
        })''')
        assert all(r['padding']<=7 and r['ink']<=r['space']+1 for r in results),results
