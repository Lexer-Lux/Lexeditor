"""Production quantity controls retain invalid drafts and guard hidden Save paths."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rdr2_browser_check import document


def test_purchase_bundle_and_carry_raw_drafts_survive_redraw_and_block_all_saves():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 900})
            page.route('**/*', lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            page.evaluate('''()=>{
                window.drawFixture=()=>{
                  document.querySelector('#main').replaceChildren(...[
                    ['yieldEdits','purchase',2,1],['bundleEdits','bundle',3,1],['carryEdits','carry',-1,null]
                  ].map(([store,key,base,minimum])=>catalogQuantityInput({store:state[store],key,base,
                    value:state[store][key]??base,minimum,'aria-label':key})));};
                drawFixture();
                state.settingEdits={fixture:true};
            }''')
            for store, label, initial, invalid in [
                ('yieldEdits', 'purchase', '2', ['1.5', '0', '']),
                ('bundleEdits', 'bundle', '3', ['2.5', '0', '']),
                ('carryEdits', 'carry', '-1', ['-1.5', '']),
            ]:
                control = page.get_by_role('spinbutton', name=label, exact=True)
                for raw in invalid:
                    control.fill(raw)
                    control.blur()
                    assert control.input_value() == raw
                    assert page.evaluate(f'state.{store}["{label}"]') == raw
                    assert not control.evaluate('e=>e.checkValidity()')
                    page.evaluate('drawFixture()')
                    assert control.input_value() == raw
                    # Removing the controls models a hidden record/tab: Save
                    # must validate owned drafts rather than query mounted inputs.
                    page.evaluate("document.querySelector('#main').replaceChildren()")
                    before = page.evaluate('window.__requests.length')
                    assert 'whole quantity' in page.evaluate('''async()=>{
                      try{await saveCatalog();return 'saved'}catch(e){return e.message}}''')
                    page.evaluate('saveAllChanges()')
                    assert page.evaluate('window.__requests.length') == before
                    assert page.evaluate(f'state.{store}["{label}"]') == raw
                    page.evaluate('drawFixture()')
                    control.fill(initial)
                    assert not page.evaluate(f'"{label}" in state.{store}'), control.evaluate('e=>({value:e.value,min:e.min,max:e.max,message:e.validationMessage,html:e.outerHTML})')
                # Positive, exact text is retained without a Number round trip.
                control.fill('9007199254740993')
                assert page.evaluate(f'state.{store}["{label}"]') == '9007199254740993'
                page.evaluate('validateCatalogQuantityDrafts()')
                control.fill(initial)
            assert page.evaluate('Object.keys(state.yieldEdits).length+Object.keys(state.bundleEdits).length+Object.keys(state.carryEdits).length') == 0
            page.evaluate('''()=>{
              const item=state.catalog.items[0];item.buy=[{key:'BUY',yield:2,costtype:'COST_TYPE_PRICE',
                parts:[{item:'CURRENCY_CASH',qty:100}],unlocks:[]}];item.carry=[{slot:'SLOTID_ANY',qty:'-1'}];
              window.callerItem=item;
              window.drawCallers=()=>document.querySelector('#main').replaceChildren(itemRow(item));drawCallers();
            }''')
            purchase = page.get_by_role('spinbutton', name='Purchase quantity for CONSUMABLE_RUM', exact=True)
            carry = page.get_by_role('spinbutton', name='Carry quantity for CONSUMABLE_RUM SLOTID_ANY', exact=True)
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
            from paged_detail import reveal
            for control, store in [(purchase, 'yieldEdits'), (carry, 'carryEdits')]:
                reveal(page, control)
                control.fill('1.5')
                control.blur()
                assert page.evaluate(f'Object.values(state.{store})') == ['1.5']
                page.evaluate('drawCallers()')
                reveal(page, control)
                expect(control).to_have_value('1.5')
                assert not control.evaluate('e=>e.checkValidity()')
                control.fill('2' if store == 'yieldEdits' else '-1')
                assert page.evaluate(f'Object.keys(state.{store}).length') == 0
            key = page.evaluate('''()=>{
              const key=Object.keys(PURCHASE_CONTAINERS)[0],spec=PURCHASE_CONTAINERS[key];
              const container={...callerItem,key};state.catalog.items.push(container,
                {...callerItem,key:spec.target,lootSources:[{file:'loot_table_itemgroups.meta',table:spec.table,min:'3',max:'3'}]});
              window.drawBundle=()=>document.querySelector('#main').replaceChildren(purchaseQuantityCell(container));
              drawBundle();return key;
            }''')
            bundle = page.get_by_role('spinbutton', name=f'Bundle output quantity for {key}', exact=True)
            bundle.fill('1.5')
            bundle.blur()
            assert page.evaluate('Object.values(state.bundleEdits)') == ['1.5']
            page.evaluate('drawBundle()')
            expect(bundle).to_have_value('1.5')
            bundle.fill('3')
            assert page.evaluate('Object.keys(state.bundleEdits).length') == 0
        finally:
            browser.close()
