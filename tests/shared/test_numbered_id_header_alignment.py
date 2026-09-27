"""A numbered-id column's header starts where its ids start, and no id is cut.

Lexer, 2026-09-27: "the Slot column header is horizontally misaligned.
again." The header was centred over start-aligned ids, and a first sortable
column keeps room for the sort mark, which its cells did not.
"""
from test_shared_ui_feedback import ROOT, page, framework


def test_id_header_and_ids_share_a_start(page):
    page.add_style_tag(content=(ROOT / 'plugins/ff8/editor.css').read_text(encoding='utf-8').replace('url(', 'url(x'))
    framework(page)
    page.evaluate("document.body.dataset.lexPlugin='ff8'")
    page.evaluate('''()=>{
      const rows=[13,7,14,22].map(id=>({id,name:'Ability '+id}));
      const main=document.querySelector('main');main.style.cssText='width:600px';
      main.replaceChildren(LexeditorUI.columnList({rows,key:r=>r.id,
        template:'52px minmax(120px,1fr)',
        columns:[{key:'id',label:'Slot',sortable:true,numberedId:true},{key:'name',label:'Ability',sortable:true}]}));
    }''')
    page.wait_for_timeout(200)
    result = page.evaluate('''()=>{
      const start=node=>{const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);
        for(let t;(t=walker.nextNode());)if(t.data.trim()){const r=document.createRange();r.selectNodeContents(t);return r.getBoundingClientRect().left}};
      const head=document.querySelector('.lex-column-list-head-cell');
      const cells=[...document.querySelectorAll('.lex-column-list-row > .lex-column-list-cell:first-child')];
      return {head:start(head),ids:cells.map(c=>c.querySelector('.lex-record-id').getBoundingClientRect().left),
        cut:cells.filter(c=>{const k=c.querySelector('.lex-column-cell-content');return k.scrollWidth>k.clientWidth+1}).length}
    }''')
    assert all(abs(result['head'] - left) <= 2 for left in result['ids']), result
    assert result['cut'] == 0, result
