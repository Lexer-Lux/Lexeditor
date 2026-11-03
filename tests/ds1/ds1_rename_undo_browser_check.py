"""A record rename pushes undo; the toolbar buttons take it back.

Renaming an item enables Undo; Undo restores the old name and Redo
reapplies the new one. Before the fix the rename left the history
stack empty, so the undo button sat dead after every rename.
Synthetic fixtures only, in a writable scratch mod.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from plugins.ds1 import texts
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-rename-undo-') as folder:
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
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    strip = '.lex-subtab-bar:not(.lex-tabbed-panel .lex-subtab-bar) [data-subtab]'
                    page.locator(strip + '[data-subtab="consumables"]').click()
                    page.wait_for_function(
                        'state.sub==="consumables" && state.row && !state.pending',
                        timeout=120000)
                    renamed = page.evaluate('state.row.id')
                    before = page.evaluate('state.row.name')
                    assert page.locator('#global-undo').is_disabled()
                    cell = page.locator(
                        f'.lex-list-row[data-key$="{renamed}"] [data-column-key="name"]').first
                    cell.click()
                    page.wait_for_timeout(150)
                    cell = page.locator(
                        f'.lex-list-row[data-key$="{renamed}"] [data-column-key="name"]').first
                    cell.dblclick()
                    editor = page.locator('.lex-cell-editing input')
                    editor.fill('Renamed Stone')
                    editor.press('Enter')
                    page.wait_for_function(
                        '!state.pending && state.row.name==="Renamed Stone"', timeout=60000)
                    assert not page.locator('#global-undo').is_disabled(), \
                        'undo stays dead after a rename'
                    page.locator('#global-undo').click()
                    page.wait_for_function(
                        '!state.pending && state.row.name===%r' % before, timeout=60000)
                    assert page.locator('.lex-detail-panel-name').first.inner_text() == before
                    assert not page.locator('#global-redo').is_disabled(), \
                        'redo stays dead after an undo'
                    page.locator('#global-redo').click()
                    page.wait_for_function(
                        '!state.pending && state.row.name==="Renamed Stone"', timeout=60000)
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 rename undo passed.')


if __name__ == '__main__':
    main()
