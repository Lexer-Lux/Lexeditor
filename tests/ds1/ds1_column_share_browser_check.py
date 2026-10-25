"""Detail column counts share across subtabs: weapons 4 means ammo 4.

Lexer: "under the defense panel tab under the weapons subtab there are
four columns, under ammo there's three, why?" One count per tab now,
through the real COLUMNS control; a single shared key persists it.
Synthetic GameParam only: row 100 is a weapon, 101 and 102 are ammo.
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

STRIP = '.lex-subtab-bar:not(.lex-tabbed-panel .lex-subtab-bar) [data-subtab="{}"]'
CONTROL = '.lex-list-detail-divider .lex-detail-column-control'
PANEL = '.lex-tabbed-panel [data-subtab="defense"]'


def column_count(page):
    page.locator(CONTROL).hover()
    return int(page.locator(f'{CONTROL} .lex-barrel-count').text_content())


def set_columns(page, count):
    control = page.locator(CONTROL)
    control.hover()
    for _ in range(8):
        current = int(control.locator('.lex-barrel-count').text_content())
        if current == count:
            break
        control.locator('.lex-barrel-increase' if current < count
                        else '.lex-barrel-decrease').click()
        page.wait_for_timeout(250)
    page.wait_for_timeout(300)
    return column_count(page)


def open_subtab(page, sub):
    page.locator(STRIP.format(sub)).click()
    page.wait_for_function('(sub) => state.sub === sub && state.row && !state.error', arg=sub)
    page.locator(PANEL).click()
    page.wait_for_timeout(300)


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-column-share-') as folder:
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
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('button[data-tab="items"]').click()
                    page.wait_for_function('state.tab === "items" && !state.error')
                    open_subtab(page, 'weapons')
                    before = column_count(page)
                    want = before % 6 + 1
                    assert set_columns(page, want) == want, (before, want)
                    open_subtab(page, 'ammo')
                    assert column_count(page) == want, want
                    keys = page.evaluate(
                        "() => Object.keys(localStorage).filter(k => k.includes('columns'))")
                    assert keys == ['lexeditor:columns:ds1-items'], keys
                    if output:
                        page.screenshot(path=str(output / 'ds1-column-share.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 column counts share across subtabs.')


if __name__ == '__main__':
    main()
