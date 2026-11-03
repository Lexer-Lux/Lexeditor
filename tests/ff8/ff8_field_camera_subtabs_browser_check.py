"""FF8 Field Camera tab: Position/Ranges/Movie live as sub-tabs of Camera."""
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from plugins.ff8.plugin import FF8Session
MAP='bghall_1'
def labels(page,root):
 return page.evaluate("""root=>[...root.querySelectorAll(':scope .lex-subtab-button')].map(node=>node.textContent.trim().replace(/[.?]+$/,''))""",root)
def main():
 with tempfile.TemporaryDirectory(prefix='lexeditor-field-camera-subtabs-') as project, FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True)
   page=browser.new_page(viewport={'width':1600,'height':950})
   page.goto(session.url)
   page.wait_for_function("typeof state!=='undefined'&&!state.booting",timeout=90000)
   page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')",timeout=30000)
   page.evaluate(f"""()=>{{const row=state.data.fields.rows.find(r=>r.name==={MAP!r});
     state.selected.fields=row.id;state.filters.fields={MAP!r};state.fieldDetailTab='camera';navigate('fields');return 1}}""")
   page.wait_for_function("state.data.fields.rows.some(r=>r._loaded)",timeout=60000)
   page.wait_for_timeout(500)
   outer=page.locator('#main .lex-tabbed-panel > .lex-subtab-bar').first
   names=outer.locator('.lex-subtab-button').all_text_contents()
   names=[name.strip().rstrip('.?').strip() for name in names]
   assert 'Camera' in names,names
   assert 'Camera Ranges' not in names and 'Movie Camera' not in names,names
   inner=page.locator('#main .lex-tabbed-panel-content .lex-tabbed-panel > .lex-subtab-bar')
   assert inner.count()==1
   subs=inner.locator('.lex-subtab-button').all_text_contents()
   subs=[name.strip().rstrip('?').strip() for name in subs]
   assert subs==['Movie','Position','Ranges'],subs
   active=inner.locator('.lex-subtab-button.active').inner_text().strip().rstrip('?').strip().lower()
   assert active=='position',(subs,active)
   assert page.locator('#main input[aria-label$="camera 1 zoom"]').count()==1
   inner.locator('.lex-subtab-button').filter(has_text='Ranges').click()
   page.wait_for_timeout(300)
   assert page.get_by_text('Camera range',exact=False).count()>=1
   assert 'top' in page.locator('#main .lex-tabbed-panel-content .lex-tabbed-panel-content').first.inner_text().lower()
   inner.locator('.lex-subtab-button').filter(has_text='Movie').click()
   page.wait_for_timeout(300)
   movie=page.locator('#main .lex-tabbed-panel-content .lex-tabbed-panel-content').first.inner_text()
   assert 'Frame' in movie or 'movie camera frames' in movie,movie[:400]
   # A stale ranges selection from before the merge lands on the Ranges sub-tab.
   page.evaluate("()=>{state.fieldDetailTab='ranges';rerenderFields();return 1}")
   page.wait_for_timeout(300)
   active=page.locator('#main .lex-tabbed-panel-content .lex-tabbed-panel > .lex-subtab-bar .lex-subtab-button.active').inner_text().strip().rstrip('?').strip().lower()
   assert active=='ranges',active
   page.screenshot(path=str(Path(tempfile.gettempdir())/'lex-field-camera-subtabs.png'))
   browser.close();print('Field Camera tab: Position/Ranges/Movie sub-tabs passed.')
if __name__=='__main__':main()
