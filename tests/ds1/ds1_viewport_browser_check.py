"""Render the Areas viewport on synthetic map data, never game files.

Runs read-only with no mod: viewing maps must work for Vanilla readers,
so the map switcher must not count as an edit attempt.
"""
import io
import sys
from pathlib import Path
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from flver_fixture import build_flver
from msb_fixture import build_msb
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-viewport-') as folder:
        temp = Path(folder)
        game = temp / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / 'test.msb').write_bytes(build_msb())
        (game / MAP_DIR / 'test2.msb').write_bytes(build_msb())
        (game / 'map' / 'test').mkdir(parents=True)
        (game / 'map' / 'test' / 'm10piece.flver').write_bytes(build_flver())
        (game / 'map' / 'test2').mkdir(parents=True)
        (game / 'map' / 'test2' / 'm10piece.flver').write_bytes(build_flver())
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
                    page.locator('button[data-tab="areas"]').click()
                    page.wait_for_function('state.tab==="areas" && state.sub==="placements" && state.rows.length>0 && !state.error')
                    # State updates before render, so the strip needs its own
                    # wait; the previous tab's strip would pass a bare assert.
                    page.wait_for_selector('[data-subtab="viewport"]')
                    assert page.locator('[data-subtab]').evaluate_all('nodes=>nodes.map(n=>n.dataset.subtab)') == ['placements', 'viewport']
                    page.locator('[data-subtab="viewport"]').click()
                    page.wait_for_function('state.tab==="areas" && state.sub==="viewport" && state.mapView && !state.error')
                    page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=30000)
                    status = page.locator('[data-viewport-status]').inner_text()
                    assert 'test.msb' in status and '3 parts' in status and '6 triangles' in status, status
                    assert page.locator('canvas[data-viewport]').count() == 1
                    def rendered_pixels(label):
                        # A blank canvas is one flat color; a rendered quad
                        # adds its face plus antialiased edges.
                        shot = page.locator('canvas[data-viewport]').screenshot()
                        colors = Image.open(io.BytesIO(shot)).convert('RGB').getcolors(maxcolors=1 << 20)
                        count = 'many' if colors is None else len(colors)
                        assert colors is None or len(colors) > 2, f'{label} canvas blank ({count} colors)'
                    rendered_pixels('test.msb')
                    page.locator('.lex-viewport-picker').click()
                    page.locator('.lex-choice-popover button', has_text='test2.msb').click()
                    page.wait_for_function('(want)=>document.querySelector("[data-viewport-status]")?.textContent?.includes(want)', arg='test2.msb', timeout=30000)
                    page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=30000)
                    rendered_pixels('test2.msb')
                    if output:
                        page.screenshot(path=str(output / 'viewport.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 viewport render passed.')


if __name__ == '__main__':
    main()
