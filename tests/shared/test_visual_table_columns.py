"""Record IDs stay compact while visual/descriptive columns use spare width."""
import os
from test_shared_ui_feedback import page, framework, ROOT


def test_world_gradient_fills_its_cell_and_ids_do_not_expand(page):
    framework(page)
    page.add_style_tag(path=str(ROOT/'plugins/ff8/editor.css'))
    source=(ROOT/'plugins/ff8/battle.js').read_text(encoding='utf-8')
    page.add_script_tag(content='const {el}=LexeditorUI;'+source[source.index('  function worldColorHex'):source.index('  function railPointNumber')])
    page.evaluate('''()=>{
      const U=LexeditorUI,main=document.querySelector('main');
      main.style.cssText='width:600px;display:block;';
      for(const sky of [true,false]){
        const columns=[{key:'id',label:sky?'Record':'Entry',numberedId:true},
          sky?{key:'gradient',label:'Sky gradient',cellClass:'lex-cell-fill',render:worldSkySwatch}:
              {key:'field',label:'Field'}];
        const table=U.columnList({rows:[{id:1,field:'Balamb',skyTop:[0,0,100],skyCenter:[0,150,255],skyBottom:[255,240,200]}],
          columns,columnPreferences:U.columnPreferences('visual-'+sky,columns),key:r=>r.id});
        table.style.height='180px';main.append(table);
      }
    }''')
    page.wait_for_timeout(100)
    for cell in page.locator('.lex-column-list-cell[data-column-key="id"]').all():
        assert cell.bounding_box()['width']<150
    swatch=page.locator('.world-sky-swatch')
    assert swatch.evaluate('''e=>{
      const s=e.getBoundingClientRect(),c=e.closest('.lex-column-list-cell').getBoundingClientRect();
      return Math.abs(s.width-c.width)<=2 && Math.abs(s.height-c.height)<=2;
    }'''), swatch.evaluate('e=>[e.getBoundingClientRect().toJSON(),e.parentElement.getBoundingClientRect().toJSON(),e.closest(".lex-column-list-cell").getBoundingClientRect().toJSON()]')
    if os.environ.get('LEX_SKY_SCREENSHOT'):
        page.screenshot(path=os.environ['LEX_SKY_SCREENSHOT'])
