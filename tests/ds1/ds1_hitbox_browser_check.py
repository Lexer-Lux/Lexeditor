"""Render the enemy Model view on synthetic data, never game files.

Runs read-only with no mod: viewing models must work for Vanilla readers,
so the enemy and attack switchers must not count as edit attempts.
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
from flver_fixture import build_flver, make_chrbnd
from msb_fixture import build_msb
from plugins.ds1.formats import ItemDocument
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    document = ItemDocument(make_archive())
    document.edit('AtkParam_Npc', 100, 'hit0_Radius', 0.5)
    document.edit('AtkParam_Npc', 100, 'hit0_DmyPoly1', 100)
    document.edit('AtkParam_Npc', 100, 'hit0_DmyPoly2', -1)
    document.edit('AtkParam_Npc', 100, 'hit1_Radius', 0.4)
    document.edit('AtkParam_Npc', 100, 'hit1_DmyPoly1', 100)
    document.edit('AtkParam_Npc', 100, 'hit1_DmyPoly2', 101)
    document.edit('NpcParam', 120000, 'hitRadius', 0.5)
    document.edit('NpcParam', 120000, 'hitHeight', 1.8)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-hitbox-') as folder:
        temp = Path(folder)
        game = temp / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(document.export())
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / 'test.msb').write_bytes(build_msb())
        (game / 'chr').mkdir(parents=True)
        (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(make_chrbnd(build_flver()))
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
                    page.locator('button[data-tab="enemies"]').click()
                    page.wait_for_function('state.tab==="enemies" && state.rows.length>0 && !state.error')
                    page.wait_for_selector('[data-subtab="model"]')
                    # Scoped to the Enemies strip: the monster detail pane
                    # carries its own subtabs further down the page.
                    strip = page.locator('[aria-label="Enemies"] [data-subtab]')
                    assert strip.evaluate_all('nodes=>nodes.map(n=>n.dataset.subtab)') == ['model', 'monsters']
                    page.locator('[data-subtab="model"]').click()
                    page.wait_for_function('state.tab==="enemies" && state.sub==="model" && state.chrView && !state.error')
                    page.wait_for_selector('[data-chr-host][data-ready="true"]', timeout=30000)
                    status = page.locator('[data-chr-status]').inner_text()
                    assert 'c1200' in status, status
                    assert '1 mesh' in status and '2 triangles' in status, status
                    assert '1 model point' in status, status
                    assert '2 live hitboxes' in status, status
                    assert '1 slot points at a missing model point' in status, status
                    assert 'Body R 0.5 x H 1.8' in status, status
                    assert page.locator('canvas[data-viewport]').count() == 1
                    # The quad, the green model point, the blue body and the
                    # red hitboxes paint more than a blank canvas ever could.
                    shot = page.locator('canvas[data-viewport]').screenshot()
                    colors = Image.open(io.BytesIO(shot)).convert('RGB').getcolors(maxcolors=1 << 20)
                    count = 'many' if colors is None else len(colors)
                    assert colors is None or len(colors) > 8, f'hitbox canvas blank ({count} colors)'
                    attacks = page.evaluate('state.chrView.attacks.map(a=>a.name)')
                    assert len(attacks) >= 2, attacks
                    page.locator('.lex-viewport-bar [aria-label="Attack"]').click()
                    page.locator('.lex-choice-popover button', has_text=attacks[1]).click()
                    page.wait_for_function('(want)=>document.querySelector("[data-chr-status]")?.textContent?.includes(want)', arg=attacks[1], timeout=30000)
                    page.wait_for_selector('[data-chr-host][data-ready="true"]', timeout=30000)
                    if output:
                        page.screenshot(path=str(output / 'hitbox.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 hitbox render passed.')


if __name__ == '__main__':
    main()
