"""Exercise the RDR2 shop picker through the shared table component."""
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
            page.evaluate("""async()=>{
              __responses['/api/shops']={shops:[{type:'ST_GENERAL',items:[]},{type:'ST_GUNSMITH',items:[]}]};
              __responses['/api/shop-buyers']={available:true,shops:['ST_GENERAL','ST_GUNSMITH'],vanillaBuyers:{}};
              state.tab='shops';await renderShops();
            }""")
            picker = page.locator('.lex-column-list').filter(has=page.get_by_role('columnheader', name='2 Shops'))
            rows = picker.locator('.lex-list-row')
            expect(rows).to_have_count(2)
            expect(rows.first).to_contain_text('0 listings')
            page.evaluate("""()=>{
              state.filters.shopBuyQ='RUM';state.filters.shopSellQ='RUM';
              state.filters.shopSellCategory='old';state.filters.shopSellSubcategory='old';
              state.filters['shop-buys-page']=8;state.filters['shop-sells-page']=9;
            }""")
            picker.locator('[data-key="ST_GUNSMITH"]').click()
            expect(picker.locator('[data-key="ST_GUNSMITH"]')).to_have_attribute('aria-selected', 'true')
            assert page.evaluate("""()=>({
              selected:state.filters.shopType,category:state.filters.shopSellCategory,
              subcategory:state.filters.shopSellSubcategory,
              buyPage:state.filters['shop-buys-page'],sellPage:state.filters['shop-sells-page']
            })""") == {'selected':'ST_GUNSMITH','category':'','subcategory':'','buyPage':0,'sellPage':0}
            expect(picker.locator('[data-key="ST_GENERAL"]')).to_have_attribute('aria-selected', 'false')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert not errors, errors
        finally:
            browser.close()
    print('PASS: shared shop picker count, listings, selection, and category/page resets')


if __name__ == '__main__':
    main()
