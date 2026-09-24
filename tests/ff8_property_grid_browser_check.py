"""Inputs and flags must fit in the shared Start/Field property grid."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugin_ui import plugin_ui
def main():
 s=plugin_ui('ff8')
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':2560,'height':1352})
  p.route('http://fixture/',lambda r:r.fulfill(content_type='text/html',body='<body data-lex-plugin="ff8"><main class="lex-detail-panel"></main></body>'));p.goto('http://fixture/')
  p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  p.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
  p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  p.evaluate("""()=>{const U=LexeditorUI;const grid=U.el('div',{class:'starting-field-grid lex-property-grid'});
   for(let i=0;i<15;i++){const input=i%2?U.el('input',{value:'17336449'}):U.el('select',{},U.el('option',{},'Squall'));
    grid.append(U.detailField({label:i%2?'Unlocked weapon recipes':'Party member 1',control:U.provenanceControl({control:input,current:1,vanilla:0,references:[],apply(){}})}));}
   grid.append(U.detailField({label:'Config flags',control:U.el('div',{class:'flag-list'},...['Battle vibration trigger','Vibration hardware present','Use custom controls','No controller detected','Controls modified'].map(name=>U.el('label',{},U.el('input',{type:'checkbox'}),name)))}));
   document.querySelector('main').append(grid);
  }""")
  for width in [360,700,1100,2500]:
   for scale in [.96,1,1.5]:
    p.evaluate('([w,s])=>{document.querySelector("main").style.width=w+"px";document.body.style.zoom=s}',[width,scale])
    p.wait_for_timeout(60)
    errors=p.evaluate("""()=>[...document.querySelectorAll('input:not([type=checkbox]),select')].filter(e=>e.clientWidth<80).map(e=>e.clientWidth)""")
    assert not errors,(width,scale,errors)
    assert p.locator('.flag-list').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'),(width,scale)
  b.close()
 print('Start/Field property layout: readable inputs and contained flags at four widths and three scales.')
if __name__=='__main__':main()
