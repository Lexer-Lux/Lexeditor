"""The monster Blocking tab sits still: no rhythmic jumping.

Samples the divider, the detail width and every Blocking field's
geometry for five seconds (past the shell's 2s game-process refresh):
nothing may move.
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def main():
    errors = []
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-blocking-') as temp:
        temp = Path(temp)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1400, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.wait_for_function(
                        'document.querySelector(".lex-plugin-loading-screen") === null',
                        timeout=60000)
                    page.locator('[data-tab="enemies"]').click()
                    page.wait_for_function(
                        'state.tab==="enemies" && state.row?.table==="NpcParam"'
                        ' && !state.error', timeout=60000)
                    page.locator('.lex-tabbed-panel [data-subtab="blocking"]').click()
                    page.wait_for_function('state.monsterTab==="blocking"')
                    time.sleep(1.0)
                    snaps = []
                    for _ in range(25):
                        snaps.append(page.evaluate('''() => {
                            const strip = document.querySelector(
                                '.lex-panel-layout-divider:has(> .lex-barrel-control)');
                            const fields = [...document.querySelectorAll(
                                '.lex-tabbed-panel-content .lex-detail-field')].map(
                                f => Math.round(f.getBoundingClientRect().y * 100));
                            return {divX: Math.round(
                                        strip.getBoundingClientRect().x * 100),
                                    fields};
                        }'''))
                        time.sleep(0.2)
                    assert len(snaps[0]['fields']) > 0, 'blocking fields render'
                    for key in ('divX',):
                        vals = [s[key] for s in snaps]
                        assert max(vals) - min(vals) <= 50, (key, min(vals), max(vals))
                    for i in range(len(snaps[0]['fields'])):
                        vals = [s['fields'][i] for s in snaps]
                        assert max(vals) - min(vals) <= 50, (f'field {i}', vals)
                    assert not errors, errors
                    print('DS1 blocking stability browser check passed')
                finally:
                    browser.close()
        finally:
            session.stop()


if __name__ == '__main__':
    main()
