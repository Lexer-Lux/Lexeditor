"""Maps viewport chrome: no counts footer, readable Local toggle.

The parts/models/triangles status line under the map viewport is gone;
selection feedback lives in the Selection panel. The directory's Local?
filter reads left to right instead of scaling the pager row tall.
"""
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


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-maps-viewport-') as folder:
        game, mod = Path(folder) / 'game', Path(folder) / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'map' / 'MapStudio').mkdir(parents=True)
        (game / 'map' / 'MapStudio' / 'm10_00_00_00.msb').write_bytes(build_msb())
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
                    page = browser.new_page(viewport={'width': 1400, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function('state.tab==="maps" && !state.error', timeout=60000)
                    page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=60000)
                    assert page.locator('[data-viewport-status]').count() == 0
                    page.locator('[data-tabstrip-id="placements"]').click()
                    page.wait_for_function('state.mapTab==="placements"', timeout=30000)
                    page.locator('[data-maps-dir] .lex-subtab-button', has_text='Drops').click()
                    page.wait_for_function('state.dirTab==="drops"', timeout=30000)
                    page.wait_for_selector('[data-maps-dir] [data-dir-local]', timeout=30000)
                    toggle = page.locator('[data-dir-local]')
                    assert toggle.count() == 1
                    # Loading the directory can replace the row between
                    # separate style and box reads. Measure one visible row
                    # atomically instead of dereferencing a detached box.
                    measured = page.wait_for_function("""() => {
                      const node = document.querySelector('[data-dir-local]');
                      if (!node) return null;
                      const box = node.getBoundingClientRect();
                      if (!box.width || !box.height) return null;
                      return {height: box.height,
                        mode: getComputedStyle(node.querySelector(':scope > span')).writingMode};
                    }""", timeout=30000).json_value()
                    assert measured['mode'] == 'horizontal-tb', measured
                    assert measured['height'] < 50, measured
                    if output:
                        page.screenshot(path=str(output / 'maps-viewport.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print('DS1 maps viewport passed.')


if __name__ == '__main__':
    main()
