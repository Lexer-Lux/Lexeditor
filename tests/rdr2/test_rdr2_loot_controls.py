"""Production loot controls retain invalid drafts, save type and protect readonly rows."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rdr2_browser_check import document


def test_loot_drafts_save_type_exact_quantities_and_readonly_controls(tmp_path):
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 900})
            page.route('**/*', lambda route: route.abort())
            page.set_content(document().replace('<head>', '<head><base href="https://lexeditor.test/">', 1))
            page.wait_for_function('!state.booting&&state.catalog?.items?.length')
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')")
            page.evaluate('''()=>{
              const file='loot_table_itemgroups.meta';window.lootFileFixture=file;
              window.lootTableFixture={key:'FIXTURE',type:'AggregateDrop',entries:[{name:'CONSUMABLE_RUM',type:'Item',rate:'0.25',min:'1',max:'2'}]};
              state.lootFile=file;state.config.datasets.mine.lootFiles=[file];
              for(const info of Object.values(state.config.datasets))info.scopes=[];
              state.loot={[file]:{tables:[lootTableFixture]}};state.store.mine.loot=state.loot;
              state.lootUsage={tables:{}};state.lootDirty={};
              window.__responses['/api/loot/'+file+'/save']={saved:1};
              window.drawLoot=()=>document.querySelector('#main').replaceChildren(lootDetail(lootTableFixture,file));drawLoot();
            }''')
            for label, raw in [('Min', '1.5'), ('Max', '1.5'), ('Rate', '-1')]:
                control = page.get_by_role('spinbutton', name=label, exact=True)
                control.fill(raw)
                control.blur()
                expect(control).to_have_value(raw)
                assert not control.evaluate('e=>e.checkValidity()')
                page.evaluate('drawLoot()')
                expect(page.get_by_role('spinbutton', name=label, exact=True)).to_have_value(raw)
                before = page.evaluate('window.__requests.length')
                failure = page.evaluate("async()=>{try{await saveLoot();return ''}catch(e){return e.message}}")
                assert failure
                assert page.evaluate('window.__requests.length') == before
                page.evaluate("()=>{lootTableFixture.entries[0]={name:'CONSUMABLE_RUM',type:'Item',rate:'0.25',min:'1',max:'2'};drawLoot()}")
            page.get_by_role('spinbutton', name='Min', exact=True).fill('-9007199254740993')
            page.get_by_role('spinbutton', name='Max', exact=True).fill('9007199254740995')
            page.get_by_role('combobox', name='Drop type', exact=True).select_option('ContinuousLinearDrop')
            page.wait_for_function("lootTableFixture.type==='ContinuousLinearDrop'")
            page.evaluate('drawLoot()')
            page.evaluate('saveLoot()')
            page.wait_for_function("window.__requests.some(r=>r.path==='/api/loot/'+lootFileFixture+'/save')")
            posted = page.evaluate("window.__requests.find(r=>r.path==='/api/loot/'+lootFileFixture+'/save').body.edits[0]")
            assert posted['type'] == 'ContinuousLinearDrop'
            assert posted['entries'][0]['min'] == '-9007199254740993'
            assert posted['entries'][0]['max'] == '9007199254740995'
            page.evaluate('''()=>{lootTableFixture.readonly=true;
              state.store.vanilla.loot={[lootFileFixture]:{tables:[{...lootTableFixture,type:'AggregateDrop',entries:[{name:'CONSUMABLE_RUM',type:'Item',rate:'1',min:'1',max:'2'}]}]}};
              drawLoot()}''')
            for label in ['Rate', 'Min', 'Max']:
                expect(page.get_by_role('spinbutton', name=label, exact=True)).to_be_disabled()
            expect(page.get_by_role('combobox', name='Drop type', exact=True)).to_be_disabled()
            expect(page.get_by_role('button', name='Remove entry', exact=True)).to_be_disabled()
            expect(page.get_by_role('button', name='Add a catalog item directly to this table', exact=True)).to_be_disabled()
            assert page.locator('.lex-reference-value').count() > 0
            assert page.locator('.lex-source-control .lex-reference-value').evaluate_all('buttons=>buttons.every(b=>b.disabled)')
            page.screenshot(path=str(tmp_path / 'readonly-loot.png'), full_page=True)
            page.evaluate("()=>{lootTableFixture.type='UNKNOWN_DROP';lootTableFixture.entries[0].rate='NaN';drawLoot()}")
            expect(page.get_by_role('textbox', name='Drop type', exact=True)).to_have_value('UNKNOWN_DROP')
            expect(page.get_by_role('textbox', name='Rate', exact=True)).to_have_value('NaN')
            expect(page.get_by_role('textbox', name='Rate', exact=True)).to_be_disabled()
        finally:
            browser.close()
