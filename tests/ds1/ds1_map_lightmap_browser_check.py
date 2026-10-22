"""Map viewport bakes lightmaps: lightMap on channel 1 over uv1.

A fixture map piece with a diffuse and a lightmap texture renders
through MeshBasicMaterial with the light on the second UV set - map
times light, no scene rig, the way the game shades terrain.
Synthetic fixtures only; read-only with no mod.
"""
import base64
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
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-map-lightmap-') as folder:
        game = Path(folder) / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'map' / 'MapStudio').mkdir(parents=True)
        (game / 'map' / 'MapStudio' / 'm10_00_00_00.msb').write_bytes(build_msb())
        piece_dir = game / 'map' / 'm10_00_00_00'
        piece_dir.mkdir(parents=True)
        (piece_dir / 'm10piece.flver.dcx').write_bytes(build_flver(
            second_uv=True, light_tex='lit0'))
        red = make_dds_rgba(2, 2, [(255, 0, 0, 255)] * 4)
        white = make_dds_rgba(2, 2, [(255, 255, 255, 255)] * 4)
        (piece_dir / 'm10piece.tpf').write_bytes(make_tpf([('tex0', red),
                                                           ('lit0', white)]))
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
            with urllib.request.urlopen(
                    session.url + '/api/map/geometry?map=m10_00_00_00.msb&model=m10piece',
                    timeout=60) as response:
                data = json.load(response)
            assert data['meshes'][0]['light'] == 'lit0', data['meshes'][0].get('light')
            assert base64.b64decode(data['meshes'][0]['uv1']), 'uv1 is empty'
            assert 'lit0' in data['textures'], sorted(data['textures'])
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
                            const lit = [];
                            scene.traverse(obj => {
                              if (obj.isMesh && obj.material && obj.material.lightMap)
                                lit.push({type: obj.material.type,
                                          channel: obj.material.lightMap.channel,
                                          uv1: !!obj.geometry.attributes.uv1}); });
                            return lit; }""")
                    assert found, 'no lightmapped material in the scene'
                    for entry in found:
                        assert entry['type'] == 'MeshBasicMaterial', entry
                        assert entry['channel'] == 1, entry
                        assert entry['uv1'], entry
                    if output:
                        page.locator('[data-viewport-host]').screenshot(
                            path=str(output / 'map-lightmap.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 map lightmap passed.')


if __name__ == '__main__':
    main()
