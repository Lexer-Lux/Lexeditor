"""Bare tab switches return to the tab's own last subtab.

Items -> Ammo, Textures tab, Back: shell history restores the tab by
calling navigate(tab) with no sub, and the previous tab's sub rode along
as the default, failed items validation, and fell back to consumables.
Each tab now remembers its own last subtab instead.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-tab-memory-') as folder:
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
                    page.evaluate("() => navigate('items','ammo')")
                    page.wait_for_function("state.tab==='items'&&state.sub==='ammo'")
                    page.evaluate("() => navigate('textures')")
                    page.wait_for_function("state.tab==='textures'")
                    # Back restores the tab through a bare navigate(tab):
                    # ammo, not the consumables fallback.
                    page.evaluate("window.__lexeditorNavigateHistory(-1)")
                    page.wait_for_function("state.tab==='items'")
                    assert page.evaluate("state.sub") == 'ammo', page.evaluate("state.sub")
                    # And forward returns to textures' own subtab.
                    page.evaluate("window.__lexeditorNavigateHistory(1)")
                    page.wait_for_function("state.tab==='textures'")
                    assert page.evaluate("state.sub") == 'files', page.evaluate("state.sub")
                    # A later subtab becomes the remembered one.
                    page.evaluate("() => navigate('items','armor')")
                    page.wait_for_function("state.sub==='armor'")
                    page.evaluate("() => navigate('textures')")
                    page.wait_for_function("state.tab==='textures'")
                    page.evaluate("window.__lexeditorNavigateHistory(-1)")
                    page.wait_for_function("state.tab==='items'")
                    assert page.evaluate("state.sub") == 'armor', page.evaluate("state.sub")
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 tab subtab memory: bare switches return to the last subtab passed.')


if __name__ == '__main__':
    main()
