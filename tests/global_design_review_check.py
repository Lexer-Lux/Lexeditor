"""Interactive design previews and accessible, schema-derived control help."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('global_fixtures', ROOT/'tests/global_browser_check.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def main() -> None:
    out = Path(os.environ.get('LEXEDITOR_REVIEW_OUT', str(ROOT/'out/global-review')))
    out.mkdir(parents=True, exist_ok=True)
    # Replay local application resources; every outside request is rejected.
    os.environ['LEXEDITOR_BROWSER_OFFLINE'] = '1'
    results = []
    with sync_playwright() as playwright:
        args = {'headless': True, 'args': ['--no-sandbox']}
        if os.environ.get('CHROMIUM_PATH'):
            args['executable_path'] = os.environ['CHROMIUM_PATH']
        browser = playwright.chromium.launch(**args)
        for width, height in [(900,620), (1600,900)]:
            page = browser.new_page(viewport={'width':width,'height':height})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            fixtures.load_page(page, '', '/games/blank/editor.html')
            page.get_by_role('button', name='Design Review', exact=True).click()
            page.get_by_label('Layout proposal', exact=True).select_option('tabs')
            assert page.locator('.lex-review-details .lex-review-model').count() == 1
            page.get_by_role('button', name='Hide preview', exact=True).click()
            assert not page.locator('.lex-review-model').is_visible()
            page.get_by_role('button', name='Show preview', exact=True).click()
            page.get_by_label('Layout proposal', exact=True).select_option('rail')
            assert page.locator('.lex-review-side-rail').count() == 1
            assert page.locator('.lex-review-rail-content > .lex-review-model').count() == 1
            page.locator('.lex-design-review').evaluate('(e)=>e.scrollTop=0')
            page.screenshot(path=str(out/f'layout-{width}.png'))
            assert page.get_by_label('Formula typography', exact=True).count() == 0
            assert page.locator('.lex-review-fraction').count() == 1
            assert 'no remaining A/B choice' in page.locator('.lex-review-section').nth(1).inner_text()
            page.get_by_role('slider', name='Multiplier A', exact=True).fill('2')
            assert page.locator('.lex-review-max').inner_text() == 'max 200'
            formula = page.locator('.lex-review-formula')
            formula.scroll_into_view_if_needed()
            assert formula.evaluate('(e)=>getComputedStyle(e).backgroundColor') == 'rgba(0, 0, 0, 0)'
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
            page.screenshot(path=str(out/f'formula-{width}.png'))
            page.close()
            results.append({'viewport':[width,height],'new_layout_alternatives':'pass','approved_formula_A':'pass','errors':errors})
            assert not errors, errors
        page = browser.new_page(viewport={'width':900,'height':620})
        fixtures.load_page(page, '', '/games/blank/editor.html')
        page.evaluate('''() => {
          const {el,detailField,unitField,infoHelp}=LexeditorUI;
          const field=detailField({label:'Example cost',control:unitField(el('input',{id:'help-contract',type:'number',min:0,max:100,step:1,value:20}),'G')});
          document.querySelector('#main').replaceChildren(field);
        }''')
        control = page.locator('#help-contract')
        text = control.get_attribute('aria-description')
        assert '0 to 100' in text and 'Whole numbers only' in text and 'Unit: G' in text
        assert 'not documented' in text # no invented runtime effect for unknown data
        marker = page.locator('.lex-info-help').last
        assert marker.evaluate('(e)=>!e.closest(\'[aria-hidden="true"]\')')
        marker.focus()
        popup = page.get_by_role('tooltip')
        popup.wait_for(state='visible')
        page.keyboard.press('ArrowDown')
        assert popup.evaluate('(e)=>e===document.activeElement')
        page.keyboard.press('Escape')
        assert page.get_by_role('tooltip').count() == 0
        # A long source description is retained and can be scrolled while focused.
        page.evaluate('''() => document.querySelector('#main').replaceChildren(LexeditorUI.infoHelp('Important constraint. '.repeat(400)))''')
        page.locator('.lex-info-help').last.focus()
        page.keyboard.press('ArrowDown')
        popup = page.get_by_role('tooltip')
        popup.evaluate('(e)=>e.scrollTop=100')
        page.wait_for_timeout(250)
        assert popup.count() == 1 and 'Important constraint.' in popup.inner_text()
        page.keyboard.press('Escape')
        assert popup.count() == 0
        browser.close()
        results.append({'input_constraints':'pass','unknown_meaning_not_invented':'pass','long_help_keyboard_scroll':'pass'})
    (out/'results.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results))


if __name__ == '__main__':
    main()
