"""Hidden graph controls must not create scroll range or consume page turns."""
from test_shared_ui_feedback import page, framework


def test_graph_drawer_and_wheel(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      window.turns=0;
      const graph=U.curveEditor({title:'HP',domain:{min:1,max:100},range:{min:0,max:100},evaluate:x=>x,
        variables:['A','B','C','D'].map(label=>({label,control:U.el('input',{type:'number',value:2})}))});
      const panel=U.tabbedPanel({tabs:[{id:'stats',label:'Stats'}],active:'stats',
        content:U.pagedPane(graph,U.pager({page:0,pages:3,pageSize:1,total:3,change:()=>turns++}))});
      panel.style.height='500px';panel.style.width='500px';
      document.querySelector('main').replaceChildren(panel);
    }''')
    page.mouse.move(1100,750)
    page.wait_for_timeout(250)
    assert page.locator('.lex-paged-pane-content').evaluate('n=>n.scrollHeight<=n.clientHeight+1')
    assert page.locator('.lex-tabbed-panel-content').evaluate('n=>n.scrollHeight<=n.clientHeight+1')
    page.locator('.lex-curve-plot').hover()
    page.mouse.wheel(0,100)
    page.wait_for_timeout(200)
    assert page.evaluate('turns')==1
    page.mouse.move(1100,750)
    page.wait_for_timeout(250)
    assert page.locator('.lex-paged-pane-content').evaluate('n=>n.scrollHeight<=n.clientHeight+1')
