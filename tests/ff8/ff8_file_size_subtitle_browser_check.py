"""FF8 file-backed views: the detail subtitle shows the file size."""
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from plugins.ff8.plugin import FF8Session
def subtitle(page):
 # inner_text separates inline-flex items with newlines; the line reads as one.
 return ' '.join(page.locator('.lex-detail-panel-meta').first.inner_text().split())
def main():
 with tempfile.TemporaryDirectory(prefix='lexeditor-file-subtitle-') as project, FF8Session({'LEXEDITOR_FF8_PROJECT':project}) as session:
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
   meta=subtitle(page)
   expect=page.evaluate("""()=>{const row=state.data.sfx.rows.find(r=>r.valid&&typeof r.id==='number');return assetFileSize(row.bytes)}""")
   assert meta==expect,(meta,expect)
   page.evaluate("navigate('textures')")
   page.wait_for_function("state.data.textures&&state.data.textures.rows&&state.data.textures.rows.length>0",timeout=60000)
   page.evaluate("""()=>{const row=state.data.textures.rows.find(r=>r.mapped&&r.sizeBytes);
     state.selected.textures=row.id;state.filters.textures='';state.pages.textures=0;renderTextures();return 1}""")
   page.wait_for_timeout(500)
   meta=subtitle(page)
   expect=page.evaluate("""()=>{const row=state.data.textures.rows.find(r=>r.mapped&&r.sizeBytes);return `${row.modelFile||row.id} \u00b7 ${assetFileSize(row.sizeBytes)}`}""")
   assert meta==expect,(meta,expect)
   screenshot=page.locator('.lex-detail-panel-meta').first.screenshot(path=str(Path(tempfile.gettempdir())/'lex-file-subtitle.png'))
   browser.close();print('File-backed views: file size as detail subtitle passed.')
if __name__=='__main__':main()
