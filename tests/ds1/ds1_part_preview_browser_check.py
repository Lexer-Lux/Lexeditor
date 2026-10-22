"""Open the weapon, armor and enemy model drawers on synthetic data.

Runs read-only with no mod: previewing models must work for Vanilla
readers, and rows without a model say why instead of opening a drawer.
"""
import base64
import io
import sys
from pathlib import Path
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from drb_fixture import make_dcx, make_drb, sprite_shape
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from flver_fixture import build_flver, make_chrbnd
from msb_fixture import build_msb
from tpf_fixture import make_dds_rgba, make_tpf
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


def icon_left_of_name(page):
    box = page.locator('.lex-detail-panel-heading .lex-detail-panel-icon').bounding_box()
    name = page.locator('.lex-detail-panel-heading .lex-detail-panel-identity').bounding_box()
    assert box and name and box['x'] + box['width'] <= name['x'] + 1, (box, name)


def loaded_images(page, selector):
    """Every matching image finished loading with real pixels."""
    shots = page.locator(selector)
    assert shots.count() > 0, selector
    sizes = page.evaluate(
        """(query) => [...document.querySelectorAll(query)].map(
            image => [image.naturalWidth, image.naturalHeight])""",
        selector)
    assert sizes and all(width > 0 and height > 0 for width, height in sizes), sizes
    return shots.count()


def trigger_open(page):
    """The header thumbnail that opened the viewer stays visible and
    clickable while viewing, so clicking it again exits."""
    state = page.evaluate("""() => {
        const trigger = document.querySelector(
            '.lex-detail-panel-heading .lex-model-preview-trigger');
        const box = trigger.getBoundingClientRect();
        const hit = document.elementFromPoint(
            box.left + box.width / 2, box.top + box.height / 2);
        const style = getComputedStyle(trigger);
        return {shown: style.visibility === 'visible' && style.display !== 'none'
                && box.width > 0 && box.height > 0,
                clickable: !!(hit && (hit === trigger || trigger.contains(hit)))};
    }""")
    assert state == {'shown': True, 'clickable': True}, state


