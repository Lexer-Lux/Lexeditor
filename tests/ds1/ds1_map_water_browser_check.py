"""Map viewport draws shader water translucent blue, not gray.

A [We] water material names no diffuse (only a bump map), so the old
fallback gray lit by the scene rig rendered the Depths sewer channel
as flat white. Water materials now get a translucent blue instead.
Synthetic fixtures only; read-only with no mod.
"""
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from flver_fixture import build_flver
from msb_fixture import build_msb
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

WATER = 0x2F6F9E


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-map-water-') as folder:
        game = Path(folder) / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'map' / 'MapStudio').mkdir(parents=True)
        (game / 'map' / 'MapStudio' / 'm10_00_00_00.msb').write_bytes(build_msb())
        piece_dir = game / 'map' / 'm10_00_00_00'
        piece_dir.mkdir(parents=True)
        (piece_dir / 'm10piece.flver.dcx').write_bytes(build_flver(
            mtd_name='A10_Water_sewer[We].mtd'))
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
            with urllib.request.urlopen(
                    session.url + '/api/map/geometry?map=m10_00_00_00.msb&model=m10piece',
                    timeout=60) as response:
                data = json.load(response)
            assert 'Water' in data['meshes'][0]['mat_def'], data['meshes'][0].get('mat_def')
            assert 'tex0' not in data['textures'], sorted(data['textures'])
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1400, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function('state.tab === "maps" && !state.error',
                                           timeout=120000)
                    page.wait_for_selector('[data-viewport-host][data-ready="true"]',
                                           timeout=120000)
                    seam = page.evaluate(
                        "!!document.querySelector('[data-viewport-host]')._viewportScene")
                    assert seam, 'no viewport scene seam'
                    found = page.evaluate(
                        """() => { const scene = document.querySelector(
                            '[data-viewport-host]')._viewportScene;
                            const wet = [];
                            scene.traverse(obj => {
                              if (obj.isMesh && obj.material && obj.material.transparent &&
                                  obj.material.color &&
                                  obj.material.color.getHex() === %d)
                                wet.push({opacity: obj.material.opacity,
                                          depthWrite: obj.material.depthWrite}); });
                            return wet; }""" % WATER)
                    assert found, 'no translucent blue water material in the scene'
                    for entry in found:
                        assert entry['opacity'] == 0.65, entry
                        assert entry['depthWrite'] is False, entry
                    if output:
                        page.locator('[data-viewport-host]').screenshot(
                            path=str(output / 'map-water.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 map water passed.')


if __name__ == '__main__':
    main()
