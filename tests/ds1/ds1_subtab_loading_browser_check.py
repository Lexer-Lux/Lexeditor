"""DS1 tab and subtab switches announce a throbber, never stale rows.

Switching tabs (or subtabs within a tab) replaces the old content with
the loading panel synchronously, before the rows arrive. With the rows
held back, the panel is visible and no stale row survives; once
released, the new rows render and the panel clears.
"""
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

held = []


def hold(route, _request):
    held.append(route)


def wait_held(page, timeout=15):
    deadline = time.monotonic() + timeout
    while not held:
        assert time.monotonic() < deadline, 'timed out waiting for a held table fetch'
        page.wait_for_timeout(50)


def release_next():
    held.pop(0).continue_()


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-subtab-loading-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
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
                    page.set_default_timeout(60000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.wait_for_function("state.tab==='items'&&state.rows&&state.rows.length")
                    assert page.locator('#main .lex-list-row').count() > 0
                    page.route(re.compile(r'/api/table\?'), hold)
                    # A tab switch by click: panel at once, stale rows gone.
                    page.locator('[data-tab="npcs"]').click()
                    page.wait_for_selector('#main .lex-panel-loading', timeout=30000)
                    assert page.locator('#main .lex-list-row').count() == 0, \
                        'the old tab rows clear the moment the new tab announces'
                    wait_held(page)
                    release_next()
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    page.wait_for_selector('#main .lex-list-row', timeout=30000)
                    assert page.locator('#main .lex-panel-loading').count() == 0
                    # A subtab switch inside items: same announce, no shell involved.
                    page.evaluate("void navigate('items','weapons')")
                    page.wait_for_selector('#main .lex-panel-loading', timeout=30000)
                    assert page.locator('#main .lex-list-row').count() == 0, \
                        'the old subtab rows clear the moment the new subtab announces'
                    wait_held(page)
                    release_next()
                    page.wait_for_function(
                        "state.tab==='items'&&state.sub==='weapons'&&state.rows&&state.rows.length")
                    page.wait_for_selector('#main .lex-list-row', timeout=30000)
                    assert page.locator('#main .lex-panel-loading').count() == 0
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
        print('DS1 subtab loading: switches announce a throbber, never stale rows passed.')


if __name__ == '__main__':
    main()
