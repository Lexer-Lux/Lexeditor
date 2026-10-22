"""DS1 viewports: map and model hosts show the big centered loading panel.

While geometry loads, the map and MODEL-tab stages show the shared
loadingPanel (a centered 32px pulse, aria-only label), not the tiny
inline loadingStatus with its visible text, and never an empty stage.
Once the canvas mounts, the panel is gone.
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from flver_fixture import build_flver, make_chrbnd
from msb_fixture import build_msb
from plugins.ds1 import texts
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

held = []


def hold(route, _request):
    held.append(route)


def wait_held(page, timeout=15):
    deadline = time.monotonic() + timeout
    while not held:
        assert time.monotonic() < deadline, 'timed out waiting for a held geometry fetch'
        page.wait_for_timeout(50)


def release_next():
    held.pop(0).continue_()


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir())
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-viewport-loading-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
        (game / MAP_DIR).mkdir(parents=True)
        (game / MAP_DIR / 'm0.msb').write_bytes(build_msb(parts=(('enemy', 2, 0, 0, 251000),)))
        (game / 'map' / 'm0').mkdir(parents=True)
        (game / 'map' / 'm0' / 'c1200.flver').write_bytes(build_flver())
        (game / 'chr').mkdir(parents=True)
        (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(make_chrbnd(build_flver()))
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1400, 'height': 900})
                    cdp = page.context.new_cdp_session(page)
                    cdp.send('Network.enable')
                    cdp.send('Network.setCacheDisabled', {'cacheDisabled': True})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.route('**/api/map/geometry*', hold)
                    page.route('**/api/chr/geometry*', hold)
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    # Map stage: the panel, centered and big, no inline status.
                    page.locator('[data-tab="maps"]').click()
                    page.wait_for_function("state.tab==='maps'", timeout=60000)
                    page.wait_for_function(
                        "document.querySelector('[data-viewport-host] .lex-panel-loading')"
                        " || document.querySelector('[data-viewport-host] .lex-loading-status')"
                        " || document.querySelector('[data-viewport-host] canvas')",
                        timeout=30000)
                    host = '[data-viewport-host]'
                    assert page.locator(f'{host} .lex-panel-loading').count() == 1, \
                        'map stage shows the centered loading panel while geometry loads'
                    assert page.locator(f'{host} .lex-loading-status').count() == 0, \
                        'map stage shows no tiny corner status while geometry loads'
                    width = page.evaluate(
                        "document.querySelector('[data-viewport-host] .lex-panel-loading"
                        " .lex-plugin-loading-pulse').getBoundingClientRect().width")
                    assert width >= 24, f'map pulse is big, got {width}'
                    centers = page.evaluate("""() => {
                      const hostEl = document.querySelector('[data-viewport-host]');
                      const pulseEl = hostEl.querySelector('.lex-panel-loading .lex-plugin-loading-pulse');
                      const hostBox = hostEl.getBoundingClientRect();
                      const pulseBox = pulseEl.getBoundingClientRect();
                      return {host: {x: hostBox.x + hostBox.width / 2, y: hostBox.y + hostBox.height / 2},
                              pulse: {x: pulseBox.x + pulseBox.width / 2, y: pulseBox.y + pulseBox.height / 2}};
                    }""")
                    drift = abs(centers['host']['x'] - centers['pulse']['x'])
                    assert drift < 100, f'map pulse is centered, drifted {drift}px'
                    wait_held(page)
                    page.screenshot(path=str(output / 'ds1-map-loading.png'))
                    release_next()
                    page.wait_for_selector('[data-viewport-host][data-ready="true"]', timeout=60000)
                    assert page.locator(f'{host} .lex-panel-loading').count() == 0, \
                        'map panel clears once the canvas mounts'
                    # MODEL stage: same panel instead of an empty black host.
                    page.evaluate("navigate('npcs','npcs')")
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    row = page.locator('.lex-list-row[data-key="NpcParam:251000"]')
                    row.scroll_into_view_if_needed()
                    row.click()
                    wait_held(page)
                    release_next()
                    page.wait_for_function(
                        "state.row && `${state.row.table}:${state.row.id}` === 'NpcParam:251000'")
                    page.locator('.lex-tabbed-panel [data-subtab="basics"]').click()
                    page.wait_for_function("!document.querySelector('[data-chr-host]')",
                        timeout=30000)
                    page.locator('.lex-tabbed-panel [data-subtab="model"]').click()
                    page.wait_for_function(
                        "document.querySelector('[data-chr-host] .lex-panel-loading')"
                        " || document.querySelector('[data-chr-host] .lex-loading-status')"
                        " || document.querySelector('[data-chr-host] canvas')",
                        timeout=30000)
                    host = '[data-chr-host]'
                    assert page.locator(f'{host} .lex-panel-loading').count() == 1, \
                        'model stage shows the centered loading panel while geometry loads'
                    assert page.locator(f'{host} .lex-loading-status').count() == 0, \
                        'model stage shows no tiny corner status while geometry loads'
                    width = page.evaluate(
                        "document.querySelector('[data-chr-host] .lex-panel-loading"
                        " .lex-plugin-loading-pulse').getBoundingClientRect().width")
                    assert width >= 24, f'model pulse is big, got {width}'
                    wait_held(page)
                    page.screenshot(path=str(output / 'ds1-model-loading.png'))
                    release_next()
                    page.wait_for_selector('[data-chr-host] canvas', timeout=60000)
                    assert page.locator(f'{host} .lex-panel-loading').count() == 0, \
                        'model panel clears once the canvas mounts'
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    while held:
                        try:
                            held.pop(0).continue_()
                        except Exception:
                            pass
                    browser.close()
        finally:
            session.stop()
        print('DS1 viewport loading: map and model stages show the centered panel passed.')


if __name__ == '__main__':
    main()
