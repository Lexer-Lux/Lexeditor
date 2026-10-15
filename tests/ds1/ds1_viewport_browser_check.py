"""Render and edit the Maps viewport on synthetic map data, never game files.

Phase one runs read-only with no mod: viewing maps must work for
Vanilla readers, so the map switcher must not count as an edit attempt,
and Duplicate and Remove stay disabled. A click beside the attached
gizmo must still select what is under the cursor. Phase two opens a mod
project and drives Duplicate, Remove and the move commit through the
real UI; a real gizmo drag keeps the dragged part selected.
"""
import io
import sys
from pathlib import Path
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bhf_fixture import make_bhf, make_edge
from ds1_fixture import make_archive, make_text_archive
from flver_fixture import build_flver
from msb_fixture import build_msb
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1 import texts
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
    (game / MAP_DIR / 'm10_01_00_00.msb').write_bytes(build_msb(parts=PARTS))
    blob = make_text_archive(extra={'Place_name_.fmg': {1010: 'Undead Burg', 1011: 'Undead Parish'}})
    (game / texts.RELATIVE).parent.mkdir(parents=True)
    (game / texts.RELATIVE).write_bytes(blob)
    (game / 'map' / 'test').mkdir(parents=True)
    (game / 'map' / 'test' / 'm10piece.flver').write_bytes(build_flver())
    (game / 'map' / 'test2').mkdir(parents=True)
    (game / 'map' / 'test2' / 'm10piece.flver').write_bytes(build_flver())
    (game / 'map' / 'm10_01_00_00').mkdir(parents=True)
    (game / 'map' / 'm10_01_00_00' / 'm10piece.flver').write_bytes(build_flver())
    red = make_dds_rgba(4, 4, [(220, 30, 30, 255)] * 16)
    blob = make_edge(make_tpf([('tex0', red)]))
    area = game / 'map' / 'm10'
    area.mkdir(parents=True)
    (area / 'm10_0000.tpfbdt').write_bytes(bytes(16) + blob)
    (area / 'm10_0000.tpfbhd').write_bytes(
        make_bhf([(r'\m10\tex0.tpf.dcx', 16, len(blob))]))
    return game


def open_viewport(page, session):
    page.goto(session.url)
    page.wait_for_selector('body[data-ds1-ready="true"]')
    page.locator('button[data-tab="maps"]').click()
    page.wait_for_function('state.tab==="maps" && state.mapView && state.rows.length>0 && !state.error')
    page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=30000)


def viewport_click(page, action):
    # The map buttons only take clicks while the picture is hovered, as for
    # a human reader: hovering the button itself never engages them.
    page.locator('[data-viewport-host]').hover()
    page.locator(f'[data-viewport-action="{action}"]').click()


def rendered_pixels(page, label):
    # A blank canvas is one flat color; a rendered quad
    # adds its face plus antialiased edges.
    shot = page.locator('canvas[data-viewport]').screenshot()
    colors = Image.open(io.BytesIO(shot)).convert('RGB').getcolors(maxcolors=1 << 20)
    count = 'many' if colors is None else len(colors)
    assert colors is None or len(colors) > 2, f'{label} canvas blank ({count} colors)'


