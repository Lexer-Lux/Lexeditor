"""Refine widths follow reordered columns and property controls align."""
import re,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
def main():
 s=plugin_ui('ff8')
 detail=s[s.index('  function refineDetail'):s.index('  function renderRefine')]
 text_helpers=s[s.index('  function refineTextRecord'):s.index('  function textTokenToolbar')]
 text_detail=s[s.index('  function textDetail'):s.index('  function renderTextRecords')]
 columns=re.search(r'const columns=(\[.*?\]);',s[s.index('  function renderRefine'):],re.S).group(1)
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':1500,'height':900})
  p.route('http://fixture/',lambda r:r.fulfill(content_type='text/html',body='<body data-lex-plugin="ff8"><div id="list" style="width:700px"></div><div id="detail" style="width:700px"></div></body>'));p.goto('http://fixture/')
  p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  p.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
  p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  p.on('pageerror', lambda error: print(error))
  p.add_script_tag(content="""const {el,detailField,infoHelp,readonlyField,columnList,detailPanel,hoverable}=LexeditorUI;
 const state={data:{text:{rows:[]},refine:{tables:[{id:'m000',name:'Magic Refine'}]}},vanilla:{},references:[],referenceData:{},selected:{},filters:{text:'stale filter'},pages:{text:4}},shell={refresh(){}};
 const row={id:0,table:'m000',name:'Recipe',groupName:'T Mag-RF',groupDescription:'Thunder',inputName:'Coral Fragment',outputName:'Thundara',inputQuantity:1,outputQuantity:20,text:'One becomes twenty',unknown:256};
 state.data.refine.rows=[row];state.vanilla=JSON.parse(JSON.stringify(state.data));
 function navigate(tab){state.tab=tab}
 function sourceControl(control){return control}function textTokenToolbar(){return null}
 function sharedDetail(row,prefs,body,cls){return LexeditorUI.detailPanel({title:row.name,identity:row.id,className:cls,body})}
 function numberControl(value,min,max,step,change,attrs){return el("input",{type:"number",value,min,max,step,...attrs})}
 function refineSource(control){return control}function refineChoice(){return 'Choice'}function setRefineEntity(){}
 function refineEntityControl(){return el('span',{class:'ff8-entity-search'},el('span',{},'Choice'),el('button',{},'Pick'))}
 """+text_helpers+text_detail+detail+'const columns='+columns+""";
 document.querySelector('#list').append(columnList({rows:[row],columns:[columns[1],columns[0],columns[2]],key:r=>r.id}));
 document.querySelector('#detail').append(refineDetail(row,null));""")
  widths=p.locator('.lex-column-list-head-cell').evaluate_all('(es)=>es.map(e=>e.getBoundingClientRect().width)')
  assert widths[0]>100 and widths[1]<80 and widths[2]>widths[0],widths
  assert p.locator('#detail h3').count()==0
  boxes=p.locator('#detail .lex-detail-field-control').evaluate_all('(es)=>es.map(e=>e.getBoundingClientRect().left)')
  assert len(boxes)==5,boxes
  assert p.locator('#detail .lex-recipe-row .lex-detail-field').count()==4
  labels=p.locator('#detail .lex-detail-field-label').all_text_contents()
  assert labels[:4]==['']*4 and 'Recipe text' in labels[-1],labels
  p.locator('textarea').fill('Changed recipe text')
  assert p.evaluate('row.text')=='Changed recipe text'
  # The source link opens the exact recipe in Text, clearing any stale filter.
  link=p.locator('#detail .lex-hoverable').filter(has_text='Recipe text')
  link.hover();p.mouse.down();p.wait_for_timeout(900);p.mouse.up()
  assert p.evaluate('[state.tab,state.textTab,state.selected.text,state.filters.text]')==['text','text','refine:m000:0','']
  p.evaluate("document.querySelector('#detail').replaceChildren(textDetail(textRecordRows().find(r=>r.id===state.selected.text),null))")
  p.locator('#detail textarea').fill('Edited from Text')
  assert p.evaluate('row.text')=='Edited from Text'
  assert p.evaluate('state.data.text.rows.length')==0,'virtual recipe rows leaked into separate text save payload'
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
   if key=='text':
    p.wait_for_timeout(100)
    p.screenshot(path=str(Path(tempfile.gettempdir())/'ff8-refine-text-pin.png'))
    bounds=pin.evaluate('''pin=>{const b=pin.getBoundingClientRect(),clipped=[];
      for(let p=pin.parentElement;p;p=p.parentElement){const s=getComputedStyle(p),r=p.getBoundingClientRect();
        if(/hidden|clip|auto|scroll/.test(s.overflowX)&&(b.left<r.left-1||b.right>r.right+1))clipped.push(p.className);
        if(/hidden|clip|auto|scroll/.test(s.overflowY)&&(b.top<r.top-1||b.bottom>r.bottom+1))clipped.push(p.className);}
      return clipped}''')
    assert not bounds,bounds
    corner=pin.evaluate('''pin=>{const b=pin.getBoundingClientRect(),r=pin.closest('.lex-detail-field').querySelector('textarea').getBoundingClientRect();
      return Math.abs(b.bottom-r.top)<18&&Math.abs(b.right-r.right)<18}''')
    assert corner,'recipe pin is not anchored to its text box'
   pin.click();p.wait_for_timeout(300)
   assert p.locator(f'.lex-column-list-head-cell[data-column-key="{key}"]').count()==1,key
   assert pin.get_attribute('aria-pressed')=='true'
  p.evaluate('window.renderPins()')
  assert p.locator('#detail textarea').input_value()=='Edited from Text'
  for key in ['inputName','inputQuantity','outputName','outputQuantity','text']:
   assert p.locator(f'.lex-column-list-head-cell[data-column-key="{key}"]').count()==1,key
   pin=p.locator(f'[data-lex-pin-column="{key}"]');pin.focus();pin.click();p.wait_for_timeout(300)
   assert p.locator(f'.lex-column-list-head-cell[data-column-key="{key}"]').count()==0,key
  p.screenshot(path=str(Path(tempfile.gettempdir())/'ff8-refine-linked-text.png'))
  b.close()
 print('Refine reordered column widths, one recipe row, recipe text editing, and all five property pins with saved preferences passed.')
if __name__=='__main__':main()


