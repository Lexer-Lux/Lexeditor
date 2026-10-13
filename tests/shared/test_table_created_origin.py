"""Record origin is rendered by the shared table, including after sorting."""
from test_shared_ui_feedback import page, framework


def test_created_origin_is_automatic_and_not_duplicated(page):
    framework(page)
    page.evaluate("""()=>{
      const U=LexeditorUI;
      document.querySelector('main').append(U.columnList({
        rows:[{id:1,name:'Vanilla',created:false},{id:2,name:'Added',created:true},
          {id:3,name:'Old renderer',created:true},{id:4,name:'Date field',created:'2026-01-01'}],
        columns:[{key:'id',label:'ID'},{key:'name',label:'Name',render:row=>row.id===3
          ? U.inlineLabel(U.recordSource({created:true}),row.name):row.name}]
      }));
    }""")
    pens = page.get_by_role('img', name='Created in this mod', exact=True)
    assert pens.count() == 2
    for name in ['Added', 'Old renderer']:
        row = page.locator('.lex-column-list-row').filter(has_text=name)
        assert row.get_by_role('img', name='Created in this mod').count() == 1
        assert row.locator('[data-column-key=name]').get_by_role('img').count() == 1
    page.locator('.lex-column-list-head-cell[data-column-key=name]').click()
    assert pens.count() == 2
    assert page.locator('.lex-column-list-row').filter(has_text='Vanilla').get_by_role('img').count() == 0
