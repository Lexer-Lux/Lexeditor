"""Map camera keeps a tight depth range: no more distant shimmer.

Near 0.1 under a far plane past the horizon left distant coplanar
ground patches fighting for every pixel. The camera now fits both
planes to the map's own box every frame, so the far/near ratio stays
small at any zoom. Synthetic fixtures only; read-only with no mod.
"""
import sys
import tempfile
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


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-map-depth-') as folder:
        game = Path(folder) / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'map' / 'MapStudio').mkdir(parents=True)
        (game / 'map' / 'MapStudio' / 'm10_00_00_00.msb').write_bytes(build_msb())
        piece_dir = game / 'map' / 'm10_00_00_00'
        piece_dir.mkdir(parents=True)
        (piece_dir / 'm10piece.flver.dcx').write_bytes(build_flver())
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
                    page.wait_for_timeout(500)
                    depth = page.evaluate(
                        """() => { const camera = document.querySelector(
                            '[data-viewport-host]')._viewportCamera;
                            if (!camera) return {near: 0, far: 0};
                            return {near: camera.near, far: camera.far}; }""")
                    assert depth['near'] > 0.1, depth
                    assert depth['far'] / depth['near'] < 1000, depth
                    if output:
                        page.locator('[data-viewport-host]').screenshot(
                            path=str(output / 'map-depth.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 map depth passed.')


if __name__ == '__main__':
    main()
