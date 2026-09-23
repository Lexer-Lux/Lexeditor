"""Text editing must use the detail pane width."""
import re
import json
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
from plugin_ui import plugin_ui
from plugins.ff8 import kernel_text
def main():
 s=plugin_ui('ff8')
 fn=s[s.index('  function textTokenToolbar'):s.index('  function renderText')]
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page()
  p.route('http://fixture/',lambda r:r.fulfill(content_type='text/html',body='<body data-lex-plugin="ff8"><main></main></body>'));p.goto('http://fixture/')
  p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  p.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
  p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  p.add_style_tag(content='main{display:block!important;padding:0!important}.lex-detail-panel{width:100%}')
  p.add_script_tag(content="""const {el,detailField,detailSection,infoHelp,detailPanel,readonlyField}=LexeditorUI;
 const state={references:[],vanilla:{},data:{text:{}}},shell={refresh(){}};
 function matchingTextRow(){return {value:'Drain'}}
 function sourceControl(control,current,vanilla,references,apply,format,options){return LexeditorUI.provenanceControl({control,current,vanilla,references,apply,internal:options.internal})}
 function sharedDetail(row,prefs,body){return el('div',{class:'lex-detail-panel'},body)}
 const row={source:'kernel',name:'Magic text #44 Name',role:'Name',recordId:44,value:'Drain'};
 """+"state.data.text.tokens="+json.dumps(kernel_text.editor_tokens())+";"+fn+"document.querySelector('main').append(textDetail(row,null));")
  for width in [300,420,700]:
   p.evaluate('w=>document.querySelector("main").style.width=w+"px"',width)
   p.wait_for_timeout(60)
   assert p.locator('textarea').evaluate('(e)=>e.offsetWidth/e.closest(".lex-detail-field").clientWidth>.9'),width
   assert p.locator('.ff8-text-token-toolbar').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'),width
  # The editor has no name but keeps its help about tokens and save limits.
  assert p.locator('.lex-text-editor .lex-info-help').count()==1
  p.locator('textarea').fill('New text')
  assert p.evaluate('row.value')=='New text'
  p.locator('textarea').evaluate('(e)=>{e.focus();e.setSelectionRange(4,8);e.dispatchEvent(new Event("select"))}')
  p.get_by_role('button',name='Insert Squall',exact=True).click()
  assert p.evaluate('row.value')=='New {Squall}'
  p.locator('textarea').press('Control+z')
  assert p.evaluate('row.value')=='New text', 'toolbar insertion must support undo'
  p.locator('textarea').evaluate('(e)=>{e.setSelectionRange(0,0);e.dispatchEvent(new Event("select"))}')
  p.get_by_role('button',name='Insert Red',exact=True).click()
  p.get_by_role('combobox',name='Insert Variables',exact=True).select_option('{Var0}')
  assert p.evaluate('row.value')=='{Red}{Var0}New text'
  p.get_by_role('combobox',name='Insert Variables',exact=True).select_option('{Var0}')
  assert p.evaluate('row.value')=='{Red}{Var0}{Var0}New text'
  p.locator('textarea').evaluate('(e)=>e.readOnly=true')
  p.get_by_role('button',name='Insert Squall',exact=True).click()
  assert p.evaluate('row.value')=='{Red}{Var0}{Var0}New text'
  p.evaluate('document.querySelector("main").style.width="700px"')
  p.screenshot(path=str(Path(tempfile.gettempdir())/'ff8-text-toolbar.png'))
  b.close()
 print('Text width, toolbar overflow, selection replacement, undo, repeated menu insertion and read-only checks passed.')
if __name__=='__main__':main()
