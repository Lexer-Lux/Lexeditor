"""Shared column minima include titles, sort controls, and help."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
def main():
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page()
  p.route('http://fixture/',lambda r:r.fulfill(content_type='text/html',body='<body data-lex-plugin="ff8"><main style="width:900px"></main></body>'));p.goto('http://fixture/')
  p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  p.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
  p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  for scale in [.96,1,1.5]:
   p.evaluate("""scale=>{
    document.body.style.zoom=scale;
    document.querySelector('main').replaceChildren(LexeditorUI.columnList({rows:[{slot:1,item:'Potion',rare:false}],key:r=>r.slot,class:'ff8-shop-table ff8-record-list',template:'24px minmax(150px,1fr) 30px',sortState:{key:'slot',dir:1},columns:[{key:'slot',label:'Slot'},{key:'item',label:'Item'},{key:'rare',label:'Rare',help:'Familiar unlocks rare stock.'}]}));
   }""",scale)
   p.wait_for_timeout(100)
   result=p.locator('.lex-column-list-head-cell').evaluate_all("""es=>es.map(e=>{const label=e.querySelector('.header-label'),r=document.createRange();r.selectNodeContents(label);return {width:e.clientWidth,lines:r.getClientRects().length,overflow:label.scrollWidth>e.clientWidth}})""")
   assert result[0]['width']>24 and result[2]['width']>30,result
   assert not any(r['overflow'] for r in result),result
   slot=p.locator('.header-label').first
   assert slot.evaluate("e=>e.offsetHeight<30"),result
  b.close()
 print('Shared header fitting passed for narrow Slot and Rare columns at three scales.')
if __name__=='__main__':main()
