"""Detail column counts are manual per subtab: weapons 4 leaves ammo alone.

Each subtab keeps its own manually-set count through the real COLUMNS
control; setting one subtab never changes another, and no shared key
is written. A count saved under the retired shared key moves down
into the open subtab's own key once
(lexeditor:columns:ds1-items -> lexeditor:columns:ds1-items-<sub>:<tab>)
and the shared key goes away.
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
DIVIDER = '.lex-list-detail-divider'
CONTROL = '.lex-list-detail-divider .lex-detail-column-control'
PANEL = '.lex-tabbed-panel [data-subtab="defense"]'
SHARED = 'lexeditor:columns:ds1-items'
WEAPONS = 'lexeditor:columns:ds1-items-weapons:defense'
AMMO = 'lexeditor:columns:ds1-items-ammo:defense'


def summon_columns(page):
    # Summon like a reader: hover the divider strip, not the parked
    # gizmo. Parked it sits under pane content, which intercepts the
    # pointer; the strip is the reveal zone.
    page.locator(DIVIDER).hover()
    page.wait_for_timeout(300)


def column_count(page):
    summon_columns(page)
    page.locator(CONTROL).hover()
    return int(page.locator(f'{CONTROL} .lex-barrel-count').text_content())


def set_columns(page, count):
    summon_columns(page)
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


def column_keys(page):
    return page.evaluate(
        "() => Object.keys(localStorage).filter(k => k.includes('columns')).sort()")


def open_items_weapons(page):
    page.locator('button[data-tab="items"]').click()
    page.wait_for_function('state.tab === "items" && !state.error')
    open_subtab(page, 'weapons')


def check_manual(page):
    open_items_weapons(page)
    before = column_count(page)
    want = before % 6 + 1
    assert set_columns(page, want) == want, (before, want)
    assert column_keys(page) == [WEAPONS], (WEAPONS, column_keys(page))
    open_subtab(page, 'ammo')
    assert AMMO not in column_keys(page), column_keys(page)
    other = want % 6 + 1
    assert set_columns(page, other) == other, (want, other)
    open_subtab(page, 'weapons')
    assert column_count(page) == want, (want, column_count(page))
    open_subtab(page, 'ammo')
    assert column_count(page) == other, (other, column_count(page))
    assert column_keys(page) == [AMMO, WEAPONS], column_keys(page)


def check_migration(page):
    page.evaluate(f"() => localStorage.setItem('{SHARED}', '4')")
    page.reload()
    page.wait_for_selector('body[data-ds1-ready="true"]')
    open_items_weapons(page)
    keys = column_keys(page)
    assert SHARED not in keys, keys
    assert len(keys) == 1 and keys[0].startswith('lexeditor:columns:ds1-items-'), keys
    assert page.evaluate(
        f"() => localStorage.getItem('{keys[0]}')") == '4', keys


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-column-manual-') as folder:
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
                    check_manual(page)
                    if output:
                        page.screenshot(path=str(output / 'ds1-column-manual.png'))
                    assert not errors, errors
                    page.close()
                    fresh = browser.new_page(viewport={'width': 1440, 'height': 900})
                    fresh.on('pageerror', lambda error: errors.append(str(error)))
                    fresh.goto(session.url)
                    fresh.wait_for_selector('body[data-ds1-ready="true"]')
                    check_migration(fresh)
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 column counts stay manual per subtab.')


if __name__ == '__main__':
    main()
