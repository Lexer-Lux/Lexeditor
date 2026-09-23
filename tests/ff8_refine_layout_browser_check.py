"""Refine widths follow reordered columns and property controls align."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugin_ui import plugin_ui
def main():
 s=plugin_ui('ff8')
 detail=s[s.index('  function refineDetail'):s.index('  function renderRefine')]
 columns=re.search(r'const columns=(\[.*?\]);',s[s.index('  function renderRefine'):],re.S).group(1)
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':1500,'height':900})
  p.route('http://fixture/',lambda r:r.fulfill(content_type='text/html',body='<body data-lex-plugin="ff8"><div id="list" style="width:700px"></div><div id="detail" style="width:700px"></div></body>'));p.goto('http://fixture/')
  p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  p.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
  p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  p.on('pageerror', lambda error: print(error))
  p.add_script_tag(content="""const {el,detailField,infoHelp,readonlyField,columnList}=LexeditorUI;
 const state={data:{refine:{tables:[{id:'m000',name:'Magic Refine'}]}}},shell={refresh(){}};
 const row={id:0,table:'m000',name:'Recipe',groupName:'T Mag-RF',groupDescription:'Thunder',inputName:'Coral Fragment',outputName:'Thundara',inputQuantity:1,outputQuantity:20,text:'One becomes twenty',unknown:256};
 function sharedDetail(row,prefs,body,cls){return el('div',{class:cls},...body)}
 function numberControl(value,min,max,step,change,attrs){return el("input",{type:"number",value,min,max,step,...attrs})}
 function refineSource(control){return control}function refineChoice(){return 'Choice'}function setRefineEntity(){}
 function refineEntityControl(){return el('span',{class:'ff8-entity-search'},el('span',{},'Choice'),el('button',{},'Pick'))}
 """+detail+'const columns='+columns+""";
 document.querySelector('#list').append(columnList({rows:[row],columns:[columns[1],columns[0],columns[2]],key:r=>r.id}));
 document.querySelector('#detail').append(refineDetail(row,null));""")
  widths=p.locator('.lex-column-list-head-cell').evaluate_all('(es)=>es.map(e=>e.getBoundingClientRect().width)')
  assert widths[0]>100 and widths[1]<80 and widths[2]>widths[0],widths
  assert p.locator('#detail h3').count()==0
  boxes=p.locator('#detail .lex-detail-field-control').evaluate_all('(es)=>es.map(e=>e.getBoundingClientRect().left)')
  assert len(boxes)==5,boxes
  assert p.locator('#detail .lex-recipe-row .lex-detail-field').count()==4
  assert p.locator('#detail .lex-detail-field-label').all_text_contents()==['']*5
  p.locator('textarea').fill('Changed recipe text')
  assert p.evaluate('row.text')=='Changed recipe text'
  p.evaluate("""() => {
    window.renderPins = () => {
      window.prefs = LexeditorUI.columnPreferences('ff8-refine-fixture',columns,window.renderPins);
      document.querySelector('#list').replaceChildren(columnList({rows:[row],columns,columnPreferences:window.prefs,key:r=>r.id}));
      document.querySelector('#detail').replaceChildren(refineDetail(row,window.prefs));
    };
    window.renderPins();
  }""")
  for key in ['inputName','inputQuantity','outputName','outputQuantity','text']:
   pin=p.locator(f'[data-lex-pin-column="{key}"]')
   pin.focus()
   pin.click();p.wait_for_timeout(300)
   assert p.locator(f'.lex-column-list-head-cell[data-column-key="{key}"]').count()==1,key
   assert pin.get_attribute('aria-pressed')=='true'
  p.evaluate('window.renderPins()')
  for key in ['inputName','inputQuantity','outputName','outputQuantity','text']:
   assert p.locator(f'.lex-column-list-head-cell[data-column-key="{key}"]').count()==1,key
   pin=p.locator(f'[data-lex-pin-column="{key}"]');pin.focus();pin.click();p.wait_for_timeout(300)
   assert p.locator(f'.lex-column-list-head-cell[data-column-key="{key}"]').count()==0,key
  b.close()
 print('Refine reordered column widths, one recipe row, recipe text editing, and all five property pins with saved preferences passed.')
if __name__=='__main__':main()


