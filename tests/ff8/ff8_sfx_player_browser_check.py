"""FF8 SFX: the heading player has play + scrubber; no second player in the body."""
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from plugins.ff8.plugin import FF8Session
def main():
 with tempfile.TemporaryDirectory(prefix='lexeditor-sfx-player-') as project, FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True)
   page=browser.new_page(viewport={'width':1600,'height':950})
   page.goto(session.url)
   page.wait_for_function("typeof state!=='undefined'&&!state.booting",timeout=90000)
   page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')",timeout=30000)
   page.evaluate("navigate('sfx')")
   page.wait_for_function("state.data.sfx&&state.data.sfx.rows&&state.data.sfx.rows.length>0",timeout=60000)
   page.evaluate("""()=>{const row=state.data.sfx.rows.find(r=>r.valid&&typeof r.id==='number');
     state.selected.sfx=row.id;state.filters.sfx='';state.pages.sfx=0;renderSfx();return 1}""")
   page.wait_for_timeout(500)
   assert page.locator('.lex-audio-play').count()==1
   assert page.locator('.lex-audio-scrub').count()==1
   assert page.locator('.lex-detail-panel-body audio').count()==0
   browser.close();print('FF8 SFX: heading player with scrubber passed.')
if __name__=='__main__':main()