def attached_thumb(page):
    icon = page.locator('.lex-detail-panel-heading .lex-detail-panel-icon')
    img = icon.locator('img.ds1-model-thumbnail')
    img.wait_for(timeout=30000)
    page.wait_for_function("document.querySelector('.lex-detail-panel-heading .lex-detail-panel-icon img.ds1-model-thumbnail')?.dataset.modelReady==='true'")
    src = img.get_attribute('src') or ''
    assert src.startswith('data:image/png'), src[:40]
    assert len(src) > 1000, len(src)
    assert 'No image' not in icon.inner_text()
    icon_left_of_name(page)


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    document = ItemDocument(make_archive())
    put(document, 'EquipParamWeapon', 100, 'equipModelId', 100)
    put(document, 'EquipParamGoods', 100, 'iconId', 2004)
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
        red = make_dds_rgba(4, 4, [(200, 40, 40, 255)] * 16)
        (game / 'parts' / 'WP_A_0100.partsbnd.dcx').write_bytes(
            make_chrbnd(build_flver(), stem='WP_A_0100',
                        extra=[('WP_A_0100.tpf', make_tpf([('tex0', red)]))]))
        (game / 'parts' / 'BD_M_0200.partsbnd.dcx').write_bytes(
            make_chrbnd(build_flver(), stem='BD_M_0200'))
        (game / 'parts' / 'BD_F_0200.partsbnd.dcx').write_bytes(
            make_chrbnd(build_flver(pos_offset=(5.0, 0.0, 0.0)), stem='BD_F_0200'))
        (game / 'menu').mkdir(parents=True)
        quadrants = []
        for y in range(360):
            for x in range(320):
                quadrants.append((255, 0, 0, 255) if x < 160 and y < 180
                                 else (0, 255, 0, 255) if x >= 160 and y < 180
                                 else (0, 0, 255, 255) if x < 160
                                 else (255, 255, 255, 255))
        (game / 'menu' / 'menu_0.tpf.dcx').write_bytes(make_dcx(make_tpf([
            ('Icon00', make_dds_rgba(320, 360, quadrants)),
            ('Menu04_2', make_dds_rgba(512, 1024, [(40, 120, 200, 255)] * 512 * 1024)),
        ])))
        (game / 'menu' / 'menu.drb').write_bytes(make_drb(['Icon00', 'Menu04_2'], {
            'Icon': [('EquIcon_2004', sprite_shape((0, 0, 0, 0), (1, 1, 81, 91), 0))],
        }))
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
                    attached_thumb(page)
                    trigger.click()
                    page.wait_for_selector('.lex-model-stage[data-ready="true"]', timeout=30000)
                    trigger_open(page)
                    assert page.locator('canvas[data-preview]').count() == 1
                    assert page.evaluate('!!window.__lexPreview'), 'preview hook missing'
                    modes = page.locator('.lex-model-stage .lex-model-view-modes button')
                    assert modes.count() == 3
                    assert [modes.nth(index).get_attribute('aria-label')
                            for index in range(3)] == ['Regular', 'Fullbright', 'Wireframe']
                    hint = page.locator('.lex-model-stage-hint').inner_text()
                    assert hint.startswith('Drag to rotate'), hint
                    assert 'mesh' not in hint and 'triangle' not in hint, hint
                    drawer = page.locator('.lex-model-preview-drawer').bounding_box()
                    stage = page.locator('.lex-model-stage').bounding_box()
                    assert abs(stage['y'] + stage['height'] - drawer['y'] - drawer['height']) <= 2, (
                        stage, drawer)
                    assert drawer['width'] - stage['width'] <= 2, (stage, drawer)
                    geo = page.evaluate(
                        "fetch('/api/parts/geometry?table=EquipParamWeapon&id=100&variant=M')"
                        ".then(r => r.json())")
                    assert geo['meshes'][0]['map'] == 'tex0', geo['meshes'][0]
                    assert geo['meshes'][0]['uv'], 'uv missing'
                    raw = base64.b64decode(geo['textures']['tex0'])
                    image = Image.open(io.BytesIO(raw))
                    image.load()
                    assert image.size == (4, 4), image.size
                    painted(page, 'canvas[data-preview]')
                    if output:
                        page.screenshot(path=str(output / 'parts-weapon.png'))
                    trigger.click()
                    page.wait_for_function('window.__lexPreview === undefined')
                    assert page.locator('canvas[data-preview]').count() == 0
                    # Model ID face: the binder name carries the model's
                    # picture inline, like the icon face carries its own.
                    page.locator('.lex-tabbed-panel [data-subtab="appearance"]').click()
                    page.wait_for_function('state.itemTab === "appearance"')
                    field = page.locator('.lex-detail-field', has=page.locator(
                        '.lex-detail-field-label-text', has_text='Model ID'))
                    face = field.locator('.lex-detail-field-control .lex-hoverable')
                    face.wait_for()
                    thumb = face.locator('img.lex-hoverable-icon')
                    thumb.wait_for(timeout=30000)
                    page.wait_for_function(
                        "document.querySelector('.lex-detail-field .lex-hoverable"
                        " img.lex-hoverable-icon')?.dataset.modelReady === 'true'",
                        timeout=30000)
                    src = thumb.get_attribute('src') or ''
                    assert src.startswith('data:image/png'), src[:40]
                    assert len(src) > 1000, len(src)
                    # Armor drawer: dual-gender rows offer male and female.
                    navigate(page, '[data-subtab="armor"]', "EquipParamProtector", 100)
                    page.wait_for_function('state.sub === "armor" && state.row && !state.error')
                    trigger = page.locator('.lex-detail-panel-heading .lex-model-preview-trigger')
                    trigger.wait_for()
                    attached_thumb(page)
                    trigger.click()
                    page.wait_for_selector('.lex-model-stage[data-ready="true"]', timeout=30000)
                    trigger_open(page)
                    toggle = page.locator('.lex-preview-gender-toggle')
                    assert toggle.inner_text() == '\u2642', toggle.inner_text()
                    assert toggle.get_attribute('aria-label') == 'Show female model'
                    assert toggle.evaluate('button=>button.parentElement.className') == 'lex-model-view-modes'
                    modes = page.locator('.lex-model-stage .lex-model-view-modes > button')
                    assert modes.count() == 4
                    assert 'lex-model-view-mode' in (toggle.get_attribute('class') or '')
                    page.wait_for_function(
                        'document.querySelector(".lex-preview-gender-toggle")'
                        '.dataset.lexTitle === "Show female model"')
                    asked = []
                    page.on('request', lambda request: asked.append(request.url)
                            if 'parts/geometry' in request.url else None)
                    toggle.click()
                    page.wait_for_function(
                        'document.querySelector(".lex-preview-gender-toggle")'
                        '.textContent === "\u2640"')
                    assert toggle.get_attribute('aria-label') == 'Show male model'
                    page.wait_for_function(
                        'document.querySelector(".lex-preview-gender-toggle")'
                        '.dataset.lexTitle === "Show male model"')
                    page.wait_for_selector('.lex-model-stage[data-ready="true"]', timeout=30000)
                    assert any('variant=F' in url for url in asked), asked
                    male = page.evaluate(
                        "fetch('/api/parts/geometry?table=EquipParamProtector&id=100&variant=M')"
                        '.then(r => r.json())')
                    female = page.evaluate(
                        "fetch('/api/parts/geometry?table=EquipParamProtector&id=100&variant=F')"
                        '.then(r => r.json())')
                    assert (male['meshes'][0]['positions']
                            != female['meshes'][0]['positions'])
                    painted(page, 'canvas[data-preview]')
                    if output:
                        page.screenshot(path=str(output / 'parts-armor.png'))
                    trigger.click()
                    page.wait_for_function('window.__lexPreview === undefined')
                    assert page.locator('canvas[data-preview]').count() == 0
                    # Consumables have no model: the heading shows the item's
                    # inventory picture with no magnifier and no drawer.
                    navigate(page, '[data-subtab="consumables"]', "EquipParamGoods", 100)
                    page.wait_for_function('state.sub === "consumables" && state.row && !state.error')
                    reason = page.locator('.lex-detail-panel-heading .lex-detail-panel-icon')
                    reason.wait_for()
                    picture = reason.locator('img.lex-ds1-item-icon')
                    picture.wait_for()
                    assert (picture.get_attribute('src') or '').startswith('/api/icon?table='), \
                        picture.get_attribute('src')
                    assert page.evaluate(
                        '(image) => image.naturalWidth > 0', picture.element_handle())
                    assert 'No model' not in reason.inner_text()
                    label = reason.get_attribute('aria-label') or ''
                    assert 'no model file' in label, label
                    assert page.locator(
                        '.lex-detail-panel-heading .lex-model-preview-trigger').count() == 0
                    assert page.locator(
                        '.lex-detail-panel-heading .lex-model-preview-close').count() == 0
                    assert reason.get_attribute('data-lex-preview-state') == 'unavailable'
                    icon_left_of_name(page)
                    shot = page.evaluate(
                        "fetch('/api/icon?table=EquipParamGoods&id=100').then(async r => ["
                        "r.status, r.headers.get('content-type'), (await r.arrayBuffer()).byteLength])")
                    assert shot[0] == 200 and shot[1] == 'image/png' and shot[2] > 100, shot
                    missing = page.evaluate(
                        "fetch('/api/icon?table=NpcParam&id=120000').then(r => r.status)")
                    assert missing == 400, missing
                    # Damage, defense and stat labels carry the game's own art.
                    navigate(page, '[data-subtab="weapons"]', "EquipParamWeapon", 100)
                    page.wait_for_function('state.sub === "weapons" && state.row && !state.error')
                    total = 0
                    panel_tabs = page.locator('.lex-tabbed-panel [data-subtab]')
                    for index in range(panel_tabs.count()):
                        tab_id = panel_tabs.nth(index).get_attribute('data-subtab')
                        panel_tabs.nth(index).click()
                        page.wait_for_function('(id)=>state.itemTab===id', arg=tab_id)
                        if page.locator('img.lex-ds1-label-art').count():
                            page.wait_for_function(
                                "()=>[...document.querySelectorAll('img.lex-ds1-label-art')].every(i=>i.complete&&i.naturalWidth>0)")
                            total += loaded_images(page, 'img.lex-ds1-label-art')
                    assert total >= 4, total
                    assert page.evaluate(
                        "fetch('/api/label?name=physical').then(r => r.status)") == 200
                    assert page.evaluate(
                        "fetch('/api/label?name=poison').then(r => r.status)") == 200
                    # Divine takes the sheet's white ring (icons.py), so it
                    # serves like any mapped label; luck stays the unmapped one.
                    assert page.evaluate(
                        "fetch('/api/label?name=divine').then(r => r.status)") == 200
                    assert page.evaluate(
                        "fetch('/api/label?name=luck').then(r => r.status)") == 400
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
                    attached_thumb(page)
                    trigger.click()
                    page.wait_for_selector('.lex-model-stage[data-ready="true"]', timeout=30000)
                    trigger_open(page)
                    assert page.locator('canvas[data-preview]').count() == 1
                    painted(page, 'canvas[data-preview]')
                    if output:
                        page.screenshot(path=str(output / 'parts-enemy.png'))
                    trigger.click()
                    page.wait_for_function('window.__lexPreview === undefined')
                    assert page.locator('canvas[data-preview]').count() == 0
                    thumb = page.evaluate(
                        "fetch('/api/chr/view?npc=120000&view=thumb').then(r => r.json())")
                    assert 'attacks' not in thumb and 'body' not in thumb, sorted(thumb)
                    assert thumb['chrs'] and thumb['name'], thumb
                    full = page.evaluate(
                        "fetch('/api/chr/view?npc=120000').then(r => r.json())")
                    assert 'attacks' in full and 'body' in full, sorted(full)
                    probe = page.evaluate("""() => {
                        const ui = window.LexeditorUI;
                        const before = ui.noThumbnail('__probe__').className;
                        ui.registerNoThumbnail('__probe__', label => {
                            const span = document.createElement('span');
                            span.className = 'lex-probe-art';
                            span.textContent = label;
                            return span;
                        });
                        const during = ui.noThumbnail('__probe__', 'Probe label').outerHTML;
                        ui.registerNoThumbnail('__probe__', null);
                        const after = ui.noThumbnail('__probe__').className;
                        return {before, during, after};
                    }""")
                    assert 'lex-no-thumbnail' in probe['before'], probe
                    assert 'lex-probe-art' in probe['during'], probe
                    assert 'Probe label' in probe['during'], probe
                    assert probe['after'] == probe['before'], probe
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 part preview passed.')


if __name__ == '__main__':
    main()
