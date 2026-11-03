"""Production prices preserve raw invalid dollars and serialize exact cents."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rdr2_browser_check import document


def test_price_drafts_redraw_history_rejection_and_exact_cents():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 900})
            page.route('**/*', lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            page.evaluate('''()=>{
              const item=state.catalog.items[0];item.buy=[{key:'BUY',costtype:'COST_TYPE_PRICE',yield:1,parts:[{item:'CURRENCY_CASH',qty:100}],unlocks:[]}];
              window.priceItem=item;window.drawPrice=()=>document.querySelector('#main').replaceChildren(priceInput(item,'buy',item.buy[0],item.buy[0].parts[0]));
              drawPrice();window.cleanHistory=rdr2HistoryCapture();
            }''')
            control = page.get_by_role('spinbutton', name='buy price for CONSUMABLE_RUM BUY', exact=True)
            for raw in ['1.001', '-1', '']:
                control.fill(raw)
                control.blur()
                expect(control).to_have_value(raw)
                assert not control.evaluate('e=>e.checkValidity()')
                assert page.evaluate('dirtyCount()') == 1
                page.evaluate('drawPrice()')
                expect(control).to_have_value(raw)
                assert 'edited' in control.get_attribute('class')
                # Draft ownership survives the same capture/restore used by history.
                page.evaluate('''()=>{const saved=rdr2HistoryCapture();state.moneyDrafts={};rdr2HistoryRestore(saved);drawPrice()}''')
                expect(control).to_have_value(raw)
                page.evaluate("document.querySelector('#main').replaceChildren()")
                before = page.evaluate('window.__requests.length')
                failure = page.evaluate('''async()=>{try{await saveCatalog();return 'saved'}catch(e){return e.message}}''')
                assert 'two decimal places' in failure
                page.evaluate('saveAllChanges()')
                assert page.evaluate('window.__requests.length') == before
                if page.locator('.lex-important-dialog').count():
                    page.locator('.lex-important-dialog').get_by_role('button', name='Confirm and Close', exact=True).click()
                page.evaluate('drawPrice()')
                page.evaluate('''()=>{rdr2HistoryRestore(cleanHistory);drawPrice()}''')
                expect(control).to_have_value('1.00')
                assert page.evaluate('dirtyCount()') == 0
            control.fill('1.29')
            assert page.evaluate('Object.values(state.priceEdits)') == ['129']
            control.fill('1.001')
            assert page.evaluate('dirtyCount()') == 1  # last valid edit plus invalid draft is one field
            assert page.evaluate('Object.values(state.priceEdits)') == ['129']
            control.fill('90071992547409.93')
            page.evaluate('drawPrice()')
            expect(control).to_have_value('90071992547409.93')
            page.evaluate('saveCatalog()')
            assert page.evaluate('window.__requests.filter(r=>r.path==="/api/catalog/save").at(-1).body.prices[0].qty') == '9007199254740993'
            assert page.evaluate('dirtyCount()') == 0
            page.evaluate('drawPrice()')
            expect(control).to_have_value('90071992547409.93')
            for section, family in [('buy', 'buyability'), ('sell', 'sellability')]:
                page.evaluate('''({section,family})=>{
                  state[family+'Edits'][priceItem.key]={[section+'able']:true,cents:100};
                  window.drawGeneric=()=>document.querySelector('#main').replaceChildren(section==='buy'
                    ?buyPriceCell(priceItem,[],document.createElement('div'))
                    :sellPriceCell(priceItem,[],document.createElement('div')));drawGeneric();
                }''', {'section': section, 'family': family})
                generic = page.get_by_role('spinbutton', name=f'{section} price for CONSUMABLE_RUM', exact=True)
                generic.fill('1.001')
                page.evaluate('drawGeneric()')
                expect(generic).to_have_value('1.001')
                assert page.evaluate('dirtyCount()') == 1
                generic.fill('1.29')
                assert page.evaluate(f'state.{family}Edits.CONSUMABLE_RUM.cents') == '129'
                assert page.evaluate('Object.keys(state.moneyDrafts).length') == 0
                generic.fill('1.001')
                page.evaluate('''({section})=>clearCatalogMoneyDrafts(priceItem.key,section)''', {'section': section})
                assert page.evaluate('Object.keys(state.moneyDrafts).length') == 0
                page.evaluate('''family=>{state[family+'Edits']={}}''', family)
            page.evaluate('''()=>{
              priceItem.buy=[];state.buyabilityEdits[priceItem.key]={buyable:true,cents:100};
              document.querySelector('#main').replaceChildren(buyPriceCell(priceItem,[],document.createElement('div')),
                purchaseQuantityCell(priceItem));
            }''')
            page.get_by_role('spinbutton', name='buy price for CONSUMABLE_RUM', exact=True).fill('1.29')
            page.get_by_role('spinbutton', name='Purchase quantity for CONSUMABLE_RUM', exact=True).fill('4')
            page.evaluate('saveCatalog()')
            assert page.evaluate('priceItem.buy') == [
                {'key': 'COST_SHOP_DEFAULT', 'costtype': 'COST_TYPE_PRICE', 'yield': '4',
                 'parts': [{'item': 'CURRENCY_CASH', 'qty': '129'}], 'unlocks': []}
            ]
            page.evaluate('''()=>{
              state.priceEdits['CONSUMABLE_RUM|buy|COST_SHOP_DEFAULT|CURRENCY_CASH']='145';
              state.yieldEdits['CONSUMABLE_RUM|buy|COST_SHOP_DEFAULT']='5';
              state.priceEdits['OTHER|buy|OTHER_COST|CURRENCY_CASH']='999';
              clearCatalogCashPriceEdits(priceItem,'buy');
            }''')
            assert page.evaluate('Object.keys(state.yieldEdits).length') == 0
            assert page.evaluate('Object.keys(state.priceEdits)') == ['OTHER|buy|OTHER_COST|CURRENCY_CASH']
            page.evaluate('state.priceEdits={}')
            page.evaluate('''()=>{state.buyabilityEdits[priceItem.key]={buyable:false}}''')
            page.evaluate('saveCatalog()')
            assert page.evaluate('priceItem.buy') == []
        finally:
            browser.close()
