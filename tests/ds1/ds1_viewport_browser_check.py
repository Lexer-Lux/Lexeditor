"""Render and edit the Areas viewport on synthetic map data, never game files.

Phase one runs read-only with no mod: viewing maps must work for
Vanilla readers, so the map switcher must not count as an edit attempt,
and Duplicate and Remove stay disabled. Phase two opens a mod project
and drives Duplicate, Remove and the move commit through the real UI.
"""
import io
import sys
from pathlib import Path
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from flver_fixture import build_flver
from msb_fixture import build_msb
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

PARTS = (("enemy", 2, 0, 0, 120000), ("player", 4, 0, 1, None), ("piece", 0, 0, 1, None),
         ("chest", 1, 0, 1, None), ("wall", 5, 0, 1, None), ("walk", 8, 0, 1, None))


def make_game(temp):
    game = temp / 'game'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive())
    (game / MAP_DIR).mkdir(parents=True)
    (game / MAP_DIR / 'test.msb').write_bytes(build_msb(parts=PARTS))
    (game / MAP_DIR / 'test2.msb').write_bytes(build_msb(parts=PARTS))
    (game / 'map' / 'test').mkdir(parents=True)
    (game / 'map' / 'test' / 'm10piece.flver').write_bytes(build_flver())
    (game / 'map' / 'test2').mkdir(parents=True)
    (game / 'map' / 'test2' / 'm10piece.flver').write_bytes(build_flver())
    return game


def open_viewport(page, session):
    page.goto(session.url)
    page.wait_for_selector('body[data-ds1-ready="true"]')
    page.locator('button[data-tab="areas"]').click()
    page.wait_for_function('state.tab==="areas" && state.sub==="placements" && state.rows.length>0 && !state.error')
    # State updates before render, so the strip needs its own
    # wait; the previous tab's strip would pass a bare assert.
    page.wait_for_selector('[data-subtab="viewport"]')
    assert page.locator('[data-subtab]').evaluate_all('nodes=>nodes.map(n=>n.dataset.subtab)') == ['placements', 'viewport']
    page.locator('[data-subtab="viewport"]').click()
    page.wait_for_function('state.tab==="areas" && state.sub==="viewport" && state.mapView && !state.error')
    page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=30000)


def rendered_pixels(page, label):
    # A blank canvas is one flat color; a rendered quad
    # adds its face plus antialiased edges.
    shot = page.locator('canvas[data-viewport]').screenshot()
    colors = Image.open(io.BytesIO(shot)).convert('RGB').getcolors(maxcolors=1 << 20)
    count = 'many' if colors is None else len(colors)
    assert colors is None or len(colors) > 2, f'{label} canvas blank ({count} colors)'


def phase_readonly(play, game, output, errors):
    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                          'LEXEDITOR_MOD_READ_ONLY': '1'})
    try:
        session.start()
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.on('pageerror', lambda error: errors.append(str(error)))
            open_viewport(page, session)
            status = page.locator('[data-viewport-status]').inner_text()
            for want in ('test.msb', '5 parts', '6 triangles', '1 collision marker',
                         '1 navigation marker', '1 part has no visible mesh'):
                assert want in status, status
            assert page.locator('canvas[data-viewport]').count() == 1
            rendered_pixels(page, 'test.msb')
            assert page.locator('[data-viewport-action="duplicate"]').is_disabled()
            assert page.locator('[data-viewport-action="remove"]').is_disabled()
            toggle = page.locator('[data-viewport-action="collision"]')
            assert toggle.inner_text() == 'Hide collision'
            toggle.click()
            assert toggle.inner_text() == 'Show collision'
            toggle.click()
            assert toggle.inner_text() == 'Hide collision'
            page.locator('canvas[data-viewport]').click(position={'x': 720, 'y': 380})
            page.wait_for_function('document.querySelector("[data-viewport-status]").textContent.includes("Selected:")',
                                   timeout=30000)
            assert page.locator('[data-viewport-action="duplicate"]').is_disabled()
            page.locator('.lex-viewport-picker').first.click()
            page.locator('.lex-choice-popover button', has_text='test2.msb').click()
            page.wait_for_function('(want)=>document.querySelector("[data-viewport-status]")?.textContent?.includes(want)', arg='test2.msb', timeout=30000)
            page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=30000)
            rendered_pixels(page, 'test2.msb')
            if output:
                page.screenshot(path=str(output / 'viewport.png'))
        finally:
            browser.close()
    finally:
        session.stop()
        assert session.wait_closed()


def phase_edit(play, game, mod, output, errors):
    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                          'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
    try:
        session.start()
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.on('pageerror', lambda error: errors.append(str(error)))
            open_viewport(page, session)
            page.evaluate('viewportCtl.select("1:0")')
            page.wait_for_function('state.mapSelected==="1:0"', timeout=30000)
            assert 'chest0' in page.locator('[data-viewport-status]').inner_text()
            duplicate = page.locator('[data-viewport-action="duplicate"]')
            remove = page.locator('[data-viewport-action="remove"]')
            assert not duplicate.is_disabled() and not remove.is_disabled()
            duplicate.click()
            page.wait_for_function('state.mapSelected==="1:1"', timeout=30000)
            assert 'chest0_1' in page.locator('[data-viewport-status]').inner_text()
            assert '6 parts' in page.locator('[data-viewport-status]').inner_text()
            remove.click()
            page.locator('.lex-dialog').get_by_role('button', name='Remove').click()
            # Six view parts: the removed duplicate is gone, and the enemy
            # without a model file never renders, so five parts show.
            page.wait_for_function('state.mapSelected===null && state.mapView.parts.length===6',
                                   timeout=30000)
            # The state lands before the remount renders; the old status
            # still shows the duplicate until the fresh map draws.
            page.wait_for_function('document.querySelector("[data-viewport-status]").textContent'
                                   '.startsWith("test.msb: 5 parts")', timeout=30000)
            page.evaluate("viewportMove('test.msb','1:0',[9,8,7])")
            page.wait_for_function("state.pending===0 && state.mapView.parts.find(p=>p.key==='1:0').pos[0]===9",
                                   timeout=30000)
            moved = page.evaluate("fetch('/api/row?table=test.msb&id=1:0').then(r=>r.json())"
                                  ".then(d=>d.row.fields.filter(f=>f.key.startsWith('pos')).map(f=>f.value))")
            assert moved == [9.0, 8.0, 7.0], moved
            page.evaluate('viewportCtl.select("1:0")')
            page.wait_for_function('state.mapSelected==="1:0"', timeout=30000)
            page.wait_for_timeout(1200)
            if output:
                page.screenshot(path=str(output / 'viewport-edit.png'))
        finally:
            browser.close()
    finally:
        session.stop()
        assert session.wait_closed()


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    errors = []
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-viewport-') as folder:
        temp = Path(folder)
        game = make_game(temp)
        mod = temp / 'mod'
        mod.mkdir()
        (mod / MARKER).touch()
        with sync_playwright() as play:
            phase_readonly(play, game, output, errors)
            phase_edit(play, game, mod, output, errors)
    assert not errors, errors
    print('DS1 viewport render and edit passed.')


if __name__ == '__main__':
    main()
