"""Map lightmaps load linear while diffuse maps stay sRGB.

A fixture map piece carries a packed lightmap UV set (the way Depths
pieces do) plus diffuse and light members in its sidecar TPF. The
mounted scene's lightmapped material must bind its lightmap without
an sRGB tag (baked irradiance is linear data; tagging it sRGB
crushed dim rooms to near-black) while its diffuse keeps the sRGB
tag. Synthetic fixtures only; read-only with no mod.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from ds1_textures_tab_browser_check import make_dds, make_tpf, solid_pixels
from flver_fixture import build_flver
from msb_fixture import build_msb
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-map-light-') as folder:
        game = Path(folder) / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'map' / 'MapStudio').mkdir(parents=True)
        (game / 'map' / 'MapStudio' / 'm10_00_00_00.msb').write_bytes(build_msb())
        piece_dir = game / 'map' / 'm10_00_00_00'
        piece_dir.mkdir(parents=True)
        (piece_dir / 'm10piece.flver.dcx').write_bytes(build_flver(
            packed_uv=True, light_tex='lit0', tex_name='tex0'))
        (piece_dir / 'm10piece.tpf').write_bytes(make_tpf([
            ('tex0', make_dds(16, 16, solid_pixels(16, 16, (200, 100, 50, 255)))),
            ('lit0', make_dds(16, 16, solid_pixels(16, 16, (35, 35, 35, 255)))),
        ]))
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
        errors = []
        try:
            session.start()
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
                    spaces = page.evaluate(
                        """() => { const scene = document.querySelector(
                            '[data-viewport-host]')._viewportScene;
                            const out = [];
                            scene.traverse(obj => {
                              if (!obj.isMesh || !obj.material?.lightMap) return;
                              out.push({light: obj.material.lightMap.colorSpace,
                                map: obj.material.map?.colorSpace ?? null}); });
                            return out; }""")
                    assert spaces, 'no lightmapped material mounted'
                    for entry in spaces:
                        assert entry['light'] in ('', 'linear-srgb'), entry
                        assert entry['map'] == 'srgb', entry
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print('DS1 map lightmap linear passed.')


if __name__ == '__main__':
    main()
