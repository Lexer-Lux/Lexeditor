"""Compatibility portrait sizing is shared between Magic and GFs."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
def main():
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page()
  p.route('http://fixture/',lambda r:r.fulfill(body='<div id="fixture"></div>',content_type='text/html'));p.goto('http://fixture/')
  p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  p.add_style_tag(content=re.search(r'<style>(.*?)</style>',(ROOT/'games/ff8/editor.html').read_text(encoding='utf-8'),re.S).group(1))
  p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  p.evaluate('''()=>{const U=LexeditorUI;for(const magic of [false,true]){const host=U.el('div',{class:magic?'magic-compat-column':'',style:'height:800px;width:300px'});host.append(U.columnList({class:'gf-compat-table ff8-record-list',rows:Array.from({length:16},(_,id)=>({id})),key:r=>r.id,template:'minmax(135px,1fr) 90px',columns:[{key:'id',label:'GF',render:r=>U.hoverable({class:'gf-entity-label',content:[U.el('span',{class:'gf-link-portrait-slot'},U.el('img',{class:'gf-link-portrait',src:'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="40" height="60"><rect width="40" height="60" fill="silver"/></svg>'})),U.el('span',{},'Alexander')]})},{key:'value',label:'Change',render:()=>U.el('input',{value:'0'})}]}));document.querySelector('#fixture').append(host)}}''')
  for height in [600,800,1000]:
   p.evaluate('h=>document.querySelectorAll("#fixture>div").forEach(e=>e.style.height=h+"px")',height)
   sizes=p.locator('.gf-link-portrait').evaluate_all('''es=>es.map(e=>{const r=e.getBoundingClientRect(),c=e.closest('.lex-column-list-cell').getBoundingClientRect();return {h:r.height,available:c.height,top:r.top-c.top,bottom:c.bottom-r.bottom}})''')
   assert len(sizes)==32
   assert all(abs(s['available']-s['h']-12)<.1 for s in sizes),sizes
   assert all(s['h']>20 and s['top']>=3 and s['bottom']>=3 for s in sizes),sizes
  b.close()
 print('Magic/GF portraits use identical available row height with margins at three panel heights.')
if __name__=='__main__':main()
