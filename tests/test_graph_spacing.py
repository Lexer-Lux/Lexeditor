"""Graph ink has equal margins at every panel aspect ratio."""
from pathlib import Path
import tempfile
from test_shared_ui_feedback import page, framework


def test_graph_margins_and_drawer(page):
    framework(page)
    page.add_style_tag(content='main{flex:none!important;min-height:0!important}')
    page.add_style_tag(content=':root{--lex-panel:#fff;--lex-text:#222;--lex-panel-2:#eef1f3;--lex-border:#c4ccd2}main{display:block}.lex-curve-editor,.lex-curve-plot{height:100%;box-sizing:border-box}.lex-curve-svg{height:100%;aspect-ratio:auto}')
    page.evaluate('''()=>{const U=LexeditorUI;
      document.querySelector('main').append(U.curveEditor({title:'Linear',domain:{min:1,max:100},range:{min:0,max:500},evaluate:x=>x,
        formula:U.mathFormula('Value = Level * A'),variables:[{label:'A',control:U.el('input',{type:'number',value:1})}]}));}''')
    for width,height in [(710,450),(360,600),(900,250)]:
        page.evaluate('([w,h])=>{const m=document.querySelector("main");m.style.width=w+"px";m.style.height=h+"px"}',[width,height])
        page.wait_for_timeout(100)
        result=page.locator('.lex-curve-plot').evaluate('''n=>{
          const p=n.getBoundingClientRect(),g=n.querySelector('.lex-curve-grid-lines').getBoundingClientRect(),m=n.querySelector('svg').getScreenCTM();
          return {margins:[g.left-p.left,p.right-g.right,g.top-p.top,p.bottom-g.bottom],scale:[m.a,m.d]};}''')
        assert max(result['margins'])-min(result['margins'])<1,result
        assert abs(result['scale'][0]-result['scale'][1])<.01,result
    page.evaluate('()=>{const m=document.querySelector("main");m.style.width="710px";m.style.height="450px"}')
    page.locator('.lex-curve-editor').hover()
    page.wait_for_timeout(200)
    drawer=page.locator('.lex-curve-variables')
    assert drawer.evaluate("n=>getComputedStyle(n).boxShadow")!='none'
    assert drawer.evaluate("n=>getComputedStyle(n).backgroundColor")!='rgb(255, 255, 255)'
    page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-graph-spacing.png'))
