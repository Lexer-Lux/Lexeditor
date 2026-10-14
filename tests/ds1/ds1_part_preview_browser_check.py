"""Open the weapon, armor and enemy model drawers on synthetic data.

Runs read-only with no mod: previewing models must work for Vanilla
readers, and rows without a model say why instead of opening a drawer.
"""
import io
import sys
from pathlib import Path
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from flver_fixture import build_flver, make_chrbnd
from msb_fixture import build_msb
from plugins.ds1 import texts
from plugins.ds1.formats import ItemDocument, write_field
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def put(document, table, row_id, key, value):
    _row, start, data = document._row(table, row_id)
    spec = next(f['spec'] for f in document.schemas[table]['fields'] if f['spec'].key == key)
    document.plain[start:start + len(data)] = write_field(data, spec, value, '<')


def pinned(page, table, row_id):
    """Wait until selection, record and heading all name one row."""
    page.wait_for_function(
        f'state.selected === "{table}:{row_id}" && state.row && state.row.table === "{table}"'
        f' && state.row.id === {row_id} && document.querySelector(".lex-detail-panel-name")'
        "?.textContent?.includes(state.row.name)")


def navigate(page, selector, table, row_id):
    page.locator(selector).click()
    pinned(page, table, row_id)


def painted(page, locator):
    shot = page.locator(locator).screenshot()
    colors = Image.open(io.BytesIO(shot)).convert('RGB').getcolors(maxcolors=1 << 20)
    count = 'many' if colors is None else len(colors)
    assert colors is None or len(colors) > 8, f'preview canvas blank ({count} colors)'


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    document = ItemDocument(make_archive())
    put(document, 'EquipParamWeapon', 100, 'equipModelId', 100)
    put(document, 'EquipParamProtector', 100, 'equipModelId', 200)
    put(document, 'EquipParamProtector', 100, 'equipModelCategory', 2)
    put(document, 'EquipParamProtector', 100, 'equipModelGender', 3)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-parts-') as folder:
        temp = Path(folder)
        game = temp / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(document.export())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / 'test.msb').write_bytes(build_msb())
        (game / 'chr').mkdir(parents=True)
        (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(make_chrbnd(build_flver()))
        (game / 'parts').mkdir(parents=True)
        (game / 'parts' / 'WP_A_0100.partsbnd.dcx').write_bytes(
            make_chrbnd(build_flver(), stem='WP_A_0100'))
        (game / 'parts' / 'BD_M_0200.partsbnd.dcx').write_bytes(
            make_chrbnd(build_flver(), stem='BD_M_0200'))
        (game / 'parts' / 'BD_F_0200.partsbnd.dcx').write_bytes(
            make_chrbnd(build_flver(), stem='BD_F_0200'))
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    # Weapon drawer: icon arms, opens, renders, closes.
                    navigate(page, '[data-subtab="weapons"]', "EquipParamWeapon", 100)
                    page.wait_for_function('state.sub === "weapons" && state.row && !state.error')
                    trigger = page.locator('.lex-detail-panel-heading .lex-model-preview-trigger')
                    trigger.wait_for()
                    trigger.click()
                    page.wait_for_selector('.lex-model-stage[data-ready="true"]', timeout=30000)
                    assert page.locator('canvas[data-preview]').count() == 1
                    assert page.evaluate('!!window.__lexPreview'), 'preview hook missing'
                    hint = page.locator('.lex-model-stage-hint').inner_text()
                    assert '1 mesh' in hint and '2 triangles' in hint, hint
                    painted(page, 'canvas[data-preview]')
                    if output:
                        page.screenshot(path=str(output / 'parts-weapon.png'))
                    trigger.click()
                    page.wait_for_function('window.__lexPreview === undefined')
                    assert page.locator('canvas[data-preview]').count() == 0
                    # Armor drawer: dual-gender rows offer male and female.
                    navigate(page, '[data-subtab="armor"]', "EquipParamProtector", 100)
                    page.wait_for_function('state.sub === "armor" && state.row && !state.error')
                    trigger = page.locator('.lex-detail-panel-heading .lex-model-preview-trigger')
                    trigger.wait_for()
                    trigger.click()
                    page.wait_for_selector('.lex-model-stage[data-ready="true"]', timeout=30000)
                    picker = page.locator('button[aria-label="Model variant"]')
                    assert picker.inner_text() == 'Model: Male'
                    picker.click()
                    page.locator('.lex-choice-popover button', has_text='Female').click()
                    page.wait_for_function(
                        'document.querySelector(\'button[aria-label="Model variant"]\')'
                        '.textContent === "Model: Female"')
                    page.wait_for_selector('.lex-model-stage[data-ready="true"]', timeout=30000)
                    painted(page, 'canvas[data-preview]')
                    if output:
                        page.screenshot(path=str(output / 'parts-armor.png'))
                    # Consumables name no model: the icon says why.
                    navigate(page, '[data-subtab="consumables"]', "EquipParamGoods", 100)
                    page.wait_for_function('state.sub === "consumables" && state.row && !state.error')
                    reason = page.locator('.lex-detail-panel-heading .lex-detail-panel-icon')
                    reason.wait_for()
                    assert 'No model' in reason.inner_text()
                    label = reason.get_attribute('aria-label') or ''
                    assert 'no model file' in label, label
                    assert page.locator(
                        '.lex-detail-panel-heading .lex-model-preview-trigger').count() == 0
                    # Enemy drawer: the placed character model renders plain.
                    page.locator('button[data-tab="enemies"]').click()
                    page.wait_for_function('state.tab === "enemies" && state.rows.length > 0 && !state.error')
                    page.locator('[data-subtab="monsters"]').click()
                    page.wait_for_function('state.sub === "monsters" && state.rows.length > 0 && !state.error')
                    rows = page.locator(".lex-column-list .lex-list-row")
                    for index in range(rows.count()):
                        rows.nth(index).click()
                        page.wait_for_timeout(300)
                        if page.evaluate("state.selected") == "NpcParam:120000":
                            break
                    pinned(page, "NpcParam", 120000)
                    page.wait_for_function('state.sub === "monsters" && state.row && !state.error')
                    trigger = page.locator('.lex-detail-panel-heading .lex-model-preview-trigger')
                    trigger.wait_for()
                    trigger.click()
                    page.wait_for_selector('.lex-model-stage[data-ready="true"]', timeout=30000)
                    assert page.locator('canvas[data-preview]').count() == 1
                    painted(page, 'canvas[data-preview]')
                    if output:
                        page.screenshot(path=str(output / 'parts-enemy.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 part preview passed.')


if __name__ == '__main__':
    main()
