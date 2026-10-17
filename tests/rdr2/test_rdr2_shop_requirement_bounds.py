"""Shop availability counts and condition states are nonnegative whole numbers."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rdr2_browser_check import document
from plugins.rdr2 import server as s


def test_normalize_rejects_negative_count_and_state():
    with pytest.raises(ValueError, match='nonnegative'):
        s.normalize_shop_requirement_groups([{'count': '-1', 'requirements': []}], 'SHOP')
    with pytest.raises(ValueError, match='nonnegative'):
        s.normalize_shop_requirement_groups(
            [{'count': '1', 'requirements': [{'type': 'T', 'key': 'K', 'state': '-1', 'lock': 'false'}]}],
            'SHOP')


def test_normalize_accepts_zero_count_and_state():
    assert s.normalize_shop_requirement_groups(
        [{'count': '0', 'requirements': [{'type': 'T', 'key': 'K', 'state': '0', 'lock': 'false'}]}],
        'SHOP') == [{'count': '0', 'requirements': [{'type': 'T', 'key': 'K', 'state': '0', 'lock': 'false'}]}]


def test_dialog_bounds_inputs_and_notes_unproven_state_ceiling():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 900})
            page.route('**/*', lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            assert 'nonnegative' in page.evaluate('validateShopRequirementDraft([{count:"-1",requirements:[]}])')
            assert 'nonnegative' in page.evaluate(
                'validateShopRequirementDraft([{count:"1",requirements:[{type:"T",key:"K",state:"-2",lock:"false"}]}])')
            assert page.evaluate(
                'validateShopRequirementDraft([{count:"0",requirements:[{type:"T",key:"K",state:"0",lock:"false"}]}])') == ''
            page.evaluate('''()=>{
              state.shopDirty=new Set();
              state.shops={shops:[{type:'SHOP_GENERAL_STORE',items:[{item:'CONSUMABLE_RUM',
                requirementGroups:[{count:'1',requirements:[{type:'T',key:'K',state:'1',lock:'false'}]}]}]}]};
              window.renderedShops=false;
              window.renderShops=()=>{window.renderedShops=true};
              const shop=state.shops.shops[0];
              window.shopRow=shop.items[0];
              showShopRequirements(shop,window.shopRow,{key:'CONSUMABLE_RUM',nameKey:'NAME_RUM'});
            }''')
            dialog = page.get_by_role('dialog').filter(has_text='AVAILABILITY')
            expect(dialog).to_be_visible()
            count = dialog.get_by_role('spinbutton', name='Count', exact=True)
            state = dialog.get_by_role('spinbutton', name='State', exact=True)
            assert count.get_attribute('min') == '0'
            assert state.get_attribute('min') == '0'
            assert 'No highest state is proven' in (state.get_attribute('aria-description') or '')
            count.fill('-1')
            dialog.get_by_role('button', name='APPLY', exact=True).click()
            expect(dialog).to_be_visible()
            assert page.evaluate('window.shopRow.requirementGroups[0].count') == '1'
            count.fill('0')
            state.fill('-2')
            dialog.get_by_role('button', name='APPLY', exact=True).click()
            expect(dialog).to_be_visible()
            assert page.evaluate('window.shopRow.requirementGroups[0].requirements[0].state') == '1'
            state.fill('3')
            dialog.get_by_role('button', name='APPLY', exact=True).click()
            expect(dialog).to_be_hidden()
            assert page.evaluate('window.shopRow.requirementGroups') == [
                {'count': '0', 'requirements': [{'type': 'T', 'key': 'K', 'state': '3', 'lock': 'false'}]}]
            assert page.evaluate('window.renderedShops') is True
        finally:
            browser.close()
