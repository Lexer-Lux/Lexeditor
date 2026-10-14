"""Rendered monster stat, behavior and AI edits against synthetic or copied installed data."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1.formats import BEHAVIOR_EDITABLE, ENEMY_SUBTABS, THINK_EDITABLE, ItemDocument
from plugins.ds1.monsters import NPC_FIELDS
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output: output.mkdir(parents=True, exist_ok=True)
    real = os.environ.get('LEXEDITOR_DS1_ACCEPTANCE_ROOT')
    source = Path(real) / RELATIVE if real else None
    raw = source.read_bytes() if source else make_archive()
    original_hash = hashlib.sha256(raw).hexdigest()
    changes = {'def_phys': 101, 'def_slash': -10, 'resist_poison': 275, 'physGuardCutRate': 33.5, 'dropType': 1}
    errors = []
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-monsters-') as temporary:
        game, mod = Path(temporary) / 'game', Path(temporary) / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        mod.mkdir(); (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1100, 'height': 800})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    def monsters():
                        page.locator('[data-tab="enemies"]').click()
                        page.wait_for_function('state.tab==="enemies" && state.row?.table==="NpcParam" && !state.error')
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    monsters()
                    tabs = ENEMY_SUBTABS + (('model', 'Model', 'EnemyModel'),)
                    assert page.locator('#main > .lex-stack > .lex-subtab-bar [data-subtab]').evaluate_all('n=>n.map(x=>x.dataset.subtab)') == [t[0] for t in sorted(tabs, key=lambda entry: entry[1].lower())]
                    # Every section is a tab; Attacks joins them.
                    assert page.locator('.lex-tabbed-panel [data-subtab]').evaluate_all('n=>n.map(x=>x.dataset.subtab)') == [
                        'attacks', 'basics', 'blocking', 'defense', 'effects-references', 'status-buildup-resistance',
                        'value-rewards', 'weaknesses']
                    assert page.evaluate('state.monsterTab') == 'basics'
                    page.locator('.lex-tabbed-panel [data-subtab="defense"]').click()
                    page.wait_for_function('state.monsterTab==="defense"')
                    assert page.evaluate('state.row.id') == 120000
                    count = page.evaluate('state.rows.length')
                    assert count == (335 if real else 2)
                    expected = set(page.evaluate('state.row.fields.map(f=>f.key)'))
                    assert expected == set(NPC_FIELDS) | {'effectiveHp'}
                    units = page.evaluate("""() => {
                        const out = {};
                        for (const key of ['weakPartsDamageRate', 'partsDamageRate1', 'partsDamageRate8']) {
                            const input = document.querySelector(`input[data-field-key="${key}"]`);
                            const field = input && input.closest('.lex-detail-field');
                            const unit = field && field.querySelector('.lex-unit');
                            const label = field && field.querySelector('.lex-detail-field-label-text');
                            out[key] = [unit && unit.textContent,
                                        unit && unit.classList.contains('lex-unit-multiplier'),
                                        label && label.textContent];
                        }
                        return out;
                    }""")
                    assert units['weakPartsDamageRate'] == ['\u00d7', True, 'Damage taken: weak point'], units
                    assert units['partsDamageRate1'] == ['\u00d7', True, 'Damage taken: Part 1'], units
                    assert units['partsDamageRate8'] == ['\u00d7', True, 'Damage taken: Part 8'], units
                    page.locator('.lex-tabbed-panel [data-subtab="blocking"]').click()
                    page.wait_for_function('state.monsterTab==="blocking"')
                    assert page.locator('input[data-field-key="staminaGuardDef"]:visible').count() == 1
                    assert page.locator('input[data-field-key="hp"]:visible').count() == 0
                    page.locator('.lex-tabbed-panel [data-subtab="basics"]').click()
                    page.wait_for_function('state.monsterTab==="basics"')
                    stamina = page.evaluate("""() => {
                        const input = document.querySelector('input[data-field-key="staminaRecoverBaseVel"]');
                        const field = input && input.closest('.lex-detail-field');
                        const unit = field && field.querySelector('.lex-unit');
                        const label = field && field.querySelector('.lex-detail-field-label-text');
                        return [unit && unit.textContent, label && label.textContent];
                    }""")
                    assert stamina == ['stamina/second', 'Stamina recovery'], stamina
                    seen, edited = set(), set()
                    saw_effective = False
                    tab_ids = page.locator('.lex-tabbed-panel [data-subtab]').evaluate_all('n=>n.map(x=>x.dataset.subtab)')
                    for tab_id in tab_ids:
                        page.locator(f'.lex-tabbed-panel [data-subtab="{tab_id}"]').click()
                        page.wait_for_function(f'state.monsterTab==="{tab_id}"')
                        for index in range(12):
                            if page.locator('input[aria-label="Effective HP"]:disabled').count():
                                saw_effective = True
                            fields = page.locator('input[data-field-key]:visible')
                            for i in range(fields.count()):
                                field = fields.nth(i)
                                key = field.get_attribute('data-field-key')
                                seen.add(key)
                                # The weaknesses (Divine, Occult, Abyssal) are flags.
                                kind = field.get_attribute('type')
                                assert kind in ('number', 'checkbox', 'text'), (key, kind)
                                if kind == 'text':
                                    # Grouped thousands: the bounds stay on the control.
                                    assert field.get_attribute('inputmode') in ('numeric', 'decimal'), key
                                if kind in ('number', 'text'):
                                    assert field.get_attribute('min') is not None and field.get_attribute('max') is not None
                                field.scroll_into_view_if_needed()
                                box = field.bounding_box()
                                assert 0 <= box['y'] and box['y'] + box['height'] <= 800
                                if key in changes:
                                    field.fill(str(changes[key])); field.press('Tab')
                                    page.wait_for_function('(x)=>state.pending===0 && state.row.fields.find(f=>f.key===x.key).value===x.value',
                                                           arg={'key': key, 'value': changes[key]})
                                    edited.add(key)
                            # Fresh handle per control: a commit re-renders the pane.
                            options = page.locator('select[data-field-key]:visible')
                            for key in options.evaluate_all('nodes=>nodes.map(n=>n.dataset.fieldKey)'):
                                select = page.locator(f'select[data-field-key="{key}"]:visible')
                                seen.add(key)
                                select.scroll_into_view_if_needed()
                                page.wait_for_function('(key)=>document.querySelector("select[data-field-key="+key+"]").options.length>1', arg=key)
                                assert select.locator('option').count() > 1, key
                                if key in changes:
                                    select.select_option(str(changes[key]))
                                    page.wait_for_function('(x)=>state.pending===0 && state.row.fields.find(f=>f.key===x.key).value===x.value',
                                                           arg={'key': key, 'value': changes[key]})
                                    edited.add(key)
                            if output: page.screenshot(path=str(output / f'monsters-{tab_id}-{index}.png'))
                            following = page.locator('.lex-tweaks-pages').get_by_role('button', name='Next page', exact=True)
                            if not following.count() or not following.is_enabled(): break
                            following.click()
                    assert seen == expected - {'effectiveHp'} and edited == changes.keys()
                    assert saw_effective
                    page.locator('.lex-tabbed-panel [data-subtab="basics"]').click()
                    page.wait_for_function('state.monsterTab==="basics"')
                    first = page.locator('.lex-tweaks-pages').get_by_role('button', name='First page', exact=True)
                    if first.count() and first.is_enabled():
                        first.click()
                    for _ in range(12):
                        if page.locator('.lex-detail-field[data-lex-layout-field="hp"] button.lex-column-pin:visible').count():
                            break
                        page.locator('.lex-tweaks-pages').get_by_role('button', name='Next page', exact=True).click()
                    else:
                        raise AssertionError('hp field never shown')
                    page.evaluate('document.querySelector(".lex-detail-panel").dataset.pinProbe = "1"')
                    page.locator('.lex-detail-field[data-lex-layout-field="hp"] button.lex-column-pin').click()
                    page.locator('.lex-detail-field[data-lex-layout-field="mp"] button.lex-column-pin').click()
                    page.wait_for_selector('.lex-column-list-head-cell[data-column-key="pin:mp"]')
                    assert page.evaluate('document.querySelector(".lex-detail-panel").dataset.pinProbe') == "1"
                    order = page.locator('.lex-column-list-head-cell[data-column-key^="pin:"]').evaluate_all("cells=>cells.map(c=>c.dataset.columnKey)")
                    assert order == ["pin:hp", "pin:mp"], order
                    head = page.locator('.lex-column-list-head-cell[data-column-key="pin:hp"]')
                    tail = page.locator('.lex-column-list-head-cell[data-column-key="pin:mp"]')
                    box, goal = head.bounding_box(), tail.bounding_box()
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    page.mouse.down()
                    page.mouse.move(goal["x"] + goal["width"] / 2, goal["y"] + goal["height"] / 2, steps=8)
                    page.mouse.up()
                    page.wait_for_function('JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k=>k.startsWith("lexeditor:pins:"))))[0].key==="mp"')
                    order = page.locator('.lex-column-list-head-cell[data-column-key^="pin:"]').evaluate_all("cells=>cells.map(c=>c.dataset.columnKey)")
                    assert order == ["pin:mp", "pin:hp"], order
                    stored = page.evaluate('JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k=>k.startsWith("lexeditor:pins:"))))')
                    assert [entry["key"] for entry in stored] == ["mp", "hp"], stored
                    page.locator('.lex-column-list-row[data-key]').first.click()
                    page.wait_for_function('state.pending===0 && state.row && (state.row.table+":"+state.row.id)===state.selected')
                    page.evaluate('document.querySelector(".lex-detail-panel").dataset.pinProbe = "1"')
                    selected = page.evaluate('state.selected')
                    cell = page.locator(f'.lex-column-list-row[data-key="{selected}"] .lex-column-list-cell[data-column-key="pin:hp"]')
                    cell.dblclick()
                    editor = cell.locator("input")
                    editor.fill('777')
                    editor.press('Enter')
                    page.wait_for_function('state.pending===0 && state.rows.find(r=>r.table==="NpcParam"&&r.id===state.selected.split(":")[1]*1).values.hp===777')
                    assert "777" in cell.inner_text()
                    assert page.locator('.lex-detail-field[data-lex-layout-field="hp"] input').input_value() == "777"
                    assert page.evaluate('state.row.fields.find(f=>f.key==="hp").value') == 777
                    page.locator('.lex-detail-field[data-lex-layout-field="hp"] button.lex-column-pin').click()
                    page.locator('.lex-detail-field[data-lex-layout-field="mp"] button.lex-column-pin').click()
                    page.wait_for_selector('.lex-column-list-head-cell[data-column-key^="pin:"]', state="detached")
                    assert page.evaluate('document.querySelector(".lex-detail-panel").dataset.pinProbe') == "1"
                    brains = []
                    for sub, table, allowed in [('behaviors', 'BehaviorParam', BEHAVIOR_EDITABLE), ('ai', 'NpcThinkParam', THINK_EDITABLE)]:
                        page.locator(f'[data-subtab="{sub}"]').click()
                        page.wait_for_function('(want)=>state.sub===want.sub && state.rows.length>0 && state.row && state.row.table===want.table && !state.error', arg={'sub': sub, 'table': table})
                        assert {field['key'] for field in page.evaluate('state.row.fields')} == set(allowed)
                        control = page.locator('input[data-field-key][type="number"][min]:visible').first
                        if not control.count():
                            control = page.locator('input[data-field-key][type="text"][min]:visible').first
                        key = control.get_attribute('data-field-key')
                        old = float(control.input_value() or 0)
                        low, high = float(control.get_attribute('min')), float(control.get_attribute('max'))
                        value = min(max(old + 1, low), high)
                        if value == old: value = max(low, old - 1)
                        identity = page.evaluate('state.row.id')
                        control.fill(str(int(value)) if float(value).is_integer() else str(value))
                        control.press('Tab')
                        page.wait_for_function('(x)=>state.pending===0 && state.row.fields.find(f=>f.key===x.key).value===x.value', arg={'key': key, 'value': value})
                        brains.append((table, identity, key, value))
                        if output: page.screenshot(path=str(output / f'monsters-{sub}.png'))
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty===0 && state.pending===0')
                    page.reload(); page.wait_for_selector('body[data-ds1-ready="true"]'); monsters()
                    reopened = ItemDocument((mod / RELATIVE).read_bytes())
                    for key, value in changes.items(): assert reopened.value('NpcParam', 120000, key) == value
                    for table, identity, key, value in brains: assert reopened.value(table, identity, key) == value
                    page.locator('[data-tab="items"]').click()
                    page.wait_for_function('state.tab==="items" && state.row?.table==="EquipParamGoods"')
                    assert page.locator('#main > .lex-stack > .lex-subtab-bar [data-subtab]').count() == 9
                    monsters()
                    page.set_viewport_size({'width': 1000, 'height': 700})
                    search = page.get_by_role('searchbox', name='Search monsters')
                    search.fill('Small Rat')
                    page.wait_for_function('state.row?.id===120100')
                    page.wait_for_timeout(350)  # Let the shared label fitter finish after resize/search.
                    if output: page.screenshot(path=str(output / 'monsters-small.png'))
                    # Public API must enforce the same narrow boundary as the UI.
                    for identity, key in [(120000, 'npcType'), (223000, 'def_phys')]:
                        try:
                            request_json(session.url + 'api/edit', {'table':'NpcParam','id':identity,'field':key,'value':1})
                            raise AssertionError('Out-of-scope field/record accepted')
                        except HTTPError as error: assert error.code == 400
                    session.stop()
                    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                                          'LEXEDITOR_NO_MOD':'1', 'LEXEDITOR_MOD_READ_ONLY':'1'})
                    session.start()
                    vanilla = browser.new_page(viewport={'width':1100,'height':800})
                    vanilla.on('pageerror', lambda error: errors.append(str(error)))
                    vanilla.add_init_script('''window.pywebview={api:new Proxy({
                      mod_projects:async()=>({current:'Vanilla',canCreate:true,projects:[
                        {path:'Vanilla',name:'Vanilla',valid:true,current:true,noMod:true,readOnly:true}]}),
                      lexeditor_settings:async()=>({}),window_state:async()=>({maximized:false}),theme_sounds:async()=>({rows:[]})
                    },{get:(t,k)=>t[k]||(async()=>null)})};''')
                    vanilla.goto(session.url + '?lexNoMod=1')
                    vanilla.wait_for_selector('body[data-ds1-ready="true"]')
                    vanilla.locator('[data-tab="enemies"]').click()
                    vanilla.wait_for_function('state.row?.table==="NpcParam"')
                    vanilla.wait_for_selector('.lex-plugin-loading-screen', state='detached')
                    assert vanilla.locator('#global-save').is_disabled()
                    # The field is disabled now, matching every other plugin's
                    # read-only look; a real click still reaches the shared
                    # shell's edit-attempt gate, so force this scripted one
                    # past Playwright's own actionability check for it.
                    target = vanilla.locator('input[data-field-key="def_phys"]:visible')
                    if not target.count():
                        target = vanilla.locator('[data-field-key]:visible').first
                    target.click(force=True)
                    vanilla.get_by_role('button', name='Create a mod', exact=True).wait_for()
                    vanilla.get_by_role('button', name='Cancel', exact=True).click()
                    assert request_json(session.url + 'api/state')['dirtyCount'] == 0
                    assert not errors, errors
                finally: browser.close()
        finally: session.stop()
        assert hashlib.sha256((game / RELATIVE).read_bytes()).hexdigest() == original_hash
    if source: assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    print(json.dumps({'monsters':count,'statFields':len(expected),'uiEditsSavedAndReloaded':len(edited),'brainsEdits':len(brains),
                      'vanillaReadOnly':True,'originalUnchanged':True,'browserErrors':errors}))


if __name__ == '__main__': main()
