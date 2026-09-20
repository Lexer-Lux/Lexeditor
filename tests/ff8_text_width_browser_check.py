"""Text editing must use the detail pane width."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugin_ui import plugin_ui
def main():
 s=plugin_ui('ff8')
 fn=s[s.index('  function textDetail'):s.index('  function renderText')]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page()
  p.route('http://fixture/',lambda r:r.fulfill(content_type='text/html',body='<body data-lex-plugin="ff8"><main></main></body>'));p.goto('http://fixture/')
  p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  p.add_style_tag(content=(ROOT/'games/ff8/editor.css').read_text(encoding='utf-8'))
  p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  p.add_style_tag(content='main{display:block!important;padding:0!important}.lex-detail-panel{width:100%}')
  p.add_script_tag(content="""const {el,detailField,detailSection,infoHelp}=LexeditorUI;
 const state={references:[],vanilla:{}},shell={refresh(){}};
 function matchingTextRow(){return {value:'Drain'}}
 function sourceControl(control,current,vanilla,references,apply,format,options){return LexeditorUI.provenanceControl({control,current,vanilla,references,apply,internal:options.internal})}
 function sharedDetail(row,prefs,body){return el('div',{class:'lex-detail-panel'},body)}
 const row={source:'kernel',name:'Magic text #44 Name',role:'Name',recordId:44,value:'Drain'};
 """+fn+"document.querySelector('main').append(textDetail(row,null));")
  for width in [300,420,700]:
   p.evaluate('w=>document.querySelector("main").style.width=w+"px"',width)
   p.wait_for_timeout(60)
   assert p.locator('textarea').evaluate('(e)=>e.offsetWidth/e.closest(".lex-detail-field").clientWidth>.9'),width
  assert p.locator('.lex-detail-field-label').evaluate('(e)=>e.offsetHeight>=30')
  p.locator('textarea').fill('New text')
  assert p.evaluate('row.value')=='New text'
  b.close()
 print('Text uses over 90% of the property width at three pane widths; editing passed.')
if __name__=='__main__':main()
