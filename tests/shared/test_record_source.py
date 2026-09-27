"""Record origin remains distinct from edits to existing records."""
from test_shared_ui_feedback import page, framework


def test_record_source_keeps_vanilla_plain_and_accepts_plugin_icons(page):
    framework(page)
    page.evaluate('''()=>{
      const U=LexeditorUI;
      document.querySelector('main').append(...[
        ['Vanilla',{vanilla:true,created:true}],
        ['Edited vanilla',{}],
        ['New record',{created:true}],
        ['DLC record',{label:'Expansion pack',icon:U.el('span',{},'◆')}]
      ].map(([name,source])=>U.inlineLabel(U.recordSource(source),name)));
    }''')
    assert page.get_by_role('img',name='Created in this mod',exact=True).count()==1
    assert page.get_by_role('img',name='Expansion pack',exact=True).count()==1
    rows=page.locator('main > .lex-inline-label')
    assert rows.nth(0).inner_text()=='Vanilla'
    assert rows.nth(1).inner_text()=='Edited vanilla'
    assert rows.nth(2).locator('.lex-record-source').inner_text()=='✒️'
    assert rows.nth(3).locator('.lex-record-source').inner_text()=='◆'
