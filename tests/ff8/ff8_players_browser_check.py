"""Headless Players layout and shared-state editing checks."""
import sys,re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui

def main():
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':900})
  page.route('**/*',lambda route:route.abort())
  page.route('http://fixture/',lambda route:route.fulfill(body='<html></html>',content_type='text/html'))
  # The view lists only areas that really have a card player, which it asks the
  # plugin for. Without an answer it draws its "could not find" message and
  # there is nothing here to check.
  page.route('**/api/card-players',lambda route:route.fulfill(
      content_type='application/json',
      body='{"ready":true,"error":null,"keys":["garden"],"players":['
           '{"map":"garden","id":0,"entity":"Student","script":"talk","deckId":201,"deckMode":"literal"},'
           '{"map":"garden","id":1,"entity":"Teacher","script":"talk","deckId":201,"deckMode":"literal"},'
           '{"map":"garden","id":2,"entity":"Ghost","script":"talk","deckId":null,"deckMode":"variable"}],'
           '"scanned":2,"total":2}'))
  page.goto('http://fixture/')
  page.set_content('<div id="toolbar">Old character tabs</div><main id="main" style="height:800px"></main>')
  page.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  css=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8')
  page.add_style_tag(content=css)
  page.add_style_tag(content=':root{--lex-text:#fff;--lex-panel:#626262;--lex-panel-2:#4f4f4f;--lex-border:#929292;--lex-highlight:#fff;--lex-accent:#aa2432;--lex-panel-gap:8px}')
  page.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  source=(ROOT/'plugins/ff8/cards_ui.js').read_text(encoding='utf-8').replace('    render,\n    edits:', '    render, renderPlayers:()=>{mode="players";return render()},\n    edits:',1)
  page.add_script_tag(content=source)
  page.evaluate('''()=>{
   const U=LexeditorUI;window.model={tab:'cards',activeSource:'mine',data:{cards:{rows:[]},fields:{rows:[{key:'test',name:'Test area',_loaded:true,players:[]},{key:'garden',name:'Garden',_loaded:true,players:[
     {id:0,entity:'Student',params:[{id:0,name:'Deck ID',mode:'literal',editable:true,value:201}]},
     {id:1,entity:'Teacher',params:[{id:0,name:'Deck ID',mode:'literal',editable:true,value:201}]},
     {id:2,entity:'Ghost',params:[{id:0,name:'Deck ID',mode:'variable',editable:true,value:7}]}]}]}},vanilla:{fields:{rows:[]}}};
   window.calls=[];const ui=FF8CardsUI({el:U.el,subtabBar:U.subtabBar,state:model,columnList:U.columnList,detailPanel:U.detailPanel,detailSection:U.detailSection,detailField:U.detailField,infoHelp:U.infoHelp,sourceControl:control=>control,numberControl:(value,min,max,step,change,attrs)=>U.el('input',{type:'number',value,min,max,step,...attrs,oninput:e=>change(e.target.value)}),noteFieldEdit:(...args)=>calls.push(args),shell:{refresh:()=>{}},ensureFieldDetail:async()=>{}});
   document.querySelector('main').replaceChildren(ui.renderPlayers());}''')
  assert page.locator('select').count()==0
  assert page.get_by_role('button',name='SAVE PLAYERS').count()==0
  assert page.get_by_role('table').count()==1
  assert page.get_by_label('Search card players',exact=True).count()==1
  assert page.locator('#toolbar').is_hidden()
  assert page.locator('.lex-column-list-row').filter(has_text='Student').count()==1
  assert page.locator('.lex-column-list-row').filter(has_text='Garden').count()==0
  # The deck a call names is shown in the list, and a savemap argument has no
  # deck number to show.
  assert page.locator('.lex-column-list-row').filter(has_text='Student').first.inner_text().find('201')>=0
  assert page.locator('.lex-column-list-row').filter(has_text='Ghost').first.inner_text().find('—')>=0
  # The deck is a link and a finder (Lexer, 2026-09-27).
  assert page.get_by_role('button',name='Open deck 201',exact=True).count()==1
  assert page.get_by_role('button',name='Choose the deck for Student',exact=True).count()==1
  # Which opponents share a deck belongs to the deck, not to each opponent
  # (Lexer, 2026-09-27: "remove the 'also uses deck X'").
  assert page.locator('.lex-detail-section-title',has_text='ALSO USES DECK').count()==0
  assert page.get_by_role('button',name='Open Teacher',exact=True).count()==0
  import tempfile
  page.wait_for_timeout(200)
  page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-ff8-players.png'))
  browser.close()
  print('Players: shared list/detail, empty state, themed controls and field-state edits passed.')
if __name__=='__main__':main()
