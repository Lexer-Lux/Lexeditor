"""Map lights: gizmos in the viewport, a Lights list, editable details.

Two fixture lights ride the test map: lamp0 shares its point with an SFX
flame, lamp1 stands alone. The viewport draws one marker per light, the
side panel lists them with their looks, and selecting one shows editable
position and look fields. Typed edits move the marker and survive
undo/redo without remounting the viewport.
"""
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from msb_fixture import build_msb
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

MAP = 'm10_00_00_00.msb'

LIGHTS = (
    ('lamp0', 0, 0, 3, (2, 0, -1, 0), struct.pack('<i', 8)),
    ('lamp1', 0, 1, 3, (2, 1, -1, 0), struct.pack('<i', 15)),
    ('flame0', 2, 0, 3, (2, 0, -1, 0), struct.pack('<i', 0)),
)

SCENE_LIGHTS = """() => {
  const scene = document.querySelector('[data-viewport-host]')._viewportScene;
  const found = [];
  scene.traverse(node => {
    if (node.isGroup && node.userData.part && node.userData.part.kind === 'Light') {
      const mesh = node.children.find(child => child.isMesh);
      found.push({key: node.userData.part.key,
                  pos: [node.position.x, node.position.y, node.position.z],
                  mesh: !!mesh, color: mesh ? mesh.material.color.getHex() : null});
    }
  });
  return found.sort((a, b) => a.key < b.key ? -1 : 1);
}"""


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-lights-') as folder:
        game, mod = Path(folder) / 'game', Path(folder) / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'map' / 'MapStudio').mkdir(parents=True)
        (game / 'map' / 'MapStudio' / MAP).write_bytes(build_msb(
            points=(('pt0', (10.0, 20.0, 30.0)), ('pt1', (40.0, 50.0, 60.0))),
            events=LIGHTS))
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function('state.tab==="maps" && state.mapView', timeout=60000)
                    page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=60000)
                    assert page.evaluate('state.mapView.lights.length') == 2
                    markers = page.evaluate(SCENE_LIGHTS)
                    assert [(entry['key'], entry['pos']) for entry in markers] == [
                        ('light:0', [10.0, 20.0, 30.0]), ('light:1', [40.0, 50.0, 60.0])]
                    assert [(entry['mesh'], entry['color']) for entry in markers] == [
                        (True, 0xffc46b), (True, 0xffc46b)]
                    page.locator('[data-tabstrip-id="lights"]').click()
                    page.wait_for_function('state.mapTab==="lights"')
                    rows = page.locator('[data-maps-side] .lex-column-list [role="row"]:not(.lex-column-list-header)')
                    assert rows.count() == 2, rows.count()
                    assert 'lamp0' in rows.nth(0).inner_text()
                    assert '8' in rows.nth(0).inner_text(), rows.nth(0).inner_text()
                    rows.nth(0).click()
                    page.wait_for_function('state.row?.kind==="Light"')
                    assert page.locator('[data-maps-detail] [data-field-key="preset"]:visible'
                                        ).input_value() == '8'
                    assert page.locator('[data-maps-detail] [data-field-key="posX"]:visible'
                                        ).input_value() == '10'
                    assert page.locator('[data-maps-detail] [data-row-action="duplicate"]').count() == 0
                    assert page.locator('[data-maps-detail] [data-row-action="remove"]').count() == 0
                    assert page.locator('[data-maps-detail] [data-row-action="goto"]').count() == 1
                    preset = page.locator('[data-maps-detail] [data-field-key="preset"]:visible')
                    preset.fill('25')
                    preset.press('Tab')
                    page.wait_for_function('state.pending === 0 && fieldHistory.undoStack.length === 1')
                    assert page.evaluate('state.mapView.lights[0].preset') == 25
                    pos = page.locator('[data-maps-detail] [data-field-key="posX"]:visible')
                    pos.fill('11.5')
                    pos.press('Tab')
                    page.wait_for_function('state.pending === 0 && fieldHistory.undoStack.length === 2')
                    assert page.evaluate(SCENE_LIGHTS)[0]['pos'][0] == 11.5
                    mount = page.evaluate('viewportMount')
                    page.evaluate('fieldHistory.undo()')
                    page.wait_for_function(
                        'fieldHistory.undoStack.length === 1 && fieldHistory.redoStack.length === 1')
                    page.wait_for_function(
                        'document.querySelector("[data-maps-detail] [data-field-key=\'posX\']").value === "10"')
                    assert page.evaluate(SCENE_LIGHTS)[0]['pos'][0] == 10.0
                    assert page.evaluate('viewportMount') == mount
                    page.evaluate('fieldHistory.redo()')
                    page.wait_for_function(
                        'fieldHistory.undoStack.length === 2 && fieldHistory.redoStack.length === 0')
                    page.wait_for_function(
                        'document.querySelector("[data-maps-detail] [data-field-key=\'posX\']").value === "11.5"')
                    assert page.evaluate(SCENE_LIGHTS)[0]['pos'][0] == 11.5
                    if output:
                        page.screenshot(path=str(output / 'maps-lights.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print('DS1 map lights passed.')


if __name__ == '__main__':
    main()
