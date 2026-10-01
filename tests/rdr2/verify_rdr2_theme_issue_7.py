"""Verify RDR2's registered theme on the rendered shared components."""
from pathlib import Path
import tempfile
from playwright.sync_api import expect, sync_playwright
from rdr2_browser_check import document


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('**/*', lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function("!document.documentElement.classList.contains('lex-loading-live')")
            expect(page.get_by_role('textbox', name='Item name', exact=True)).to_be_visible()
            styles = page.evaluate("""()=>{
              const css=n=>getComputedStyle(n);
              const save=document.querySelector('#global-save');
              const heading=document.querySelector('.lex-detail-panel-title');
              const input=document.querySelector('.lex-inline-label input');
              return {
                body:css(document.body).fontFamily,
                heading:css(heading).fontFamily,
                tabs:[...document.querySelectorAll('nav button[data-tab]')].map(n=>css(n).fontFamily),
                save:css(save).fontFamily,saveClass:save.classList.contains('lex-save-icon'),
                saveDisabled:save.disabled,
                inputLine:parseFloat(css(input).lineHeight)/parseFloat(css(input).fontSize),
                metrics:[...document.fonts].filter(f=>f.family==='Lex RDR Lino').map(f=>({
                  size:f.sizeAdjust,ascent:f.ascentOverride,descent:f.descentOverride,gap:f.lineGapOverride
                }))
              };
            }""")
            assert 'Lex RDR Lino' in styles['body'], styles
            assert 'Lex Redemption' in styles['heading'], styles
            assert styles['tabs'] and all('Lex Redemption' in font for font in styles['tabs']), styles
            assert styles['saveClass'] and 'Segoe UI Emoji' in styles['save'], styles
            assert styles['saveDisabled'], styles
            assert styles['inputLine'] >= 1.3, styles
            assert styles['metrics'] == [{'size':'95%','ascent':'90%','descent':'10%','gap':'20%'}], styles
            assert not errors, errors
            output = Path(tempfile.gettempdir()) / 'lexeditor-dev' / 'rdr2-theme.png'
            output.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output))
        finally:
            browser.close()
    print('PASS: shared RDR2 body, heading, tab and save-icon fonts; input line height and font metrics')


if __name__ == '__main__':
    main()
