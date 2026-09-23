"""Exercise the card preview control without changing a saved mod."""
from pathlib import Path
import sys,tempfile
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from plugins.ff8.cards import ELEMENTS
from plugins.ff8.card_art import png_bytes, element_png_bytes

def main():
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':900,'height':650})
  page.route('**/*',lambda route:route.abort())
  art=png_bytes(9)
  page.route('**/assets/cards/9.png',lambda route:route.fulfill(body=art,content_type='image/png'))
  page.route('**/assets/card-elements/*.png',lambda route:route.fulfill(body=element_png_bytes(int(Path(route.request.url).stem)),content_type='image/png'))
  page.goto('about:blank')
  page.set_content('<base href="http://fixture/"><style>:root{--lex-text:#fff;--lex-panel:#626262;--lex-border:#929292;--lex-accent:#aa2432}body{background:#626262;padding:30px}</style><main id="main"></main>')
  page.add_style_tag(path=str(ROOT/'ui/framework.css'))
  page.add_style_tag(content=':root{--lex-card-image-crop:3%;--lex-card-bg:#22357e}')
  page.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  source=(ROOT/'plugins/ff8/cards_ui.js').read_text(encoding='utf-8').replace('    render,\n    edits:', '    render, preview,\n    edits:',1)
  page.add_script_tag(content=source)
  page.evaluate('''elements=>{const el=LexeditorUI.el;window.row={id:9,top:4,left:3,right:2,bottom:4,element:0,power:22};window.edits=[];
   const ui=FF8CardsUI({el,state:{activeSource:'mine',data:{cards:{elements}}},noteFieldEdit:(...args)=>edits.push(args),conceptIcon:(kind,name)=>name==='None'?null:el('img',{src:'/assets/icons/'+({Fire:288,Ice:289,Thunder:290,Earth:291,Poison:292,Wind:293,Water:294,Holy:295}[name])+'.png',alt:'',title:name+' game icon'})});
   const render=()=>document.querySelector('main').replaceChildren(ui.preview(row,render));render();}''',[{'id':key,'name':name} for key,name in ELEMENTS.items()])
  button=page.get_by_role('button',name='Add element',exact=True)
  page.mouse.move(800,600)
  assert button.evaluate('n=>getComputedStyle(n).opacity')=='0'
  button.hover();assert button.inner_text()=='+'
  assert button.evaluate('n=>getComputedStyle(n).opacity')=='1'
  button.click();assert page.locator('.lex-choice-popover').evaluate('e=>e.matches(":popover-open")')
  assert page.locator('.lex-choice-popover button img').count()==8
  bounds=page.evaluate('''()=>{const a=document.querySelector('.lex-stat-card').getBoundingClientRect(),b=document.querySelector('.lex-choice-popover').getBoundingClientRect();return {inside:b.left>=a.left&&b.right<=a.right&&b.top>=a.top&&b.bottom<=a.bottom}}''')
  assert bounds['inside'],bounds
  page.mouse.move(800,600);page.wait_for_timeout(100)
  assert page.locator('.lex-choice-popover').count()==0
  button.click()
  page.wait_for_function('Array.from(document.querySelectorAll(".lex-choice-popover img")).every(e=>e.complete&&e.naturalWidth>0)')
  page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-card-elements.png'))
  page.get_by_role('button',name='Holy',exact=True).click()
  assert page.evaluate('row.element')==128
  assert page.locator('.lex-stat-card-corner img').get_attribute('alt')=='Holy'
  assert page.locator('.lex-stat-card-corner').inner_text()==''
  page.get_by_role('button',name='Change Holy',exact=True).click();page.get_by_role('button',name='None',exact=True).click()
  assert page.evaluate('row.element')==0
  page.mouse.move(800,600)
  page.get_by_role('button',name='Top, currently 4',exact=True).click()
  assert page.evaluate('row.top')==5
  page.get_by_role('button',name='Top, currently 5',exact=True).click(button='right')
  assert page.evaluate('row.top')==4
  assert page.evaluate("""()=>{const a=document.querySelector('.lex-stat-card').getBoundingClientRect(),b=document.querySelector('.lex-stat-card > img').getBoundingClientRect();return b.left<=a.left&&b.top<=a.top&&b.right>=a.right&&b.bottom>=a.bottom}""")
  page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-card-preview.png'))

  browser.close()
  print('Card artwork bounds, native element icons, rank edits, Holy=128, and removal passed.')
if __name__=='__main__':main()
