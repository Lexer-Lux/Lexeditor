"""Render the Maps directory tabs and edit/save/reload, never game files."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'shared'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paged_detail import reveal
from ds1_fixture import make_archive, make_text_archive
from flver_fixture import build_flver
from msb_fixture import build_msb
from plugins.ds1 import texts
from plugins.ds1.formats import WORLD_SUBTABS, ItemDocument
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from core.service_session import request_json
from playwright.sync_api import sync_playwright

FOE = 120000
FRIEND = 251000


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    real_root = os.environ.get('LEXEDITOR_DS1_ACCEPTANCE_ROOT')
    original_path = Path(real_root) / RELATIVE if real_root else None
    raw = original_path.read_bytes() if original_path else make_archive()
    source_hash = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-world-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes((Path(real_root) / texts.RELATIVE).read_bytes() if real_root else make_text_archive())
        if not real_root:
            # Enemies wear the piece mesh so go-to has a group to focus.
            (game / MAP_DIR).mkdir(parents=True)
            (game / MAP_DIR / 'test.msb').write_bytes(build_msb(parts=(
                ("enemy", 2, 0, 1, FOE), ("enemy", 2, 1, 1, FRIEND),
                ("player", 4, 0, 1, None), ("piece", 0, 0, 1, None))))
            (game / MAP_DIR / 'test2.msb').write_bytes(build_msb(parts=(
                ("enemy", 2, 0, 1, FOE), ("player", 4, 0, 1, None), ("piece", 0, 0, 1, None))))
            for stem in ('test', 'test2'):
                (game / 'map' / stem).mkdir(parents=True)
                (game / 'map' / stem / 'm10piece.flver').write_bytes(build_flver())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors, changes = [], []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    assert page.locator('button[data-tab="world"]').count() == 0
                    page.locator('button[data-tab="maps"]').click()
                    page.wait_for_function('state.tab==="maps" && state.rows.length>0 && state.dirRows.length>0 && !state.error')
                    page.wait_for_selector('[data-maps-dir] [data-subtab="treasure"]')
                    assert page.locator('[data-maps-dir] [data-subtab]').evaluate_all(
                        'nodes=>nodes.map(n=>n.dataset.subtab)') == ['drops', 'enemies', 'npcs', 'shops', 'treasure']
                    # The NPC/enemy split follows the live npcType, not names.
                    page.locator('[data-maps-dir] [data-subtab="npcs"]').click()
                    page.wait_for_function('state.dirTab==="npcs"')
                    npcs = page.evaluate('state.dirRows.map(r=>r.values.npcId)')
                    assert npcs, npcs
                    assert page.evaluate('state.dirRows.every(r=>r.values.npcType===2)')
                    if not real_root:
                        assert npcs == [FRIEND], npcs
                    page.locator('[data-maps-dir] [data-subtab="enemies"]').click()
                    page.wait_for_function('state.dirTab==="enemies"')
                    assert page.evaluate('state.dirRows.length > 0')
                    assert page.evaluate('state.dirRows.every(r=>r.values.npcType!==2)')
                    if not real_root:
                        assert sorted(page.evaluate('state.dirRows.map(r=>r.values.npcId)')) == [FOE, FOE]
                    assert page.locator('[data-maps-dir] [data-goto]').count() > 0
                    for tab, _, table in WORLD_SUBTABS:
                        page.locator(f'[data-maps-dir] [data-subtab="{tab}"]').click()
                        page.wait_for_function('(want)=>state.dirTab===want.tab && state.dirRows.length>0 && state.dirRows[0].table===want.table && !state.error',
                                               arg={'tab': tab, 'table': table})
                        page.wait_for_timeout(200)
                        assert page.evaluate('state.dirRows.length') > 0
                        page.locator('[data-maps-dir] .lex-list-row').first.click()
                        page.wait_for_function('(table)=>state.mapTab==="selection" && state.row && state.row.table===table',
                                               arg=table)
                        keys = page.evaluate('state.row.fields.map(f=>f.key)')
                        assert keys, keys
                        control = reveal(page, page.locator('[data-maps-side] input[data-field-key][type="number"][min]').first)
                        field = control.get_attribute('data-field-key')
                        old = float(control.input_value().replace(',', ''))
                        low, high = float(control.get_attribute('min')), float(control.get_attribute('max'))
                        value = min(max(old + 1, low), high)
                        if value == old:
                            value = max(low, old - 1)
                        assert value != old
                        identity = page.evaluate('({table:state.row.table,id:state.row.id})')
                        control.fill(str(int(value)) if value.is_integer() else str(value))
                        control.press('Tab')
                        page.wait_for_function('state.pending===0 && state.dirty>0')
                        row = request_json(session.url + f"api/row?table={identity['table']}&id={identity['id']}&sub={tab}")['row']
                        assert next(f['value'] for f in row['fields'] if f['key'] == field) == value
                        # The detail stays filtered after the edit round-trip.
                        assert {f['key'] for f in page.evaluate('state.row.fields')} == set(keys)
                        changes.append((identity['table'], identity['id'], field, value))
                        if output:
                            page.screenshot(path=str(output / f'dir-{tab}.png'))
                    # Go-to jumps maps and lands the camera on the placement.
                    page.locator('[data-maps-dir] [data-subtab="enemies"]').click()
                    page.wait_for_function('state.dirTab==="enemies" && state.dirRows.length>0')
                    target = page.evaluate('state.dirRows.find(r=>r.table!==state.mapId)?.table')
                    assert target, 'directory spans one map only'
                    page.wait_for_function('!!viewportCtl', timeout=60000)
                    page.evaluate("""(map)=>{
                      const row = state.dirRows.find(r=>r.table===map);
                      goToPlacement(row.table, row.table+':'+row.id);
                    }""", target)
                    page.wait_for_function('(map)=>state.mapId===map', arg=target, timeout=60000)
                    page.wait_for_function('!document.querySelector("[data-viewport-host][data-ready]")', timeout=60000)
                    page.wait_for_selector("[data-viewport-host][data-ready='true']", timeout=60000)
                    page.wait_for_function('!!viewportCtl', timeout=60000)
                    page.wait_for_function("""()=>{
                      const row = state.rows.find(r=>r.table+':'+r.id===state.selected);
                      if (!row || !viewportCtl) return false;
                      const aim = viewportCtl.aim();
                      const dx = aim[0]-row.values.posX, dy = aim[1]-row.values.posY, dz = aim[2]-row.values.posZ;
                      return Math.sqrt(dx*dx+dy*dy+dz*dz) < 5;
                    }""", timeout=60000)
                    if output:
                        page.screenshot(path=str(output / 'dir-goto.png'))
                    page.locator('#global-save').click()
                    page.wait_for_function('state.dirty===0 && state.pending===0')
                    page.reload()
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    reopened = ItemDocument((mod / RELATIVE).read_bytes())
                    for table, row_id, field, value in changes:
                        assert reopened.value(table, row_id, field) == value
                    assert not errors, errors
                finally:
                    browser.close()
            assert (game / RELATIVE).read_bytes() == raw
            assert hashlib.sha256(raw).hexdigest() == source_hash
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 directory lists, details, go-to, save/reload passed.')


if __name__ == '__main__':
    main()
