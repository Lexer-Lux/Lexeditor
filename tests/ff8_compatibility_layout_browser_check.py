"""Compatibility portrait sizing is shared between Magic and GFs."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugin_ui import plugin_ui
def main():
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page()
  p.route('http://fixture/',lambda r:r.fulfill(body='<div id="fixture"></div>',content_type='text/html'));p.goto('http://fixture/')
  p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  p.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
  p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  source=plugin_ui('ff8')
  label=source[source.index('  function gfEntityLabel('):source.index('  function gfFieldRow(')]
  panel=source[source.index('  function compatibilityPanel('):source.index('  const GF_CURVE_FIELDS')]
  p.add_script_tag(content="""
    const {el,hoverable,columnList}=LexeditorUI;
    const state={gfSorts:{compatibility:['label',1]}};
    function gfByName(name){return {id:0}}
    function openGFByName(){}
    function gfCompatibilityLabel(field){return gfEntityLabel(field)}
    function gfCompatibilityFormat(value){return String(value)}
    function fieldSourceControl(){return el('input',{value:'0'})}
  """+label+panel)
  p.route('**/assets/portraits/gfs/*.png',lambda r:r.fulfill(content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="40" height="60"><rect width="40" height="60" fill="silver"/></svg>'))
  p.evaluate("""()=>{for(const view of ['gfs','magic']){
    const host=LexeditorUI.el('div',{style:'display:flex;height:800px;width:300px'});
    host.append(compatibilityPanel(Array.from({length:16},(_,id)=>({field:String(id),label:'Alexander',value:0})),view,0));
    document.querySelector('#fixture').append(host);
  }}""")
  for height in [600,800,1000]:
   p.evaluate('h=>document.querySelectorAll("#fixture>div").forEach(e=>e.style.height=h+"px")',height)
   sizes=p.locator('.lex-inline-label > img').evaluate_all('''es=>es.map(e=>{
     const r=e.getBoundingClientRect(),cell=e.closest('.lex-column-list-cell');
     const c=cell.getBoundingClientRect(),s=getComputedStyle(cell);
     // The room a portrait has is the cell's content box: its own height less
     // the padding it keeps and the rule under the row.
     const available=c.height-parseFloat(s.paddingTop)-parseFloat(s.paddingBottom)
       -parseFloat(s.borderTopWidth)-parseFloat(s.borderBottomWidth);
     return {h:r.height,available,top:r.top-c.top,bottom:c.bottom-r.bottom}})''')
   assert len(sizes)==32
   assert all(abs(s['available']-s['h'])<.6 for s in sizes),sizes
   assert all(s['h']>20 and s['top']>=3 and s['bottom']>=3 for s in sizes),sizes
  b.close()
 print('Magic/GF portraits use identical available row height with margins at three panel heights.')
if __name__=='__main__':main()
