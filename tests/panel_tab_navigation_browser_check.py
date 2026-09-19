"""Panel tab placement, keyboard target, redraw, and saved preference."""
import sys,tempfile,re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from settings_manager import SettingsStore

def main():
 with tempfile.TemporaryDirectory() as tmp:
  store=SettingsStore(Path(tmp)/'settings.json')
  assert store.snapshot()['panelTabTarget']=='hover'
  store.save('daily',panel_tab_target='focus')
  assert SettingsStore(Path(tmp)/'settings.json').snapshot()['panelTabTarget']=='focus'
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page()
  p.route('http://fixture/',lambda r:r.fulfill(content_type='text/html',body='<body><main style="display:flex;gap:20px"><div id="a"></div><div id="b"></div></main></body>'));p.goto('http://fixture/')
  p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  p.add_style_tag(content='#a .lex-tabbed-panel,#b .lex-tabbed-panel{height:300px;width:300px}.lex-tabbed-panel-content{overflow:auto}')
  p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  p.evaluate("""()=>{const U=LexeditorUI;window.active={a:'one',b:'one'};window.draw=id=>document.getElementById(id).replaceChildren(U.tabbedPanel({label:id,active:active[id],tabs:[{id:'one',label:'One'},{id:'two',label:'Two'}],change:value=>{active[id]=value;draw(id)},content:U.el('input',{'aria-label':id+' input'})}));draw('a');draw('b')}""")
  p.wait_for_timeout(100)
  assert p.locator('#a .lex-subtab-bar').bounding_box()['y']>p.locator('#a .lex-tabbed-panel-content').bounding_box()['y']
  p.evaluate("""()=>{const U=LexeditorUI;
   const page=U.el('div',{id:'page-tabs',style:'display:flex;flex-direction:column;height:200px'},
    U.subtabBar({label:'Abilities tables',active:'general',tabs:[{id:'general',label:'General'},{id:'map',label:'Map'}]}),
    U.el('div',{id:'page-content'},'List and detail panels'));
   document.body.append(page);
  }""")
  p.wait_for_timeout(50)
  assert not p.locator('#page-tabs').evaluate("e=>e.classList.contains('lex-bottom-tab-panel')")
  assert p.locator('#page-tabs .lex-subtab-bar').bounding_box()['y']<p.locator('#page-content').bounding_box()['y']
  p.locator('#page-tabs').evaluate('e=>e.remove()')
  p.locator('#b input').focus();p.locator('#a .lex-tabbed-panel-content').hover()
  p.keyboard.press('Tab');assert p.evaluate('active.a')=='two';assert p.evaluate('active.b')=='one'
  p.keyboard.press('Tab');assert p.evaluate('active.a')=='one'
  p.keyboard.press('Shift+Tab');assert p.evaluate('active.a')=='two'
  p.evaluate("window.dispatchEvent(new CustomEvent('lexeditor-settings-ready',{detail:{panelTabTarget:'focus'}}))")
  p.locator('#b input').focus();p.keyboard.press('Tab');p.wait_for_timeout(50);assert p.evaluate('active.b')=='two'
  p.keyboard.press('Shift+Tab');p.wait_for_timeout(50);assert p.evaluate('active.b')=='one'
  p.evaluate("document.body.insertAdjacentHTML('beforeend','<div role=dialog><input id=d1><input id=d2></div>')")
  p.locator('#d1').focus();p.keyboard.press('Tab');assert p.locator('#d2').evaluate('(e)=>e===document.activeElement')
  ff8=(ROOT/'games/ff8/editor.html').read_text(encoding='utf-8')
  p.add_style_tag(content=re.search(r'<style>(.*?)</style>',ff8,re.S).group(1))
  p.add_style_tag(content='#magic{width:700px;height:650px}.magic-detail{height:100%}')
  fn=ff8[ff8.index('  function magicDetail('):ff8.index('  function abilityIcon(')]
  p.add_script_tag(content="""const {el,detailField,detailSection,tabbedPanel,multiNumberRow,infoHelp}=LexeditorUI;
   const state={};const row={id:11,name:'Aero',fields:[]};
   function fieldSourceControl(){return el('input',{type:'number',value:0})}
   function magicComposite(){return el('div',{},'Composite values')}
   function magicLabel(){return 'Aero'}
   function sharedDetail(row,prefs,body,cls){return LexeditorUI.detailPanel({title:'Aero',className:cls,body})}
   function renderKernel(){document.querySelector('#magic').replaceChildren(magicDetail(row,null))}
   document.body.insertAdjacentHTML('beforeend','<div id=magic></div>');
  """+fn+"renderKernel();")
  p.wait_for_timeout(100)
  assert p.locator('#magic .lex-detail-field-label').filter(has_text='TARGET INFO').count()==1
  p.locator('#magic [role=tab]').filter(has_text='Junction').click()
  assert p.locator('#magic .lex-detail-field-label').filter(has_text='TARGET INFO').count()==0
  assert p.locator('#magic .lex-detail-field-label').filter(has_text='JUNCTION (STATS)').count()==1
  assert p.locator('#magic .lex-subtab-bar').bounding_box()['width']>650
  assert abs(p.locator('#magic .lex-subtab-bar').bounding_box()['y']+p.locator('#magic .lex-subtab-bar').bounding_box()['height']-(p.locator('#magic').bounding_box()['y']+650))<8
  p.locator('#magic').screenshot(path='C:/Users/Lexer/AppData/Local/Temp/lexeditor-magic-tabs.png')
  b.close()
 print('Bottom panel tabs, hovered/focused routing, forward/reverse wrap, redraw focus, dialog navigation and setting persistence passed.')
if __name__=='__main__':main()
