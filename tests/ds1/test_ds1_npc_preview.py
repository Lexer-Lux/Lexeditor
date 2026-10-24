"""Armor-assembled NPCs get the honest empty preview, never a blank stage.

Humans walk on the shared player rig, which carries bones but no meshes:
their bodies are armor sets the game assembles, not one model file.
Previewing the bare rig used to mount a glitched empty thumbnail and
magnifier. The header now shows the placeholder with the reason and no
magnifier, and there is no Model tab: an NPC with neither a model nor
attacks has nothing to inspect. Armor-assembled NPCs that do have
attacks open the attack drawer instead, with their hitboxes floating
on the bare rig.
"""
import io
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from flver_fixture import build_flver, make_chrbnd  # noqa: E402
from msb_fixture import build_msb  # noqa: E402
from plugins.ds1.msb import MAP_DIR  # noqa: E402
from plugins.ds1.store import MARKER, RELATIVE  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def select(page, table, row_id):
    row = page.locator(f'.lex-list-row[data-key="{table}:{row_id}"]')
    row.scroll_into_view_if_needed()
    row.click()
    page.wait_for_function('(key) => state.row && `${state.row.table}:${state.row.id}` === key',
                           arg=f'{table}:{row_id}')


def test_armor_assembled_npc_has_no_clickable_preview():
    errors = []
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-npc-armor-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive(field_values={
            'NpcParam': {223000: {'npcType': 2}}}))
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / 'm0.msb').write_bytes(build_msb(
            parts=(('enemy', 2, 0, 0, 251000), ('enemy', 2, 1, 1, 223000)),
            models=(('c1200', 0), ('c0000', 0))))
        (game / 'chr').mkdir(parents=True)
        (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(make_chrbnd(build_flver()))
        (game / 'chr' / 'c0000.chrbnd.dcx').write_bytes(
            make_chrbnd(build_flver(mesh_count=0), stem='c0000'))
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.evaluate("navigate('npcs','npcs')")
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    select(page, 'NpcParam', 223000)
                    page.wait_for_selector(
                        '.lex-detail-panel-icon[data-lex-preview-state="unavailable"]')
                    icon = page.locator('.lex-detail-panel-icon[data-lex-preview-state="unavailable"]')
                    assert 'armor' in (icon.get_attribute('aria-label') or ''), \
                        icon.get_attribute('aria-label')
                    assert page.locator('.lex-model-preview-trigger').count() == 0
                    assert page.locator('.lex-tabbed-panel [data-subtab="model"]').count() == 0
                    select(page, 'NpcParam', 251000)
                    page.wait_for_selector('.lex-model-preview-trigger')
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()


def drawer_session(temp, field_values=None):
    temp = Path(temp)
    game, mod = temp / 'game', temp / 'mod'
    values = {'NpcParam': {223000: {'npcType': 2}}}
    for table, rows in (field_values or {}).items():
        merged = values.setdefault(table, {})
        for row_id, fields in rows.items():
            merged.setdefault(row_id, {}).update(fields)
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive(field_values=values))
    (game / MAP_DIR).mkdir(parents=True)
    (game / MAP_DIR / 'm0.msb').write_bytes(build_msb(
        parts=(('enemy', 2, 0, 0, 251000), ('enemy', 2, 1, 1, 223000)),
        models=(('c1200', 0), ('c0000', 0))))
    (game / 'chr').mkdir(parents=True)
    (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(make_chrbnd(build_flver()))
    (game / 'chr' / 'c0000.chrbnd.dcx').write_bytes(
        make_chrbnd(build_flver(mesh_count=0), stem='c0000'))
    mod.mkdir()
    (mod / MARKER).touch()
    return DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                       'LEXEDITOR_DS1_PROJECT': str(mod),
                       'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})


def attack_radius(page, attack_id=100):
    return page.evaluate(
        "fetch('/api/row?table=AtkParam_Npc&id=100&sub=attacks').then(r=>r.json())"
        ".then(payload=>payload.row.fields.find(field=>field.key==='hit0_Radius').value)")


def test_drawer_lists_attacks_and_edits_hitboxes():
    errors = []
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-npc-drawer-') as folder:
        session = drawer_session(folder)
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.evaluate("navigate('npcs','npcs')")
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    select(page, 'NpcParam', 251000)
                    page.wait_for_selector('.lex-model-preview-trigger')
                    page.locator('.lex-model-preview-trigger').click()
                    page.wait_for_selector('.lex-chr-viewer')
                    rows = page.locator('.lex-chr-viewer-list .lex-list-row')
                    assert rows.count() >= 1, rows.count()
                    field = page.locator('.lex-chr-viewer-fields input').first
                    field.wait_for()
                    assert attack_radius(page) == 0
                    field.fill('2.5')
                    field.press('Tab')
                    page.wait_for_function(
                        'state.pending === 0 && fieldHistory.undoStack.length === 1')
                    assert attack_radius(page) == 2.5
                    page.evaluate('fieldHistory.undo()')
                    page.wait_for_function(
                        'fieldHistory.undoStack.length === 0 && fieldHistory.redoStack.length === 1')
                    page.wait_for_function(
                        "document.querySelector('.lex-chr-viewer-fields input').value === '0'")
                    assert attack_radius(page) == 0
                    assert page.locator('.lex-chr-viewer').count() == 1
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
def test_armor_assembled_npc_with_attacks_opens_attack_drawer():
    errors = []
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-npc-armor-drawer-') as folder:
        session = drawer_session(folder, field_values={
            'BehaviorParam': {102: {'variationId': 223000, 'refType': 0}},
            'AtkParam_Npc': {102: {'hit0_Radius': 0.5, 'hit0_DmyPoly1': 100,
                                   'hit0_DmyPoly2': -1}}})
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.evaluate("navigate('npcs','npcs')")
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    select(page, 'NpcParam', 223000)
                    # No model to picture, so the placeholder stays, but the
                    # magnifier opens the attack drawer.
                    trigger = page.locator('.lex-detail-panel-heading .lex-model-preview-trigger')
                    trigger.wait_for()
                    icon = page.locator('.lex-detail-panel-heading .lex-detail-panel-icon')
                    assert icon.locator('.lex-no-thumbnail').count() == 1
                    assert icon.locator('img.ds1-model-thumbnail').count() == 0
                    assert page.locator('.lex-tabbed-panel [data-subtab="model"]').count() == 0
                    trigger.click()
                    page.wait_for_selector('.lex-chr-viewer-stage[data-ready="true"]', timeout=30000)
                    status = page.locator('.lex-chr-viewer .lex-viewport-status').inner_text()
                    assert 'c0000' in status, status
                    assert '0 meshes' in status, status
                    assert '1 live hitbox' in status, status
                    dots = page.evaluate(
                        'document.querySelector(".lex-chr-viewer-stage").dataset.dots')
                    assert dots == '1', dots
                    names = page.locator('.lex-chr-viewer-list .lex-list-row').all_inner_texts()
                    assert len(names) == 1, names
                    assert 'NPC_test2' in names[0], names
                    field = page.locator('.lex-chr-viewer-fields input').first
                    assert field.input_value() == '0.5'
                    shot = page.locator('.lex-chr-viewer-stage canvas').screenshot()
                    colors = Image.open(io.BytesIO(shot)).convert('RGB').getcolors(maxcolors=1 << 20)
                    count = 'many' if colors is None else len(colors)
                    assert colors is None or len(colors) > 8, f'hitbox canvas blank ({count} colors)'
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
