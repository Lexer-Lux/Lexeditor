"""Weapon checkbox alignment, arrow gap, and pin visibility."""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
def main():
 s=plugin_ui('ff8')
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':2560,'height':1352})
  p.route('http://fixture/',lambda r:r.fulfill(content_type='text/html',body='<body data-lex-plugin="ff8"><div class="lex-detail-panel weapon-detail"><div id="fields"></div></div></body>'));p.goto('http://fixture/')
  p.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'))
  p.add_style_tag(content=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8'))
  p.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
  p.evaluate("""()=>{const U=LexeditorUI, prefs=U.columnPreferences('weapon-bool-test',[{key:'melee',label:'Melee weapon',defaultVisible:false}],()=>{});
   for(const bool of [false,true]){
    const input=U.el('input',bool?{type:'checkbox'}:{type:'number',value:20});
    document.querySelector('#fields').append(U.detailField({className:'weapon-data-field',label:bool?'Melee weapon':'Attack power',control:U.provenanceControl({control:input,current:bool?false:20,vanilla:bool?false:20,references:[],apply(){},internal:true}),pin:bool?prefs.pinButton('melee','Melee weapon'):null}));
   }
  }""")
  for width in [400,800,1450]:
   for scale in [.96,1,1.5]:
    p.evaluate('([w,s])=>{document.querySelector(".weapon-detail").style.width=w+"px";document.body.style.zoom=s}',[width,scale]);p.wait_for_timeout(80)
    result=p.evaluate("""()=>{const row=document.querySelector('.lex-boolean-field'),r=e=>e.getBoundingClientRect(),labels=document.querySelectorAll('.lex-detail-field-label'),arrow=row.querySelector('.lex-field-boolean-arrow'),box=row.querySelector('input'),pin=row.querySelector('.lex-column-pin');return {labelDelta:Math.abs(r(labels[0]).right-r(labels[1]).right),gap:r(box).left-r(arrow).right,line:r(arrow).width,pinOverflow:getComputedStyle(pin).overflow,pinInside:r(pin).right<=r(row).right-4&&r(pin).left>=r(row).left}}""")
    assert result['labelDelta']<2,(width,scale,result)
    # The requested arrow-to-box gap is ten CSS pixels, including at UI zoom.
    assert abs(result['gap']/scale-10)<.6,(width,scale,result)
    assert result['line']>60,(width,scale,result)
    assert result['pinOverflow']=='visible' and result['pinInside'],result
  p.locator('.lex-boolean-field').hover()
  p.locator('#fields').screenshot(path='C:/Users/Lexer/AppData/Local/Temp/lexeditor-weapon-checkbox.png')
  p.locator('input[type=checkbox]').check();assert p.locator('input[type=checkbox]').is_checked()
  p.locator('.lex-column-pin').click();assert p.locator('.lex-column-pin').get_attribute('aria-pressed')=='true'
  b.close()
 print('Weapon label alignment, arrow line/gap, visible pin, checkbox and pin clicks passed at three widths and scales.')
if __name__=='__main__':main()
