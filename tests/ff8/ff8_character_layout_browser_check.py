"""FF8 Characters page: limit break is a top strip, stat growth fills below."""
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from plugins.ff8.plugin import FF8Session
def main():
 with tempfile.TemporaryDirectory(prefix='lexeditor-character-layout-') as project, FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True)
   page=browser.new_page(viewport={'width':1600,'height':950})
   page.goto(session.url)
   page.wait_for_function("typeof state!=='undefined'&&!state.booting",timeout=90000)
   page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')",timeout=30000)
   page.evaluate("navigate('characters')")
   page.wait_for_selector('.character-detail',timeout=30000)
   page.wait_for_timeout(500)
   geo=page.evaluate("""()=>[...document.querySelectorAll('.character-detail > .lex-detail-panel-body > .lex-detail-section')].map(s=>{const r=s.getBoundingClientRect(),t=s.querySelector('.lex-detail-section-title');return{title:(t?t.textContent:'?').trim(),top:Math.round(r.top),bottom:Math.round(r.bottom),left:Math.round(r.left),width:Math.round(r.width)}})""")
   assert [g['title'].rstrip('?').strip() for g in geo]==['LIMIT BREAK','STAT GROWTH'],geo
   limit,growth=geo
   # The limit break strip sits above the stat growth section, not beside it.
   assert limit['bottom']<=growth['top'],geo
   assert limit['left']==growth['left'] and limit['width']==growth['width'],geo
   # All three limit break fields share one row inside the strip.
   tops=page.locator('.character-limit-break .lex-detail-part').evaluate_all('parts=>parts.map(p=>Math.round(p.getBoundingClientRect().top))')
   assert len(tops)==3 and len(set(tops))==1,tops
   page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-character-layout.png'))
   browser.close();print('Character layout: limit break top strip, stat growth below, passed.')
if __name__=='__main__':main()
