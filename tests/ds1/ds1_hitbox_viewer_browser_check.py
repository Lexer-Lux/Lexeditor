"""DS1 hitbox viewer: shared controls, editable hurtbox, drag-to-move.

The enemy drawer builds its hitbox fields from the tab's shared
controls (data-field-key inputs with units), the body's hurtbox
(radius, height, offset) edits beside them, and dragging a model-point
chip onto a slot's point field re-anchors (moves) that hitbox. Each
slot carries a live-or-idle status line, and each chip names its
anchor's bone and bind-pose position.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from flver_fixture import build_flver, make_chrbnd
from msb_fixture import build_msb
from plugins.ds1.formats import ItemDocument
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    document = ItemDocument(make_archive())
    document.edit('AtkParam_Npc', 100, 'hit0_Radius', 0.5)
    document.edit('AtkParam_Npc', 100, 'hit0_DmyPoly1', -1)
    document.edit('AtkParam_Npc', 100, 'hit0_DmyPoly2', -1)
    document.edit('NpcParam', 120000, 'hitRadius', 0.5)
    document.edit('NpcParam', 120000, 'hitHeight', 1.8)
    document.edit('NpcParam', 120000, 'hitYOffset', 0.0)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-hitbox-viewer-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(document.export())
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / 'test.msb').write_bytes(build_msb())
        (game / 'chr').mkdir(parents=True)
        (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(make_chrbnd(build_flver(
            dummies=[(100, (1.0, 2.0, 3.0)), (200, (4.0, 5.0, 6.0))])))
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.set_default_timeout(60000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.locator('button[data-tab="enemies"]').click()
                    page.wait_for_function('state.tab==="enemies" && state.rows.length>0 && !state.error')
                    page.locator('[data-subtab="monsters"]').click()
                    page.wait_for_function('state.sub==="monsters" && state.rows.length>0 && !state.error')
                    rows = page.locator('.lex-column-list .lex-list-row')
                    for index in range(rows.count()):
                        rows.nth(index).click()
                        page.wait_for_timeout(300)
                        if page.evaluate('state.selected') == 'NpcParam:120000':
                            break
                    page.wait_for_function(
                        'state.row?.table==="NpcParam" && state.row?.id===120000 && !state.error')
                    page.locator('.lex-detail-panel-heading .lex-model-preview-trigger').click()
                    page.wait_for_selector('.lex-chr-viewer-stage[data-ready="true"]', timeout=60000)
                    fields = page.locator('.lex-chr-viewer-fields')
                    # Shared controls: the tab's own inputs, keyed like everywhere.
                    radius = fields.locator('[data-field-key="hit0_Radius"]')
                    assert radius.count() == 1
                    assert radius.evaluate('n=>n.tagName') == 'INPUT'
                    assert radius.is_enabled()
                    assert radius.input_value() == '0.5'
                    # The hurtbox edits beside the hitboxes.
                    body = fields.locator('[data-field-key="hitRadius"]')
                    assert body.count() == 1
                    assert body.input_value() == '0.5'
                    assert fields.locator('[data-field-key="hitHeight"]').input_value() == '1.8'
                    seq = page.evaluate(
                        'document.querySelector(".lex-chr-viewer-fields").dataset.fieldsSeq')
                    body.fill('0.7')
                    body.press('Tab')
                    # The edit commits in place first, then the viewer
                    # repaints and the fields re-render; the generation
                    # proves the repaint landed, not the in-place echo.
                    page.wait_for_function(
                        '(before)=>document.querySelector(".lex-chr-viewer-fields")'
                        '.dataset.fieldsSeq!==before', arg=seq)
                    status = page.locator('.lex-chr-viewer .lex-viewport-status')
                    assert 'Body R 0.7' in status.inner_text()
                    assert fields.locator('[data-field-key="hitRadius"]').input_value() == '0.7'
                    hurt = page.evaluate(
                        "fetch('/api/row?table=NpcParam&id=120000').then(r=>r.json())"
                        ".then(v=>v.row.fields.find(f=>f.key==='hitRadius').value)")
                    assert hurt == 0.7, hurt
                    # The drawer stays open across the edit.
                    assert fields.locator('[data-field-key="hitRadius"]').count() == 1
                    # Model-point chips: dragging one moves the hitbox there.
                    chips = fields.locator('.ds1-dummy-chip')
                    assert chips.count() == 2
                    assert chips.nth(0).get_attribute('aria-label') == 'Model point 100 on root at (1, 2, 3)'
                    assert chips.nth(0).get_attribute('data-lex-title') == (
                        "Anchor 100 on root at (1, 2, 3). Drag onto a slot's point field to move the hitbox there")
                    assert '0 live hitboxes' in status.inner_text()
                    slot = fields.locator('input[data-hit-slot-status]')
                    assert slot.count() == 4
                    assert slot.nth(0).input_value() == 'Idle: no anchor set.'
                    assert slot.nth(1).input_value() == 'Idle: radius 0 strikes nothing.'
                    seq = page.evaluate(
                        'document.querySelector(".lex-chr-viewer-fields").dataset.fieldsSeq')
                    chips.nth(0).drag_to(fields.locator('[data-point-field="hit0_DmyPoly1"]'))
                    page.wait_for_function(
                        '(before)=>document.querySelector(".lex-chr-viewer-fields")'
                        '.dataset.fieldsSeq!==before', arg=seq)
                    assert '1 live hitbox' in status.inner_text()
                    assert fields.locator('[data-point-field="hit0_DmyPoly1"] input').input_value() == '100'
                    assert fields.locator('input[data-hit-slot-status="0"]').input_value() == (
                        'Live: sphere, radius 0.5 m on anchor 100.')
                    moved = page.evaluate(
                        "fetch('/api/row?table=AtkParam_Npc&id=100&sub=attacks').then(r=>r.json())"
                        ".then(v=>v.row.fields.find(f=>f.key==='hit0_DmyPoly1').value)")
                    assert moved == 100, moved
                    # The Attacks escape hatch is still the only such button.
                    assert fields.get_by_role('button', name='in Attacks').count() == 1
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
        print('DS1 hitbox viewer: shared controls, hurtbox, drag-to-move, statuses, chip labels passed.')


if __name__ == '__main__':
    main()