def textured_pixels(page, label):
    # The m10 piece wears a pure red split-archive texture: a gray
    # render keeps red at bay, a textured one is full of it.
    shot = page.locator('canvas[data-viewport]').screenshot()
    raw = Image.open(io.BytesIO(shot)).convert('RGB').tobytes()
    red = sum(1 for i in range(0, len(raw), 3)
              if raw[i] > raw[i + 1] + 30 and raw[i] > raw[i + 2] + 30)
    assert red > 100, f'{label} map renders gray ({red} red pixels)' 

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
            for want in ('m10_01_00_00.msb', '5 parts', '6 triangles', '1 collision part',
                         '1 navigation part', '1 part has no visible mesh'):
                assert want in status, status
            assert page.locator('canvas[data-viewport]').count() == 1
            rendered_pixels(page, 'm10_01_00_00.msb')
            textured_pixels(page, 'm10_01_00_00.msb')
            assert page.locator('[data-viewport-action="duplicate"]').is_disabled()
            assert page.locator('[data-viewport-action="remove"]').is_disabled()
            assert page.locator('[data-viewport-action="add"]').is_disabled()
            assert page.locator('[data-viewport-action="copy"]').count() == 0
            assert page.locator('[data-viewport-action="paste"]').count() == 0
            assert page.locator('[data-viewport-action="duplicate"] svg').count() == 1
            assert page.locator('[data-viewport-action="remove"]').inner_text() == 'x'
            assert not page.locator('[data-viewport-action="rotate"]').is_disabled()
            assert page.locator('[data-viewport-action="collision"]').count() == 0
            canvas = page.locator('canvas[data-viewport]')
            box = canvas.bounding_box()
            # The gizmo on a selected movable part must not swallow the
            # next click: this stays frozen on 1:0 without the veto fix.
            page.evaluate('viewportCtl.select("1:0")')
            page.wait_for_function('state.mapSelected==="1:0"', timeout=30000)
            canvas.click(position={'x': box['width'] / 2, 'y': box['height'] / 2})
            page.wait_for_function('state.mapSelected==="4:0"', timeout=30000)
            assert page.locator('[data-viewport-action="duplicate"]').is_disabled()
            page.locator('[data-tabstrip-id="maps"]').click()
            page.wait_for_function('state.mapTab==="maps"')
            labels = page.locator('[data-maps-side] .lex-column-list-head-cell').evaluate_all(
                'nodes=>nodes.map(n=>n.textContent)')
            for want in ('Name', 'Parts', 'Models', 'Collision', 'Navigation'):
                assert want in ' '.join(labels), labels
            overflow = page.evaluate("""() => {
                const table = document.querySelector('[data-maps-side] .lex-column-list');
                return table.scrollWidth - table.clientWidth;
            }""")
            assert overflow <= 1, overflow
            counts = page.evaluate('state.mapList.find(r=>r.id==="test.msb").values')
            named = page.evaluate('state.mapList.find(r=>r.id==="m10_01_00_00.msb").name')
            assert named == 'Undead Burg (m10_01_00_00.msb)', named
            assert counts['collision'] == 1 and counts['navigation'] == 1, counts
            page.locator('[data-maps-side] .lex-list-row', has_text='test2.msb').click()
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
            page.locator('[data-maps-side] .lex-list-row', has_text='test.msb').click()
            page.wait_for_function('(want)=>document.querySelector("[data-viewport-status]")'
                                   '?.textContent?.includes(want)', arg='test.msb', timeout=30000)
            page.evaluate('viewportCtl.select("1:0")')
            page.wait_for_function('state.mapSelected==="1:0"', timeout=30000)
            assert 'chest0' in page.locator('[data-viewport-status]').inner_text()
            duplicate = page.locator('[data-viewport-action="duplicate"]')
            remove = page.locator('[data-viewport-action="remove"]')
            assert not duplicate.is_disabled() and not remove.is_disabled()
            viewport_click(page, 'duplicate')
            page.wait_for_function('state.mapSelected==="1:1"', timeout=30000)
            page.wait_for_function('document.querySelector("[data-viewport-status]").textContent'
                                   '.includes("chest0_1")', timeout=30000)
            assert '6 parts' in page.locator('[data-viewport-status]').inner_text()
            viewport_click(page, 'remove')
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
            page.evaluate("viewportRotate('test.msb','1:0',[0,180,0])")
            page.wait_for_function("state.pending===0 && state.mapView.parts.find(p=>p.key==='1:0').rot[1]===180",
                                   timeout=30000)
            turned = page.evaluate("fetch('/api/row?table=test.msb&id=1:0').then(r=>r.json())"
                                   ".then(d=>d.row.fields.filter(f=>f.key.startsWith('rot')).map(f=>f.value))")
            assert turned == [0.0, 180.0, 0.0], turned
            # A press that moves the part is a drag, not a click: the
            # release must keep the dragged part selected.
            page.evaluate('viewportCtl.select("1:0")')
            page.wait_for_function('state.mapSelected==="1:0"', timeout=30000)
            drag_box = page.locator('canvas[data-viewport]').bounding_box()
            page.mouse.move(drag_box['x'] + drag_box['width'] / 2, drag_box['y'] + drag_box['height'] / 2)
            page.mouse.down()
            page.evaluate("viewportMove('test.msb','1:0',[21,22,23])")
            page.wait_for_function("state.pending===0 && state.mapView.parts.find(p=>p.key==='1:0').pos[0]===21",
                                   timeout=30000)
            page.mouse.up()
            page.wait_for_function('state.pending===0', timeout=30000)
            assert page.evaluate('state.mapSelected') == '1:0'
            page.evaluate('viewportAdd(\'test.msb\',document.querySelector(\'[data-viewport-action="add"]\'))')
            page.locator('.lex-choice-popover button', has_text='m10piece').click()
            page.wait_for_function('state.mapSelected==="1:1"', timeout=30000)
            page.wait_for_function('document.querySelector("[data-viewport-status]").textContent'
                                   '.includes("6 parts")', timeout=30000)
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
