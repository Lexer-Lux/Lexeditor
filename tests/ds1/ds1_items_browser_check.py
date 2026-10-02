"""Render all eight item lists and edit/save/reload copies, never game files."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument, SUBTABS
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output: output.mkdir(parents=True, exist_ok=True)
    real_root = os.environ.get('LEXEDITOR_DS1_ACCEPTANCE_ROOT')
    original_path = Path(real_root) / RELATIVE if real_root else None
    raw = original_path.read_bytes() if original_path else make_archive()
    source_hash = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-ui-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors, changes, counts = [], [], {}
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    assert page.locator('[data-subtab]').evaluate_all('nodes=>nodes.map(n=>n.dataset.subtab)') == [t[0] for t in SUBTABS]
                    for tab, _, _ in SUBTABS:
                        page.locator(f'[data-subtab="{tab}"]').click()
                        page.wait_for_function('(tab)=>state.sub===tab && state.row && !state.error', arg=tab)
                        page.wait_for_timeout(200)
                        counts[tab] = page.evaluate('state.rows.length')
                        assert counts[tab] > 0
                        assert page.locator('.lex-column-list .lex-list-row').count() > 0
                        control = page.locator('input[data-field-key][type="number"]:visible').first
                        control.wait_for()
                        field = control.get_attribute('data-field-key')
                        old = float(control.input_value().replace(',', ''))
                        low, high = float(control.get_attribute('min')), float(control.get_attribute('max'))
                        value = min(max(old + 1, low), high)
                        if value == old: value = max(low, old - 1)
                        assert value != old
                        identity = page.evaluate('({table:state.row.table,id:state.row.id})')
                        control.fill(str(int(value)) if value.is_integer() else str(value))
                        control.press('Tab')
                        page.wait_for_function('state.pending===0 && state.dirty>0')
                        row = request_json(session.url + f"api/row?table={identity['table']}&id={identity['id']}")['row']
                        assert next(f['value'] for f in row['fields'] if f['key'] == field) == value
                        changes.append((identity['table'], identity['id'], field, value))
                        if output: page.screenshot(path=str(output / f'{tab}.png'))
                    assert page.locator('select[data-field-key]').count() > 0
                    assert page.locator('input[type="checkbox"][data-field-key]').count() > 0
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty===0 && state.pending===0')
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    reopened = ItemDocument((mod / RELATIVE).read_bytes())
                    for table, row_id, field, value in changes:
                        assert reopened.value(table, row_id, field) == value
                    page.set_viewport_size({'width': 1000, 'height': 700})
                    page.locator('[data-subtab="weapons"]').click()
                    page.wait_for_timeout(500)
                    assert page.locator('.ds1-records').is_visible()
                    expected = set(page.evaluate('state.row.fields.filter(f=>f.editable).map(f=>f.key)'))
                    seen = set()
                    for _ in range(30):
                        fields = page.locator('.lex-tweaks-paged [data-field-key]:visible')
                        for index in range(fields.count()):
                            field = fields.nth(index)
                            field.scroll_into_view_if_needed()
                            box = field.bounding_box()
                            assert box['y'] >= 0 and box['y'] + box['height'] <= 700, box
                            seen.add(field.get_attribute('data-field-key'))
                        pager = page.locator('.lex-tweaks-pages')
                        box = pager.bounding_box()
                        assert box['height'] > 0 and box['y'] + box['height'] <= 700, box
                        next_page = pager.get_by_role('button', name='Next page', exact=True)
                        if not next_page.is_enabled(): break
                        next_page.click()
                    assert seen == expected, sorted(expected - seen)
                    page.locator('.lex-tweaks-pages').get_by_role('button', name='First page', exact=True).click()
                    previous = page.evaluate('state.selected')
                    list_next = page.locator('.lex-pager:not(.lex-pager-inline)').get_by_role('button', name='Next page', exact=True)
                    if list_next.count() and list_next.is_enabled():
                        list_next.click()
                        page.wait_for_function('(previous)=>state.selected!==previous && state.row && key(state.row)===state.selected', arg=previous)
                    search = page.get_by_role('searchbox', name='Search items')
                    search.fill('Dagger' if real_root else '100')
                    page.wait_for_function('state.row && key(state.row)===state.selected')
                    assert page.locator('.lex-column-list .lex-list-row').count() > 0
                    search.fill('')
                    page.wait_for_function('state.row && key(state.row)===state.selected')
                    if output: page.screenshot(path=str(output / 'small.png'))
                    assert not errors, errors
                    session.stop()
                    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                                          'LEXEDITOR_NO_MOD': '1', 'LEXEDITOR_MOD_READ_ONLY': '1'})
                    session.start()
                    vanilla = browser.new_page(viewport={'width': 1280, 'height': 800})
                    vanilla.on('pageerror', lambda error: errors.append(str(error)))
                    vanilla.add_init_script('''window.pywebview={api:new Proxy({
                      mod_projects:async()=>({pluginId:'ds1',current:'Vanilla',canCreate:true,
                        projects:[{path:'Vanilla',name:'Vanilla',valid:true,current:true,noMod:true,readOnly:true}]}),
                      lexeditor_settings:async()=>({}),window_state:async()=>({maximized:false}),
                      theme_sounds:async()=>({rows:[]})
                    },{get:(t,k)=>t[k]||(async()=>null)})};''')
                    vanilla.goto(session.url + '?lexNoMod=1')
                    vanilla.wait_for_selector('body[data-ds1-ready="true"]')
                    vanilla.wait_for_function('document.documentElement.dataset.lexProjectReadonly==="true"')
                    assert vanilla.locator('#global-save').is_disabled()
                    assert 'Vanilla' in vanilla.locator('.lex-project-control').inner_text()
                    # The ready marker means data loaded, not that the shared
                    # minimum-duration loading curtain has stopped intercepting clicks.
                    vanilla.wait_for_selector('.lex-plugin-loading-screen', state='detached')
                    vanilla.evaluate('() => document.fonts.ready')
                    # The field is disabled now, matching every other plugin's
                    # read-only look. A real mouse click at its position still
                    # reaches the shared shell's document-level edit-attempt
                    # gate, so click by position rather than through
                    # Playwright's own actionability check, which refuses to
                    # drive a disabled element at all.
                    field_box = vanilla.locator('input[data-field-key]:visible').first.bounding_box()
                    vanilla.mouse.click(field_box['x'] + field_box['width'] / 2, field_box['y'] + field_box['height'] / 2)
                    dialog = vanilla.locator('.lex-dialog')
                    dialog.wait_for()
                    assert 'Create a mod' in dialog.inner_text()
                    dialog.get_by_role('button', name='Cancel', exact=False).first.click()
                    assert request_json(session.url + 'api/state')['dirtyCount'] == 0
                    vanilla_row = request_json(session.url + 'api/row?table=EquipParamGoods&id=100')['row']
                    first_change = changes[0]
                    field_value = next(f['value'] for f in vanilla_row['fields'] if f['key'] == first_change[2])
                    assert field_value == ItemDocument(raw).value('EquipParamGoods', 100, first_change[2])
                    if output: vanilla.screenshot(path=str(output / 'vanilla.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
        assert hashlib.sha256((game / RELATIVE).read_bytes()).hexdigest() == source_hash
    if original_path:
        assert hashlib.sha256(original_path.read_bytes()).hexdigest() == source_hash
    print(json.dumps({'source': 'installed archive copy' if real_root else 'synthetic fixture',
                      'counts': counts, 'uiEditsSavedAndReloaded': len(changes), 'browserErrors': errors,
                      'originalUnchanged': True}, indent=2))


if __name__ == '__main__':
    main()
