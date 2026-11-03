"""RDR2's shared subtabs continue the active main tab's red surface."""
from pathlib import Path
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(ROOT/'tests'/'rdr2'))
from plugin_ui import plugin_ui
from rdr2_browser_check import document


def main():
    source=plugin_ui('rdr2')
    assert source.count('LexeditorUI.subtabBar(')>=8, 'RDR2 pages must use shared subtab bars'
    output=Path(tempfile.gettempdir())/'lexeditor-dev'/'rendered'
    output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1600,'height':900})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('**/*',lambda route:route.abort())
            page.set_content(document().replace('<head>','<head><base href="https://lexeditor.test/">',1))
            page.wait_for_function("!state.booting&&!document.documentElement.classList.contains('lex-loading-live')")
            for tab,active in [('effects','effects'),('effects','behaviors'),('crafting','vanilla')]:
                page.evaluate('''async ([tab,active])=>{
                  state.filters.effectSection=tab==='effects'?active:'effects';
                  state.tab=tab;await render();
                }''',[tab,active])
                bar=page.locator('#toolbar > .lex-subtab-bar')
                bar.wait_for()
                page.wait_for_function("getComputedStyle(document.querySelector('nav button.active')).backgroundColor===getComputedStyle(document.querySelector('#toolbar>.lex-subtab-bar')).backgroundColor")
                metrics=bar.evaluate('''bar=>{
                  const main=document.querySelector('nav button.active'),
                    chosen=bar.querySelector('.lex-subtab-button.active'),
                    mb=main.getBoundingClientRect(),bb=bar.getBoundingClientRect(),
                    style=getComputedStyle(chosen);
                  return{mainBackground:getComputedStyle(main).backgroundColor,
                    barBackground:getComputedStyle(bar).backgroundColor,gap:bb.top-mb.bottom,
                    children:[...bar.children].map(node=>({background:getComputedStyle(node).backgroundColor,
                      border:getComputedStyle(node).borderTopWidth,radius:getComputedStyle(node).borderRadius})),
                    marker:style.boxShadow,color:style.color};
                }''')
                assert metrics['barBackground']==metrics['mainBackground']!='rgba(0, 0, 0, 0)',metrics
                assert abs(metrics['gap'])<1,metrics
                assert all(child=={'background':'rgba(0, 0, 0, 0)','border':'0px','radius':'0px'} for child in metrics['children']),metrics
                assert 'inset' in metrics['marker'] and '3px' in metrics['marker'] and metrics['color'] in metrics['marker'],metrics
                inactive=bar.locator('.lex-subtab-button:not(.active)').first
                before=inactive.evaluate('(node)=>getComputedStyle(node).color')
                inactive.hover()
                assert inactive.evaluate('(node)=>getComputedStyle(node).color')!=before
                page.keyboard.press('Escape')
                inactive.focus()
                assert inactive.evaluate('(node)=>getComputedStyle(node).outlineWidth')=='2px'
                page.screenshot(path=str(output/f'rdr2-flowing-{tab}-{active}.png'))
                inactive.blur()
            assert not errors,errors
        finally:
            browser.close()
    print('PASS: shared RDR2 red strip, seam-free main/subtabs, selected underline, hover and keyboard focus')


if __name__=='__main__':
    main()
