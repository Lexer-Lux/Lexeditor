"""Composite table editors fill rows and keep checkboxes centred."""
from test_shared_ui_feedback import ROOT, page, framework


def test_table_controls_share_row_height(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    page.evaluate('''()=>{
      const U=LexeditorUI;
      const source=control=>U.provenanceControl({control,current:()=>1,vanilla:1});
      document.querySelector('main').append(U.columnList({fill:true,editable:true,
        template:'70px minmax(0,1fr) minmax(0,1fr)',
        rows:Array.from({length:8},(_,id)=>({id})),key:r=>r.id,columns:[
          {key:'enabled',label:'Enabled',render:()=>source(U.el('input',{type:'checkbox',checked:true}))},
          {key:'enemy',label:'Enemy',render:()=>source(U.choiceField(U.el('span',{},'G-Soldier'),U.el('button',{},U.selectionIcon())))},
          {key:'level',label:'Level',render:()=>source(U.stack({fill:false},U.el('select',{},U.el('option',{},'Fixed level')),U.el('input',{type:'number',value:20})))}
        ]}));
    }''')
    for height in [300,650]:
        page.locator('.lex-column-list').evaluate('(n,h)=>n.style.height=h+"px"',height)
        page.wait_for_timeout(100)
        for row in page.locator('.lex-column-list-row').all():
            metrics=row.evaluate('''row=>{
              const box=n=>n.getBoundingClientRect();
              const cell=key=>row.querySelector(`[data-column-key="${key}"]`);
              const c=box(cell('enabled')), check=box(cell('enabled').querySelector('input'));
              const enemy=box(cell('enemy')), picker=box(row.querySelector('.lex-choice-field'));
              const level=box(cell('level')), select=box(row.querySelector('select')), num=box(row.querySelector('input[type=number]'));
              return {centre:(check.top+check.bottom-c.top-c.bottom)/2,
                pickerGap:enemy.height-picker.height, levelGap:level.height-select.height-num.height,
                halves:select.height-num.height,join:select.bottom-num.top};
            }''')
            assert all(abs(v)<3 for v in metrics.values()),metrics
