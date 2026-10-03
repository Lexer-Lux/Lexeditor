"""Production item creation offers observed choices and retains failed drafts."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rdr2_browser_check import document


def test_item_creation_choices_failure_retry_and_read_only(tmp_path):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 900})
            page.route('**/*', lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            page.evaluate('''()=>{
              state.catalog.items.push({...state.catalog.items[0],key:'LEX_GUNPOWDER',category:'CI_CATEGORY_MATERIALS',group:'PROVISION'});
              const fetchOriginal=window.fetch;window.__creationFails=true;
              window.fetch=async(url,opts)=>url.startsWith('/api/catalog/create')&&window.__creationFails
                ?new Response(JSON.stringify({error:'Synthetic write failure'}),{status:500}):fetchOriginal(url,opts);
              createNewItem();
            }''')
            dialog = page.get_by_role('dialog').filter(has_text='Create item record')
            expect(dialog.get_by_role('combobox')).to_have_count(2)
            selects = dialog.get_by_role('combobox')
            assert selects.nth(0).locator('option').evaluate_all('options=>options.map(o=>o.value)') == ['CI_CATEGORY_CONSUMABLE', 'CI_CATEGORY_MATERIALS']
            assert selects.nth(1).locator('option').evaluate_all('options=>options.map(o=>o.value)') == ['Consumables', 'PROVISION']
            expect(selects.nth(0)).to_have_value('CI_CATEGORY_MATERIALS')
            expect(selects.nth(1)).to_have_value('PROVISION')
            fields = dialog.get_by_role('textbox')
            create = dialog.get_by_role('button', name='Create item', exact=True)
            create.click()
            assert not page.evaluate("window.__requests.some(r=>r.path==='/api/catalog/create')")
            fields.nth(0).fill('lex_fixture')
            fields.nth(1).fill('Fixture')
            fields.nth(2).fill('Description')
            create.click()
            expect(page.locator('.lex-toast').filter(has_text='Synthetic write failure')).to_be_visible()
            expect(dialog).to_be_visible()
            expect(fields.nth(0)).to_have_value('lex_fixture')
            page.screenshot(path=str(tmp_path / 'creation.png'), full_page=True)
            page.evaluate('window.__creationFails=false')
            create.click()
            page.wait_for_function("window.__requests.some(r=>r.path==='/api/catalog/create')")
            assert page.evaluate("window.__requests.find(r=>r.path==='/api/catalog/create').body") == {
                'key': 'LEX_FIXTURE', 'name': 'Fixture', 'description': 'Description',
                'category': 'CI_CATEGORY_MATERIALS', 'group': 'PROVISION', 'capacity': 20}
            expect(dialog).to_have_count(0)
            page.evaluate("state.ds='vanilla';createNewItem()")
            expect(dialog).to_have_count(0)
        finally:
            browser.close()
