"""FF8 GF center panel: HP and XP tabs, no leveling pager."""
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from plugins.ff8.plugin import FF8Session
def main():
 with tempfile.TemporaryDirectory(prefix='lexeditor-gf-level-tabs-') as project, FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True)
   page=browser.new_page(viewport={'width':1600,'height':950})
   page.goto(session.url)
   page.wait_for_function("typeof state!=='undefined'&&!state.booting",timeout=90000)
   page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')",timeout=30000)
   page.evaluate("navigate('gfs')")
   page.wait_for_selector('#gf-detail',timeout=30000)
   page.wait_for_timeout(500)
   bar=page.locator('#gf-detail .lex-tabbed-panel > .lex-subtab-bar').first
   names=[name.strip().rstrip('.?').strip() for name in bar.locator('.lex-subtab-button').all_text_contents()]
   assert 'Leveling' not in names,names
   assert 'HP' in names and 'XP' in names,names
   center=page.locator('#gf-detail .lex-tabbed-panel-content').first
   assert center.locator('.lex-pager, .lex-compact-pager').count()==0
   titles=center.locator('.lex-curve-editor').evaluate_all("cards=>cards.map(card=>card.dataset.curve||card.querySelector('.lex-curve-heading')?.textContent?.trim())")
   assert titles==['HP'],titles
   bar.locator('.lex-subtab-button').filter(has_text='XP').click()
   page.wait_for_timeout(300)
   titles=page.locator('#gf-detail .lex-tabbed-panel-content').first.locator('.lex-curve-editor').evaluate_all("cards=>cards.map(card=>card.dataset.curve||card.querySelector('.lex-curve-heading')?.textContent?.trim())")
   assert titles==['XP'],titles
   # A stale Leveling selection from before the split lands on the HP tab.
   page.evaluate("()=>{state.gfDetailTab='properties';renderGFs();return 1}")
   page.wait_for_timeout(300)
   active=page.locator('#gf-detail .lex-tabbed-panel > .lex-subtab-bar .lex-subtab-button.active').first.inner_text().strip().rstrip('?').strip().lower()
   assert active=='hp',active
   page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-gf-level-tabs.png'))
   browser.close();print('GF center panel: HP and XP tabs, no pager, passed.')
if __name__=='__main__':main()
