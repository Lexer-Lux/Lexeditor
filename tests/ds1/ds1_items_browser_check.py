"""Render all nine item lists and edit/save/reload copies, never game files."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0,str(ROOT / 'tests' / 'shared'))
from paged_detail import reveal
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
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
        # Item names live in the game's text archive, beside the parameters.
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes((Path(real_root) / texts.RELATIVE).read_bytes() if real_root else make_text_archive())
        # Menu labels live in the game's menu archive, beside the item text.
        (game / texts.MENU_RELATIVE).write_bytes((Path(real_root) / texts.MENU_RELATIVE).read_bytes() if real_root else make_menu_archive())
        if real_root:
            # Item pictures need the installed menu sheets and catalog.
            for entry in (Path(real_root) / 'menu').glob('menu*.tpf.dcx'):
                (game / 'menu' / entry.name).parent.mkdir(parents=True, exist_ok=True)
                (game / 'menu' / entry.name).write_bytes(entry.read_bytes())
            layout = Path(real_root) / 'menu' / 'menu.drb'
            if layout.is_file():
                (game / 'menu' / 'menu.drb').write_bytes(layout.read_bytes())
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
                    # Subtabs follow the shared alphabetical rule, not declaration order.
                    expected = [key for key, _label, _table in sorted(
                        SUBTABS + (('ashes-of-war','Ashes of War','WeaponSkill'),),
                        key=lambda entry: entry[1].lower())]
                    # The strip only: record details carry panel tabs with the
                    # same marker now (an "upgrades" Upgrades tab included).
                    strip = '.lex-subtab-bar:not(.lex-tabbed-panel .lex-subtab-bar) [data-subtab]'
                    assert page.locator(strip).evaluate_all('nodes=>nodes.map(n=>n.dataset.subtab)') == expected
                    for tab, _, _ in SUBTABS:
                        page.locator(strip + f'[data-subtab="{tab}"]').click()
                        page.wait_for_function('(tab)=>state.sub===tab && state.row && !state.error', arg=tab)
                        # The first render of a big list lags its rows,
                        # so the wait names DOM rows, not a fixed pause.
                        page.wait_for_function("() => document.querySelectorAll('.lex-column-list .lex-list-row').length > 0")
                        counts[tab] = page.evaluate('state.rows.length')
                        assert counts[tab] > 0
                        cells = page.locator('.lex-column-list .lex-list-row').first.evaluate(
                            'row=>row.children.length')
                        # No fixed icon column: thumbnails arrive through the
                        # header preview's pin like any other column.
                        assert cells == 1, (tab, cells)
                        if real_root:
                            page.locator('.lex-detail-panel-icon > .lex-column-pin').click(force=True)
                            page.wait_for_timeout(400)
                            done = ("()=>[...document.querySelectorAll("
                                + "'.lex-column-list .lex-list-row img')].every(i=>i.complete)")
                            page.wait_for_function(done)
                            loaded = page.locator('.lex-column-list .lex-list-row img').evaluate_all(
                                'imgs=>imgs.filter(img=>img.naturalWidth>0).length')
                            assert loaded > 0, (tab, loaded)
                            page.locator('.lex-detail-panel-icon > .lex-column-pin.pinned').click(force=True)
                            page.wait_for_timeout(400)
                        panel_tabs = page.locator('.lex-tabbed-panel [data-subtab]')
                        if panel_tabs.count():
                            for index in range(panel_tabs.count()):
                                if page.locator('input[data-field-key][type="number"]').count():
                                    break
                                tab_id = panel_tabs.nth(index).get_attribute('data-subtab')
                                panel_tabs.nth(index).click()
                                page.wait_for_function('(id)=>state.itemTab===id', arg=tab_id)
                        panel_ids = page.locator('.lex-tabbed-panel [data-subtab]').evaluate_all(
                            'nodes=>nodes.map(n=>n.dataset.subtab)')
                        assert 'linked-records' not in panel_ids, (tab, panel_ids)
                        if tab == 'weapons':
                            # The protected scaling-curve link names its curve
                            # where the field is, with no finder to change it.
                            for _ in panel_ids:
                                if page.locator('[data-field-key="correctType"]').count():
                                    break
                                page.locator('.lex-tabbed-panel [data-subtab]').nth(
                                    panel_ids.index(page.evaluate('state.itemTab')) + 1
                                    if page.evaluate('state.itemTab') in panel_ids else 0).click()
                                page.wait_for_timeout(200)
                            face = page.locator('.ds1-reference-face[data-field-key="correctType"]')
                            assert face.count() == 1
                            if real_root:
                                assert face.locator('.lex-hoverable').count() == 1
                            assert page.locator(
                                '[data-lex-property="correctType"] .ds1-find-reference').count() == 0
                        control = reveal(page,page.locator('input[data-field-key][type="number"]').first)
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
                    # Mod contents only leaves the one edited armor out of three; unticking restores the list.
                    page.locator(strip + '[data-subtab="armor"]').click()
                    # The sub flips before the new rows arrive, so the
                    # wait names the armor rows; stale rows would pass it.
                    page.wait_for_function('state.sub==="armor" && state.rows.length>0 && state.rows[0].table==="EquipParamProtector" && state.row?.table==="EquipParamProtector" && !state.pending')
                    real = '.lex-column-list .lex-list-row:not(.lex-filler-row)'
                    toggle = page.locator('.lex-pager-toggle input[aria-label="Mod contents only"]')
                    assert toggle.count() == 1
                    assert toggle.is_enabled()
                    full = page.locator(real).count()
                    assert full > 1
                    changed = page.evaluate('state.rows.find(row=>row.modified===true).id')
                    toggle.check()
                    page.wait_for_function('state.modOnly===true')
                    filtered = ('(changed)=>{const rows=[...document.querySelectorAll('
                        '".lex-column-list .lex-list-row:not(.lex-filler-row)")];'
                        'return rows.length===1 && rows[0].dataset.key.endsWith(":"+changed)}')
                    page.wait_for_function(filtered, arg=changed)
                    toggle.uncheck()
                    restored = ('(full)=>document.querySelectorAll('
                        '".lex-column-list .lex-list-row:not(.lex-filler-row)").length===full')
                    page.wait_for_function(restored, arg=full)
                    # Weapons and armor carry their upgrade paths on an Upgrades panel tab.
                    for tab, owned in (('weapons', True), ('shields', True), ('armor', False)):
                        page.locator(strip + f'[data-subtab="{tab}"]').click()
                        page.wait_for_function('(tab)=>state.sub===tab && (((tab==="weapons"||tab==="shields") && state.row?.table==="EquipParamWeapon") || (tab==="armor" && state.row?.table==="EquipParamProtector"))', arg=tab)
                        page.locator('.lex-tabbed-panel [data-subtab="upgrades"]').click()
                        page.wait_for_function('state.itemTab==="upgrades"')
                        keys = page.locator('.lex-tabbed-panel [data-field-key]').evaluate_all(
                            'nodes=>nodes.map(n=>n.dataset.fieldKey)')
                        for key in ('materialSetId', 'reinforceTypeId', 'basicPrice'):
                            assert key in keys, (tab, keys)
                        assert ('isCustom' in keys) == owned, (tab, keys)
                        assert ('baseChangeCategory' in keys) == owned, (tab, keys)
                        assert ('disableBaseChangeReset' in keys) == owned, (tab, keys)
                        assert any(key.startswith('originEquip') for key in keys), (tab, keys)
                        if output: page.screenshot(path=str(output / f'{tab}-upgrades.png'))
                    # Consumables have no upgrade path, so section tabs but no Upgrades tab.
                    page.locator(strip + '[data-subtab="consumables"]').click()
                    page.wait_for_function('state.sub==="consumables" && state.rows.length>0 && state.rows[0].table==="EquipParamGoods" && state.row?.table==="EquipParamGoods" && !state.pending')
                    page.wait_for_function("() => document.querySelectorAll('.lex-tabbed-panel').length > 0")
                    assert page.locator('.lex-tabbed-panel').count() == 1
                    assert page.locator('.lex-tabbed-panel [data-subtab="upgrades"]').count() == 0
                    # Menu labels is the last subtab and holds one text field;
                    # the enum and checkbox controls live on the param rows.
                    page.locator(strip + '[data-subtab="rings"]').click()
                    # The sub flips before the new rows arrive, so the
                    # wait names the rings rows; stale rows would pass it.
                    page.wait_for_function('state.sub==="rings" && state.rows.length>0 && state.rows[0].table==="EquipParamAccessory" && state.row?.table==="EquipParamAccessory" && !state.pending')
                    rings_tabs = page.locator('.lex-tabbed-panel [data-subtab]')
                    seen = set()
                    for index in range(rings_tabs.count()):
                        if page.locator('select[data-field-key]:visible').count():
                            seen.add('select')
                        if page.locator('input[type="checkbox"][data-field-key]:visible').count():
                            seen.add('checkbox')
                        if seen == {'select', 'checkbox'}:
                            break
                        tab_id = rings_tabs.nth(index).get_attribute('data-subtab')
                        rings_tabs.nth(index).click()
                        page.wait_for_function('(id)=>state.itemTab===id', arg=tab_id)
                    assert seen == {'select', 'checkbox'}, seen
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty===0 && state.pending===0')
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    reopened = ItemDocument((mod / RELATIVE).read_bytes())
                    for table, row_id, field, value in changes:
                        assert reopened.value(table, row_id, field) == value
                    # An item is renamed in the table's Name cell, by double-click.
                    page.locator(strip + '[data-subtab="consumables"]').click()
                    page.wait_for_function('state.sub==="consumables" && state.row && !state.pending')
                    renamed = page.evaluate('state.row.id')
                    cell = page.locator(f'.lex-list-row[data-key$="{renamed}"] [data-column-key="name"]').first
                    cell.click()
                    page.wait_for_timeout(150)
                    cell = page.locator(f'.lex-list-row[data-key$="{renamed}"] [data-column-key="name"]').first
                    cell.dblclick()
                    editor = page.locator('.lex-cell-editing input')
                    editor.fill('Soul Safety Stone')
                    editor.press('Enter')
                    page.wait_for_function('!state.pending && state.row.name==="Soul Safety Stone"')
                    assert page.locator('.lex-detail-panel-name').first.inner_text() == 'Soul Safety Stone'
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty===0 && state.pending===0')
                    assert texts.TextDocument((mod / texts.RELATIVE).read_bytes()).name('EquipParamGoods', renamed) == 'Soul Safety Stone'
                    short = reveal(page, page.locator('input[data-field-key="description"]'))
                    short.fill('A safer stone.')
                    short.press('Tab')
                    page.wait_for_function('!state.pending && state.row.fields.find(f=>f.key==="description").value==="A safer stone."')
                    full = reveal(page, page.locator('textarea[data-field-key="longDescription"]'))
                    full.fill('Line one.\nLine two.')
                    full.press('Tab')
                    page.wait_for_function('!state.pending && state.row.fields.find(f=>f.key==="longDescription").value==="Line one.\\nLine two."')
                    if output: page.screenshot(path=str(output / 'descriptions.png'))
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty===0 && state.pending===0')
                    saved = texts.TextDocument((mod / texts.RELATIVE).read_bytes())
                    assert saved.description('EquipParamGoods', renamed) == 'A safer stone.'
                    assert saved.description('EquipParamGoods', renamed, long=True) == 'Line one.\nLine two.'
                    try:
                        request_json(session.url + 'api/edit', {'table': 'EquipParamGoods', 'id': renamed, 'field': 'description', 'value': 'two\nlines'})
                        raise AssertionError('Invalid description accepted')
                    except HTTPError as error: assert error.code == 400
                    page.set_viewport_size({'width': 1000, 'height': 700})
                    page.locator(strip + '[data-subtab="weapons"]').click()
                    page.wait_for_timeout(500)
                    assert page.locator('#main > .lex-stack .lex-column-list').first.is_visible()
                    expected = set(page.evaluate('state.row.fields.filter(f=>f.editable||(state.row.recordLinks||[]).some(l=>l.field===f.key&&l.kind!=="npc")).map(f=>f.key)'))
                    seen = set()
                    panel_tabs = page.locator('.lex-tabbed-panel [data-subtab]')
                    assert panel_tabs.count() > 1
                    for index in range(panel_tabs.count()):
                        tab_id = panel_tabs.nth(index).get_attribute('data-subtab')
                        panel_tabs.nth(index).click()
                        page.wait_for_function('(id)=>state.itemTab===id', arg=tab_id)
                        fields = page.locator('.lex-tabbed-panel [data-field-key]:visible')
                        for number in range(fields.count()):
                            field = fields.nth(number)
                            field.scroll_into_view_if_needed()
                            box = field.bounding_box()
                            assert box['y'] >= 0 and box['y'] + box['height'] <= 700, box
                            seen.add(field.get_attribute('data-field-key'))
                    assert seen == expected, sorted(expected - seen)
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
                    # Data readiness precedes the shared loading transition.
                    # Coordinate clicks bypass Playwright's overlay checks.
                    vanilla.wait_for_function('!document.documentElement.classList.contains("lex-loading-live")')
                    vanilla.wait_for_selector('.lex-plugin-loading-screen', state='detached')
                    assert vanilla.locator('#global-save').is_disabled()
                    assert 'Vanilla' in vanilla.locator('.lex-project-control').inner_text()
                    # The field is disabled now, matching every other plugin's
                    # read-only look. A real mouse click at its position still
                    # reaches the shared shell's document-level edit-attempt
                    # gate, so click by position rather than through
                    # Playwright's own actionability check, which refuses to
                    # drive a disabled element at all.
                    # A press made while the loading screen still covers the
                    # page lands on that screen, not on the field.
                    vanilla.wait_for_selector('.lex-plugin-loading-screen', state='detached')
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
