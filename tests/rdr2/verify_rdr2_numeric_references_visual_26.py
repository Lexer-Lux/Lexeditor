"""Rendered numeric references using production RDR2 UI and synthetic data."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rdr2_browser_check import document
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width':1000,'height':750})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('**/*', lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function("!state.booting&&state.catalog?.items?.length")
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            probe = page.evaluate("""()=>{
              window.applied=null;
              const matching=refStack([['V','vtag',50],['K','ktag',50]],50,value=>applied=value,String);
              const input=el('input',{value:'50'});
              const differing=refField(input,[['V','vtag',60],['K','ktag',50]],50,value=>applied=value,String);
              differing.style.cssText='position:fixed;left:20px;top:200px;width:260px';
              document.querySelector('#main').replaceChildren(differing);
              return {matchingAbsent:matching==='',labels:[...differing.querySelectorAll('.lex-reference-value')].map(n=>n.textContent.trim())};
            }""")
            assert probe['matchingAbsent'], probe
            assert probe['labels'] == ['V60'], probe
            button = page.locator('#main .lex-reference-value')
            assert button.is_visible()
            assert button.evaluate('n=>n.scrollWidth<=n.clientWidth+1')
            assert button.evaluate('''n=>{
              const b=n.getBoundingClientRect(),i=document.querySelector('#main input').getBoundingClientRect();
              return Math.abs((b.top+b.bottom-i.top-i.bottom)/2)<=3;
            }''')
            button.click()
            assert page.evaluate('window.applied') == 60
            assert not errors, errors
            output=Path(tempfile.gettempdir())/'lexeditor-dev'/'rdr2-numeric-reference.png'
            output.parent.mkdir(exist_ok=True)
            page.screenshot(path=str(output))
            print(f'Equal references hidden; differing vanilla value restores on click. Screenshot: {output}')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
