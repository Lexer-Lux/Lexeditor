"""Production RDR2 crafting and loot links with synthetic catalog records."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rdr2_browser_check import document
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={'width':1400,'height':900})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('**/*',lambda route:route.abort())
            page.set_content(document().replace('<head>','<head><base href="https://lexeditor.test/">',1))
            page.wait_for_function("!state.booting&&state.catalog?.items?.length")
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            page.evaluate("""()=>{
              state.customCrafting.vanilla=[{recipe_id:'TEST_RECIPE',station:'CUSTOM_ANY',
                output_item:'CONSUMABLE_BRANDY',output_quantity:1,ingredients:[{item:'CONSUMABLE_RUM',quantity:1}]}];
              const file='loot_table_itemgroups.meta';
              for(const dataset of Object.values(state.config.datasets))dataset.scopes=[];
              state.config.datasets.mine.lootFiles=[file];
              const tables=[{key:'DIRECT',type:'AggregateDrop',entries:[{name:'CONSUMABLE_RUM',type:'Item',rate:1,min:1,max:1}]},
                {key:'PARENT',type:'AggregateDrop',entries:[{name:'DIRECT',type:'Table',rate:1,min:1,max:1}]}];
              state.loot[file]={tables};state.lootUsage={tables:{}};
              window.__responses['/api/loot']={tables};
              window.showFixtureLoot=async(key,alt=false)=>{
                window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{hoverableAltClick:alt,developerMode:false,viewPreferences:{}}}));
                state.lootFile=file;state.tab='loot';state.filters.lootSel=key;state.filters.lootQ=key;state.filters.lootPage=0;
                await renderLoot();
              };
              window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{hoverableAltClick:false}}));
              navigate('crafting');
            }""")
            item_selector='.lex-hoverable[data-hover-target-type="rdr2-item"][data-hover-target-id="CONSUMABLE_RUM"]'
            page.locator('#main .lex-detail-panel '+item_selector).click()
            page.wait_for_function("state.tab==='items'&&state.filters.itemSel==='CONSUMABLE_RUM'")
            page.evaluate("showFixtureLoot('DIRECT')")
            link=page.locator('#main '+item_selector)
            link.hover()
            assert link.evaluate("n=>getComputedStyle(n).textDecorationLine")=='underline'
            link.click()
            page.wait_for_function("state.tab==='items'&&state.filters.itemSel==='CONSUMABLE_RUM'")
            page.evaluate("showFixtureLoot('DIRECT',true)")
            link.click()
            assert page.evaluate("state.tab==='loot'&&state.filters.lootSel==='DIRECT'")
            link.click(modifiers=['Alt'])
            page.wait_for_function("state.tab==='items'&&state.filters.itemSel==='CONSUMABLE_RUM'")
            page.evaluate("showFixtureLoot('PARENT')")
            page.locator('.lex-hoverable[data-hover-target-type="rdr2-loot-table"]').first.click()
            page.wait_for_function("state.tab==='loot'&&state.lootFile==='loot_table_itemgroups.meta'&&state.filters.lootSel==='DIRECT'")
            assert not errors,errors
            print('Craft ingredient, direct loot, Alt-click preference and nested table links passed.')
        finally:
            browser.close()


if __name__=='__main__':
    main()
