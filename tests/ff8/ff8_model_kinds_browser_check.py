"""FF8 Models tab: Unsupported and Sound data rows explain themselves."""
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from plugins.ff8.plugin import FF8Session
def select(page,fixture):
 page.evaluate(f"""()=>{{const row=state.data.models.rows.find(r=>r.file==={fixture!r});
   state.selected.models=row.id;state.filters.models={fixture!r};state.pages.models=0;renderModels();return 1}}""")
 page.wait_for_timeout(500)
def main():
 with tempfile.TemporaryDirectory(prefix='lexeditor-model-kinds-') as project, FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True)
   page=browser.new_page(viewport={'width':1600,'height':950})
   page.goto(session.url)
   page.wait_for_function("typeof state!=='undefined'&&!state.booting",timeout=90000)
   page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')",timeout=30000)
   page.evaluate("navigate('models')")
   page.wait_for_function("state.data.models&&state.data.models.rows&&state.data.models.rows.length>0",timeout=60000)
   page.wait_for_timeout(800)
   kind=page.locator('.lex-column-list-head-cell').filter(has_text='Kind')
   assert kind.count()==1
   bubble=kind.locator('.lex-info-help')
   assert bubble.count()==1
   label=bubble.get_attribute('aria-label') or ''
   assert 'Sound data' in label and 'Unsupported' in label,label
   select(page,'mag184_f.dat')
   stored=page.locator('.lex-detail-field').filter(has_text='STORED NUMBER')
   assert stored.count()==1
   assert stored.locator('.lex-info-help').count()==1
   select(page,'mag005_b.08')
   replace=page.get_by_role('button',name='Replace',exact=True)
   assert replace.is_disabled()
   reason=replace.get_attribute('data-lex-title') or replace.get_attribute('title') or ''
   assert 'cannot be replaced' in reason,reason
   page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-model-kinds.png'))
   browser.close();print('Models tab: Unsupported and Sound data rows explained, passed.')
if __name__=='__main__':main()
