"""Headless Players layout and shared-state editing checks."""
import sys,re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]

def main():
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':900})
  page.route('**/*',lambda route:route.abort())
  page.route('http://fixture/',lambda route:route.fulfill(body='<html></html>',content_type='text/html'))
  page.goto('http://fixture/')
  page.set_content('<main id="main" style="height:800px"></main>')
  page.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  css=re.search(r'<style>(.*?)</style>',(ROOT/'games/ff8/editor.html').read_text(encoding='utf-8'),re.S).group(1)
  page.add_style_tag(content=css)
  page.add_style_tag(content=':root{--lex-text:#fff;--lex-panel:#626262;--lex-panel-2:#4f4f4f;--lex-border:#929292;--lex-highlight:#fff;--lex-accent:#aa2432;--lex-panel-gap:8px}')
  page.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  source=(ROOT/'games/ff8/cards_ui.js').read_text(encoding='utf-8').replace('    render,\n    edits:', '    render, renderPlayers:()=>{mode="players";return render()},\n    edits:',1)
  page.add_script_tag(content=source)
  page.evaluate('''()=>{
   const U=LexeditorUI;window.model={tab:'cards',activeSource:'mine',data:{fields:{rows:[{key:'test',name:'Test area',_loaded:true,players:[]},{key:'garden',name:'Garden',_loaded:true,players:[{id:0,entity:'Student',params:[{id:0,name:'Deck level',mode:'literal',editable:true,value:3}]}]}]}},vanilla:{fields:{rows:[]}}};
   window.calls=[];const ui=FF8CardsUI({el:U.el,subtabBar:U.subtabBar,state:model,columnList:U.columnList,detailPanel:U.detailPanel,detailSection:U.detailSection,detailField:U.detailField,infoHelp:U.infoHelp,sourceControl:control=>control,numberControl:(value,min,max,step,change,attrs)=>U.el('input',{type:'number',value,min,max,step,...attrs,oninput:e=>change(e.target.value)}),noteFieldEdit:(...args)=>calls.push(args),shell:{refresh:()=>{}},ensureFieldDetail:async()=>{}});
   document.querySelector('main').replaceChildren(ui.renderPlayers());}''')
  assert page.locator('select').count()==0
  assert page.get_by_role('button',name='SAVE PLAYERS').count()==0
  assert page.get_by_role('table').count()==1
  assert page.get_by_label('Search card-player areas',exact=True).count()==1
  assert page.get_by_text('There are no Triple Triad players in this area.').is_visible()
  page.get_by_text('Garden',exact=True).click()
  control=page.locator('.ff8-card-player-detail input')
  control.fill('5')
  assert page.evaluate('model.data.fields.rows[1].players[0].params[0].value')==5
  assert page.evaluate('calls[0][0]')=='fields'
  styles=control.evaluate('e=>{const s=getComputedStyle(e);return [s.color,s.backgroundColor]}')
  assert styles[0]!='rgb(0, 0, 0)' and styles[1]!='rgb(255, 255, 255)',styles
  import tempfile
  page.wait_for_timeout(200)
  page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-ff8-players.png'))
  browser.close()
  print('Players: shared list/detail, empty state, themed controls and field-state edits passed.')
if __name__=='__main__':main()
