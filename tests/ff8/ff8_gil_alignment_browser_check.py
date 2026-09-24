"""Gil and its price share a baseline at dense FF8 table sizes."""
import base64, os, re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from plugin_ui import plugin_ui
def main():
    font=Path(os.environ['LOCALAPPDATA'])/'Lexeditor/game-data/ff8/generated/ff8-menu.ttf'
    css=(ROOT/'plugins/ff8/editor.css').read_text(encoding='utf-8')
    css=css.replace('/assets/ff8-menu.ttf?v=4','data:font/ttf;base64,'+base64.b64encode(font.read_bytes()).decode())
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True);page=browser.new_page()
        page.route('http://fixture/',lambda r:r.fulfill(body='<div class="ff8-record-list"></div>',content_type='text/html'));page.goto('http://fixture/')
        page.add_style_tag(content=(ROOT/'ui/framework.css').read_text(encoding='utf-8'));page.add_style_tag(content=css)
        page.add_script_tag(content=(ROOT/'ui/framework.js').read_text(encoding='utf-8'))
        page.evaluate('''()=>{const U=LexeditorUI;for(const size of [10,12,17,24])for(const value of [5,100,12500,50000,655350]){
          const field=U.unitField(U.numberValue(value),'G',{unitClass:'ff8-gil-unit'});field.style.fontSize=size+'px';
          for(const child of field.children){const mark=document.createElement('i');mark.className='baseline';mark.style.cssText='display:inline-block;width:0;height:0;vertical-align:baseline';const text=document.createElement('span');text.textContent=child.textContent;child.replaceChildren(text);text.append(mark)}
          document.querySelector('.ff8-record-list').append(field);
        }}''')
        page.evaluate('document.fonts.ready')
        for scale in [.96,1,1.5]:
            page.evaluate('s=>document.body.style.zoom=s',scale)
            differences=page.locator('.lex-unit-field-static').evaluate_all('''es=>es.map(e=>{let marks=e.querySelectorAll('.baseline');return Math.abs(marks[0].getBoundingClientRect().top-marks[1].getBoundingClientRect().top)})''')
            assert max(differences)<.1,differences
        browser.close()
    print('Gil baseline matches prices at four font sizes and three scales.')
if __name__=='__main__':main()
