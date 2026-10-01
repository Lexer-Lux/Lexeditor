"""Unified abilities navigation, distinct GF identities and enemy action saves."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from plugins.ff8.plugin import FF8Session


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-abilities-') as project:
        with FF8Session({'LEXEDITOR_FF8_PROJECT': project}) as session, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1600, 'height': 950})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(session.url)
            page.wait_for_function("typeof state!=='undefined'&&!state.booting", timeout=90000)
            page.wait_for_function("!document.querySelector('.lex-plugin-loading-screen')", timeout=30000)
            page.evaluate("state.activeSource='mine';navigate('abilities')")
            assert set(page.locator('#toolbar [data-subtab]').evaluate_all('nodes=>nodes.map(n=>n.dataset.subtab)')) == {'gfAbilities', 'magic', 'enemyAbilities'}, errors
            assert page.evaluate("abilityCategories.reduce((n,[key])=>n+state.data[key].rows.length,0)") == 116
            page.evaluate("state.selected.abilityMenu=5;navigate('abilityMenu')")
            assert page.evaluate("state.selected.gfAbilities") == 97
            assert page.get_by_label('Type', exact=True).input_value() == 'Menu'
            page.get_by_label('AP to learn', exact=True).fill('31')
            page.get_by_label('AP to learn', exact=True).dispatch_event('input')
            output = Path(tempfile.gettempdir())/'lexeditor-dev'/'abilities-gf.png'
            output.parent.mkdir(exist_ok=True)
            page.screenshot(path=str(output))
            page.locator('#toolbar [data-subtab="magic"]').click()
            assert page.evaluate("state.tab==='abilities'&&state.abilityTab==='magic'")
            page.locator('#toolbar [data-subtab="enemyAbilities"]').click()
            assert page.evaluate("state.data.enemyAbilities.rows.length") == 384
            page.screenshot(path=str(output.with_name('abilities-enemy.png')))
            # Locate a real custom enemy action, follow it, then choose another attack.
            info = page.evaluate("""()=>{
              for(const row of state.data.enemyTables.rows)for(const [tier,entries] of Object.entries(row.tables.abilities)){
                const entry=entries.find(e=>e.type===8&&e.abilityId>0);
                if(entry)return {id:row.id,tier,slot:entry.slot,before:entry.abilityId};
              }
            }""")
            assert info
            page.evaluate("i=>{state.selected.enemies=i.id;state.enemyDetailTab='actions';state.enemyActionTier=i.tier;navigate('enemies')}", info)
            action = page.locator('.enemy-ability-table .lex-column-list-row').nth(info['slot'])
            link = action.locator('[data-hover-target-type="enemyAbilities"]')
            link.click()
            page.wait_for_function("state.abilityTab==='enemyAbilities'&&state.tab==='abilities'")
            page.evaluate("i=>{state.selected.enemies=i.id;navigate('enemies')}", info)
            action.get_by_role('button', name='Choose enemy ability', exact=True).click()
            page.wait_for_function("state.abilityTab==='enemyAbilities'&&state.tab==='abilities'")
            candidate = page.locator('.ff8-record-list .lex-column-list-row').filter(has=page.locator('[data-column-key="name"]')).first
            chosen = int(candidate.get_attribute('data-key'))
            candidate.hover()
            page.mouse.down()
            page.wait_for_timeout(900)
            page.mouse.up()
            page.wait_for_function("state.tab==='enemies'")
            assert page.evaluate("i=>state.data.enemyTables.rows.find(r=>r.id===i.id).tables.abilities[i.tier][i.slot].abilityId", info) == chosen
            page.evaluate("state.selected.enemyAbilities=2;navigate('enemyAbilities')")
            # Set through the actual field control, then save and read the endpoint.
            field = page.get_by_label('Attack power', exact=True)
            field.fill('73')
            field.dispatch_event('input')
            page.evaluate("saveAll()")
            page.wait_for_function("dirtyCount()===0", timeout=90000)
            stored = page.request.get(session.url.rstrip('/')+'/api/kernel?section=4&dataset=current').json()
            assert next(f['value'] for f in stored['rows'][2]['fields'] if f['field']=='attack_power') == 73
            menu = page.request.get(session.url.rstrip('/')+'/api/kernel?section=18&dataset=current').json()
            assert next(f['value'] for f in menu['rows'][5]['fields'] if f['label']=='AP to learn') == 31
            tables = page.request.get(session.url.rstrip('/')+'/api/enemy-tables?dataset=current').json()
            assert next(r for r in tables['rows'] if r['id']==info['id'])['tables']['abilities'][info['tier']][info['slot']]['abilityId'] == chosen
            assert not errors, errors
            browser.close()
            print('Unified abilities and enemy action round-trip passed.')


if __name__ == '__main__':
    main()
