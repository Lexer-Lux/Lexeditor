"""Weapon portrait placement and character replacement through the shared finder."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-weapon-character-') as project:
        with FF8Session({'LEXEDITOR_FF8_PROJECT': project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1600, 'height': 1000})
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.documentElement.classList.contains('lex-loading-live')", timeout=30000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            page.evaluate("state.selected.weapons=0;navigate('weapons')")
            page.wait_for_selector('button[aria-label="Choose character for Revolver"]')
            page.wait_for_function("[...document.querySelectorAll('.lex-record-card img')].every(i=>i.complete&&i.naturalWidth>0)")
            card = page.locator('.lex-record-card')
            assert card.locator('img').get_attribute('alt') == 'Squall'
            assert card.bounding_box()['width'] >= 90
            assert page.locator('.lex-detail-panel-beside').evaluate('''node=>{
                const [portrait,fields]=node.children;
                return portrait.getBoundingClientRect().right<=fields.getBoundingClientRect().left;
            }''')
            output = Path(tempfile.gettempdir())/'lexeditor-dev'/'weapon-character.png'
            output.parent.mkdir(exist_ok=True)
            page.screenshot(path=str(output))
            ingredient = page.locator('.weapon-ingredient-row').last
            ingredient.scroll_into_view_if_needed()
            assert ingredient.is_visible()
            card.scroll_into_view_if_needed()
            # Use the isolated fixture project; selecting never touches the user's mod.
            page.evaluate("state.activeSource='mine';renderWeapons()")
            card.hover()
            page.get_by_role('button', name='Choose character for Revolver', exact=True).click()
            target = page.locator('#characters-tab-1')
            assert 'lex-search-candidate' in target.get_attribute('class')
            assert not target.evaluate('n=>!!n.closest("[inert]")')
            target.hover()
            page.mouse.down()
            page.wait_for_timeout(800)
            page.mouse.up()
            page.wait_for_selector('button[aria-label="Choose character for Revolver"]')
            assert page.locator('.lex-record-card img').get_attribute('alt') == 'Zell'
            assert page.evaluate("state.data.weapons.rows[0].fields.find(f=>f.field==='character_id').value") == 1
            card.hover()
            page.get_by_role('button', name='Choose character for Revolver', exact=True).click()
            page.get_by_role('button', name='Cancel selection', exact=True).click()
            assert page.evaluate("state.data.weapons.rows[0].fields.find(f=>f.field==='character_id').value") == 1
            page.locator('figcaption .lex-hoverable').click()
            page.wait_for_function("state.tab==='characters'&&state.selected.characters===1")
            browser.close()
            print(f'Weapon portrait, linked name and finder replacement passed. Screenshot: {output}')


if __name__ == '__main__':
    main()
