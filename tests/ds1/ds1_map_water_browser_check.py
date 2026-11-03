"""Shader water uses its normal map even when it has no diffuse texture.
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
from flver_fixture import build_flver, make_chrbnd
from mtd_fixture import build_mtd
from msb_fixture import build_msb
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

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
        model = build_flver(mtd_name='A10_Water_sewer[We].mtd')
        assert b'g_Diffuse\0' in model
        (piece_dir / 'm10piece.flver.dcx').write_bytes(model.replace(b'g_Diffuse\0', b'g_Bumpmap\0'))
        textures=game/'map'/'m10'
        textures.mkdir()
        pixels=[(80,80,80,255),(160,160,160,255)]*8
        (textures/'ripple.tpf').write_bytes(make_tpf([('tex0',make_dds_rgba(4,4,pixels))]))
        definitions=game/'mtd'
        definitions.mkdir()
        definition=bytearray(make_chrbnd(b'',extra=[('A10_Water_sewer[We].mtd',build_mtd())],dcx=False))
        definition[12]=0x54
        (definitions/'Mtd.mtdbnd.dcx').write_bytes(definition)
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
            assert data['meshes'][0]['map'] is None
            assert data['meshes'][0]['normal'] == 'tex0'
            assert 'tex0' in data['textures'], data.get('notes')
            assert abs(data['meshes'][0]['water']['color'][3]-0.4)<0.00001
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
                              if (obj.isMesh && obj.material?.transparent && obj.material.bumpMap)
                                wet.push({opacity: obj.material.opacity,
                                          depthWrite: obj.material.depthWrite,
                                          bump:!!obj.material.bumpMap,
                                          channel:obj.material.bumpMap?.channel,
                                          colorSpace:obj.material.bumpMap?.colorSpace,
                                          color:obj.material.color.toArray(),
                                          waveHeight:obj.material.bumpScale}); });
                            return wet; }""")
                    assert found, 'no material-defined water surface in the scene'
                    for entry in found:
                        assert abs(entry['opacity']-0.4)<0.00001, entry
                        assert entry['depthWrite'] is False, entry
                        assert entry['bump'] and entry['channel']==0, entry
                        assert entry['colorSpace']=='', entry
                        assert all(abs(a-b)<0.00001 for a,b in zip(entry['color'],[0.2,0.3,0.1])), entry
                        assert entry['waveHeight']==2, entry
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
