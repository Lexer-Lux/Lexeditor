"""FF8 graph regressions using the plugin's full stylesheet."""
import re,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
FRAMEWORK_CSS=(ROOT/'ui/framework.css').read_text(encoding='utf-8')
FRAMEWORK_JS=(ROOT/'ui/framework.js').read_text(encoding='utf-8')
def main():
 css=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8')
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':2048,'height':1100})
  page.route('http://fixture/**',lambda route:route.fulfill(body='<html></html>',content_type='text/html'))
  page.goto('http://fixture/')
  page.set_content('<base href="http://127.0.0.1:9/"><link id="lex-ff8-graph-design-a-style"><style>'+FRAMEWORK_CSS+css+'</style><style>:root{--lex-border:#929292;--lex-text:#fff;--lex-panel:#626262;--ff8-menu-surface:#626262}body{padding:12px}#mount{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;height:1000px}</style><main id="mount"></main>')
  page.add_script_tag(content=FRAMEWORK_JS)
  page.evaluate("""()=>{for(const [i,title] of ['HP','STR','VIT','MAG','SPR','SPD','LUCK','XP'].entries()){
   const formula=i===7?'XP(L) = 10 * (L - 1) * A + floor((L - 1)^2 * B / 256)':i===0?'HP(L)=L*A-trunc(10*L*L/B)+C':'STR(L)=trunc((trunc(L*A/10)+trunc(L/B)-trunc(L*L/(2*D))+C)/4)';
   const variables=[...'ABCD'].map(label=>({label,control:LexeditorUI.el('input',{type:'number',value:20,min:0,max:255})}));
   document.querySelector('#mount').append(LexeditorUI.curveEditor({title,className:'ff8-character-curve',variables,overlayExtrema:true,domain:{min:1,max:100},range:{min:0,max:i===7?100000:255},evaluate:x=>i===7?1000*(x-1):i===0?x*2:0,formula:LexeditorUI.mathFormula(formula)}));}}""")
  page.wait_for_timeout(400)
  cards=page.locator('.ff8-character-curve')
  for i in range(8):
   card=cards.nth(i)
   metrics=card.evaluate("""e=>{const h=e.querySelector('.lex-curve-heading'),s=getComputedStyle(h);return {border:getComputedStyle(e).borderTopWidth,clip:s.clipPath,width:h.getBoundingClientRect().width,colors:[...e.querySelectorAll('.lex-curve-plot > .lex-math-formula [class*=lex-curve-variable-]')].map(n=>getComputedStyle(n).color)}}""")
   assert metrics['clip']!='none',metrics  # The title is inside the plot.
   assert len(set(metrics['colors']))>=2,metrics
   card.hover();page.wait_for_timeout(220)
   aligned=card.evaluate("""e=>{const a=e.getBoundingClientRect(),b=e.querySelector('.lex-curve-variables').getBoundingClientRect();return b.left>=a.left&&b.right<=a.right}""")
   assert aligned,i
   # The equation is drawn term by term, and each term is turned to the slope
   # under it, so the terms are what the two end numbers have to stay clear of.
   # The element that holds them is now a box spanning the plot, and measuring
   # against it would pass whatever the terms did.
   clear=card.evaluate("""e=>{const terms=[...e.querySelectorAll('.lex-curve-plot > .lex-math-formula .lex-curve-math-atom')];return terms.length>0&&[...e.querySelectorAll('.lex-curve-range-value')].every(n=>{const b=n.getBoundingClientRect();return terms.every(t=>{const c=t.getBoundingClientRect();return c.right<=b.left-7||c.left>=b.right+7||c.bottom<=b.top-5||c.top>=b.bottom+5})})}""")
   assert clear,i
  # A narrow card must wrap its variables instead of squeezing them: four
  # variables in a ~300px drawer used to render ~50px inputs while two-variable
  # cards rendered ~120px ones, and the drawer covered the BARS toggle parked
  # at the plot's bottom-right. The toggle now rides in the drawer itself.
  page.evaluate("""()=>{const mount=document.createElement('div');
    mount.id='narrow-mount';mount.style.cssText='width:320px;height:520px;margin-top:12px';
    document.body.append(mount);
    const variables=['A','B','C','D'].map(label=>({label,control:LexeditorUI.el('input',{type:'number',value:20,min:0,max:255})}));
    mount.append(LexeditorUI.curveEditor({title:'NARROW',variables,domain:{min:1,max:100},range:{min:0,max:255},evaluate:x=>x,formula:LexeditorUI.mathFormula('N = A')}));}""")
  narrow=page.locator('#narrow-mount .lex-curve-editor')
  widths=narrow.evaluate("""e=>[...e.querySelectorAll('.lex-curve-variable input')].map(n=>Math.round(n.getBoundingClientRect().width))""")
  assert len(widths)==4 and min(widths)>=70,widths
  narrow.hover();page.wait_for_timeout(220)
  hit=narrow.evaluate("""e=>{const t=e.querySelector('.lex-curve-mode-toggle'),r=t.getBoundingClientRect();
    const n=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
    return n?(n.className?.baseVal??n.className):None}""")
  assert hit and 'lex-curve-mode-toggle' in hit,hit
  toggle=narrow.locator('.lex-curve-mode-toggle')
  toggle.click()
  assert toggle.inner_text()=='LINE'
  assert narrow.evaluate("e=>e.querySelector('.lex-curve-plot').classList.contains('lex-curve-bar-mode')")
  toggle.click()
  assert toggle.inner_text()=='BARS'
  # A wrapped strip fills the row it is in and keeps its rows down to two. The
  # grid this replaced left the last row short of the right edge and, in a
  # 240px card, needed three rows - 109px of a 143px card, so the strip covered
  # the graph it belongs to.
  page.evaluate("""()=>{const mount=document.createElement('div');
    mount.id='wrap-mount';mount.style.cssText='width:240px;height:200px;margin-top:12px';
    document.body.append(mount);
    const variables=['A','B','C','D'].map(label=>({label,control:LexeditorUI.el('input',{type:'number',value:20,min:0,max:255})}));
    mount.append(LexeditorUI.curveEditor({title:'WRAP',variables,domain:{min:1,max:100},range:{min:0,max:255},evaluate:x=>x,formula:LexeditorUI.mathFormula('N = A')}));}""")
  wrap=page.locator('#wrap-mount .lex-curve-editor')
  wrap.hover();page.wait_for_timeout(220)
  strip=wrap.evaluate("""e=>{const drawer=e.querySelector('.lex-curve-variables'),
    items=[...drawer.children].map(node=>node.getBoundingClientRect()),bands=[];
    for(const item of [...items].sort((a,b)=>a.top-b.top)){const band=bands.find(b=>item.top<b.bottom&&item.bottom>b.top);
      if(band){band.items.push(item);band.top=Math.min(band.top,item.top);band.bottom=Math.max(band.bottom,item.bottom)}
      else bands.push({top:item.top,bottom:item.bottom,items:[item]})}
    const last=bands[bands.length-1],box=drawer.getBoundingClientRect();
    return {rows:bands.length,slack:Math.round(box.right-6-Math.max(...last.items.map(item=>item.right))),
      share:Math.round(box.height/e.getBoundingClientRect().height*100),
      widths:[...e.querySelectorAll('.lex-curve-variable input')].map(node=>Math.round(node.getBoundingClientRect().width))}}""")
  assert strip['rows']<=2,strip
  assert strip['slack']<=2,strip
  assert strip['share']<=65,strip
  assert len(strip['widths'])==4 and min(strip['widths'])>=70,strip
  page.mouse.move(1,1);page.wait_for_timeout(250)
  page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-ff8-eight-graphs.png'))
  browser.close();print('Eight graphs: titles, borders, colors, drawer bounds and equation spacing passed.')
if __name__=='__main__':main()
