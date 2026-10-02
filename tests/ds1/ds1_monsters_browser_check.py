"""Rendered monster resistance edits against synthetic or copied installed data."""
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
from plugins.ds1.formats import ItemDocument
from plugins.ds1.monsters import RESISTANCES
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
    changes = {'def_phys': 101, 'def_slash': -10, 'resist_poison': 275, 'physGuardCutRate': 33.5}
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
                    assert page.locator('[data-subtab]').evaluate_all('n=>n.map(x=>x.dataset.subtab)') == ['monsters']
                    assert page.evaluate('state.row.id') == 120000
                    count = page.evaluate('state.rows.length')
                    assert count == (335 if real else 2)
                    expected = set(page.evaluate('state.row.fields.map(f=>f.key)'))
                    assert expected == set(RESISTANCES)
                    seen, edited = set(), set()
                    for index in range(12):
                        fields = page.locator('input[data-field-key]:visible')
                        for i in range(fields.count()):
                            field = fields.nth(i)
                            key = field.get_attribute('data-field-key')
                            seen.add(key)
                            assert field.get_attribute('type') == 'number'
                            assert field.get_attribute('min') is not None and field.get_attribute('max') is not None
                            field.scroll_into_view_if_needed()
                            box = field.bounding_box()
                            assert 0 <= box['y'] and box['y'] + box['height'] <= 800
                            if key in changes:
                                field.fill(str(changes[key])); field.press('Tab')
                                page.wait_for_function('(x)=>state.pending===0 && state.row.fields.find(f=>f.key===x.key).value===x.value',
                                                       arg={'key': key, 'value': changes[key]})
                                edited.add(key)
                        if output: page.screenshot(path=str(output / f'monsters-{index}.png'))
                        following = page.locator('.lex-tweaks-pages').get_by_role('button', name='Next page', exact=True)
                        if not following.count() or not following.is_enabled(): break
                        following.click()
                    assert seen == expected and edited == changes.keys()
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty===0 && state.pending===0')
                    page.reload(); page.wait_for_selector('body[data-ds1-ready="true"]'); monsters()
                    reopened = ItemDocument((mod / RELATIVE).read_bytes())
                    for key, value in changes.items(): assert reopened.value('NpcParam', 120000, key) == value
                    page.locator('[data-tab="items"]').click()
                    page.wait_for_function('state.tab==="items" && state.row?.table==="EquipParamGoods"')
                    assert page.locator('[data-subtab]').count() == 8
                    monsters()
                    page.set_viewport_size({'width': 1000, 'height': 700})
                    search = page.get_by_role('searchbox', name='Search monsters')
                    search.fill('Small Rat')
                    page.wait_for_function('state.row?.id===120100')
                    page.wait_for_timeout(350)  # Let the shared label fitter finish after resize/search.
                    if output: page.screenshot(path=str(output / 'monsters-small.png'))
                    # Public API must enforce the same narrow boundary as the UI.
                    for identity, key in [(120000, 'hp'), (223000, 'def_phys')]:
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
                    assert vanilla.locator('#global-save').is_disabled()
                    # The field is disabled now, matching every other plugin's
                    # read-only look; a real click still reaches the shared
                    # shell's edit-attempt gate, so force this scripted one
                    # past Playwright's own actionability check for it.
                    vanilla.locator('input[data-field-key="def_phys"]').click(force=True)
                    vanilla.get_by_role('button', name='Create a mod', exact=True).wait_for()
                    vanilla.get_by_role('button', name='Cancel', exact=True).click()
                    assert request_json(session.url + 'api/state')['dirtyCount'] == 0
                    assert not errors, errors
                finally: browser.close()
        finally: session.stop()
        assert hashlib.sha256((game / RELATIVE).read_bytes()).hexdigest() == original_hash
    if source: assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    print(json.dumps({'monsters':count,'resistanceFields':len(expected),'uiEditsSavedAndReloaded':len(edited),
                      'vanillaReadOnly':True,'originalUnchanged':True,'browserErrors':errors}))


if __name__ == '__main__': main()
