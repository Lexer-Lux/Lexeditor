"""A related selector shares the flag grid without reserving another column."""
from test_shared_ui_feedback import page, framework, ROOT


def test_selector_and_flags_share_grid(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{
      window.flag=false;
      document.querySelector('main').append(LexeditorUI.toggleRow({
        leading:[{label:'TYPE',control:LexeditorUI.el('select',{},LexeditorUI.el('option',{},'Magical (Shell halves)'))}],
        toggles:['Unused (0x04) – no reader','Break Damage Limit','Reflectable','Ignore defence'].map(label=>({label,help:'Help for '+label,change:value=>flag=value}))
      }));
    }''')
    for width in [400,650,1000]:
        page.evaluate('w=>document.querySelector("main").style.width=w+"px"',width)
        boxes=page.locator('.lex-toggle-row > *').evaluate_all('es=>es.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width}})')
        assert abs(boxes[0]['width']-boxes[1]['width'])<1
        assert boxes[0]['x']<boxes[1]['x'] or boxes[0]['y']<boxes[1]['y']
        assert page.locator('.lex-toggle-name').evaluate_all('es=>es.every(e=>{const r=e.getBoundingClientRect(),p=e.closest(".lex-toggle").getBoundingClientRect();return r.right<=p.right+1&&r.bottom<=p.bottom+1&&e.scrollWidth<=e.clientWidth+1})')
    page.get_by_role('checkbox',name='Reflectable',exact=True).check()
    assert page.evaluate('flag') is True
    assert page.locator('.lex-toggle-rail .lex-info-help').count()==0
    assert page.locator('.lex-toggle-name .lex-info-help').count()==4
    assert all(page.locator('.lex-toggle-name .lex-info-help').nth(i).is_visible() for i in range(4))
