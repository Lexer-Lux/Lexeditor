"""Play back a synthetic motion, never game files.

Runs read-only with no mod: watching motions must work for Vanilla
readers, so the character and motion switchers must not count as edit
attempts.
"""
import io
import sys
import time
from pathlib import Path
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from flver_fixture import build_flver, make_chrbnd
from hkx_fixture import build_tag0
from tae_fixture import build_anibnd, build_tae
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

ROWS = ('rows => rows.map(row => row.textContent.replace(/\\u200b/g, "").trim()).filter(Boolean)')


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-anim-') as folder:
        temp = Path(folder)
        game = temp / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'chr').mkdir(parents=True)
        (game / 'chr' / 'c1200.anibnd.dcx').write_bytes(build_anibnd({
            'Skeleton.hkx': build_tag0(), 'a87_3300.hkx': build_tag0(), 'a87.tae': build_tae()}))
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
                    # Characters left, viewport center, animations right; no strip.
                    page.locator('button[data-tab="animations"]').click()
                    page.wait_for_function('state.tab === "animations" && !state.error')
                    page.wait_for_selector('[data-anim-host]')
                    assert page.locator('[data-subtab]').count() == 0
                    chars = page.locator('[data-anim-chars] .lex-list-row').evaluate_all(ROWS)
                    assert chars == ['c1200'], chars
                    assert page.locator('[data-anim-chars] .lex-column-list.lex-list-fill').count() == 1
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    motions = page.locator('[data-anim-list] .lex-list-row .lex-column-list-cell[data-column-key="name"]').evaluate_all(ROWS)
                    assert motions == ['a87_3300.hkx', 'animation 3301'], motions
                    lengths = page.locator('[data-anim-list] .lex-list-row .lex-column-list-cell[data-column-key="length"]').evaluate_all(ROWS)
                    assert lengths == ['0.10s', '\u2014'], lengths
                    assert page.locator('[data-anim-list] .lex-column-list.lex-list-fill').count() == 1
                    # The mount may finish before the tab navigation lands:
                    # readiness, not the transient throbber, is the signal.
                    page.wait_for_selector('[data-anim-host][data-ready="true"]', timeout=30000)
                    # Loaded: the status line under the viewer stays empty.
                    status = page.locator('[data-anim-status]').inner_text()
                    assert status.strip() == '', status
                    assert page.locator('canvas[data-viewport]').count() == 1
                    shot = page.locator('canvas[data-viewport]').screenshot()
                    colors = Image.open(io.BytesIO(shot)).convert('RGB').getcolors(maxcolors=1 << 20)
                    count = 'many' if colors is None else len(colors)
                    assert colors is None or len(colors) > 2, f'anim canvas blank ({count} colors)'
                    # The motion plays on its own: the readout advances.
                    first = page.locator('[data-anim-readout]').inner_text()
                    page.wait_for_function('(want)=>document.querySelector("[data-anim-readout]")?.textContent!==want',
                                           arg=first, timeout=10000)
                    assert page.locator('.lex-anim-marker').count() == 4
                    # Two cues share the start slot, so the topmost marker
                    # covers its twin; the seek still fires.
                    page.locator('.lex-anim-marker').first.click(force=True)
                    time.sleep(0.3)
                    # The marker also selects its event: the left panel
                    # jumps to the Events tab with all four cues listed.
                    page.wait_for_function('state.animLeftTab === "events" && state.animScope.level === "events"')
                    events = page.locator('[data-anim-list] .lex-list-row').evaluate_all(ROWS)
                    assert len(events) == 4, events
                    assert ':ev:' in page.evaluate('state.selected')
                    page.locator('[data-anim-left] [data-tabstrip-id="anims"]').click()
                    # Pausing freezes the readout; scrubbing seeks it.
                    page.locator('[data-anim-timeline] button[aria-label="Play or pause"]').click()
                    frozen = page.locator('[data-anim-readout]').inner_text()
                    time.sleep(0.5)
                    assert page.locator('[data-anim-readout]').inner_text() == frozen
                    slider = page.locator('[data-anim-timeline] input[type="range"]')
                    last = slider.get_attribute('max')
                    slider.fill(last)
                    page.wait_for_function('(want)=>document.querySelector("[data-anim-readout]")?.textContent?.startsWith(want)', arg=f'{last} /', timeout=10000)
                    # Switching motions is viewing, not editing: nothing dirties.
                    page.locator('[data-anim-list] .lex-list-row', has_text='animation 3301').click()
                    page.wait_for_function(
                        'document.querySelector("[data-anim-status]")?.textContent?.includes("no playable motion")')
                    page.locator('[data-anim-list] .lex-list-row', has_text='a87_3300.hkx').click()
                    page.wait_for_selector('[data-anim-host][data-ready="true"]', timeout=30000)
                    assert page.evaluate('state.dirty') == 0
                    if output:
                        page.screenshot(path=str(output / 'anim.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 animation render passed.')


if __name__ == '__main__':
    main()
