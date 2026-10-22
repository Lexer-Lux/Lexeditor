"""FF8 Magic Junction tab: copy buttons sit beside their props, not across dead space."""
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from plugins.ff8.plugin import FF8Session
def main():
 with tempfile.TemporaryDirectory(prefix='lexeditor-junction-gap-') as project, FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True)
   page=browser.new_page(viewport={'width':1600,'height':950})
   page.goto(session.url)
   page.wait_for_function("typeof state!=='undefined'&&!state.booting",timeout=90000)
   page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')",timeout=30000)
   page.evaluate("state.abilityTab='magic';state.magicDetailTab='junction';navigate('abilities')")
   page.wait_for_selector('.magic-junction-stats',timeout=30000)
   page.wait_for_timeout(500)
   gaps=page.evaluate("""()=>[...document.querySelectorAll('.magic-junction-stats .lex-detail-part')].map(part=>{
     const copy=part.querySelector('.lex-copy-value'),label=part.querySelector('.lex-detail-part-label');
     const c=copy.getBoundingClientRect(),l=label.getBoundingClientRect();
     return Math.round(l.left-c.right)})""")
   assert len(gaps)==9,gaps
   assert max(gaps)<=30,gaps
   page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-junction-gap.png'))
   browser.close();print('Magic Junction: copy buttons beside their props passed.')
if __name__=='__main__':main()
