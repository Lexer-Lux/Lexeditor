"""Header buttons wear the finder look; the finder is a 1:1 row square.

Detail header buttons show the finder's full-strength icon on the
near-black box with the dim bronze border (never the loud border with
a dimmed icon). A thing-finder button is square and fills its row:
26px beside a value box, expanded in a tall row like the monster AI
header.
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from plugins.ds1.formats import ItemDocument  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def style(page, selector):
    return page.evaluate('''(sel) => { const el = document.querySelector(sel);
        const cs = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return {bg: cs.backgroundColor, border: cs.borderColor,
                opacity: cs.opacity, color: cs.color,
                w: rect.width, h: rect.height}; }''', arg=selector)


def main():
    errors = []
    document = ItemDocument(make_archive({'EquipParamGoods': [100, 101, 102, 103]}))
    raw = document.export()
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-btns-') as temp:
        temp = Path(temp)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
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
                    page.wait_for_function('state.pending === 0', timeout=60000)
                    page.locator('.lex-list-row[data-key="EquipParamGoods:100"]').click()
                    page.wait_for_function(
                        '`${state.row.table}:${state.row.id}` === "EquipParamGoods:100"')
                    tabs = page.locator('.lex-tabbed-panel [data-subtab]')
                    for index in range(tabs.count()):
                        if page.locator('.ds1-find-reference:visible').count():
                            break
                        tab_id = tabs.nth(index).get_attribute('data-subtab')
                        tabs.nth(index).click()
                        page.wait_for_function('(id)=>state.itemTab===id', arg=tab_id)
                    finder = style(page, '.ds1-find-reference')
                    header = style(
                        page, '.lex-detail-panel-actions > .lex-header-icon')
                    for key in ('bg', 'border', 'opacity', 'color'):
                        assert header[key] == finder[key], (key, header, finder)
                    assert abs(finder['w'] - finder['h']) <= 0.5, finder
                    assert abs(finder['h'] - 26) <= 1, finder
                    # The tall monster AI row grows the same button square.
                    page.locator('[data-tab="enemies"]').click()
                    page.wait_for_function(
                        'state.tab==="enemies" && state.row?.table==="NpcParam"'
                        ' && !state.error', timeout=60000)
                    page.locator('.lex-tabbed-panel [data-subtab="ai"]').click()
                    page.wait_for_function('state.monsterTab==="ai"')
                    time.sleep(0.5)
                    grown = page.evaluate('''() => {
                        const el = document.querySelector(
                            '.lex-tabbed-panel-content .lex-thing-finder');
                        if (!el) return null;
                        const rect = el.getBoundingClientRect();
                        const row = el.parentElement.getBoundingClientRect();
                        return {w: rect.width, h: rect.height, rowH: row.height};
                    }''')
                    assert grown is not None, 'AI row finder renders'
                    assert abs(grown['w'] - grown['h']) <= 0.5, grown
                    assert grown['h'] > 26, grown
                    assert abs(grown['h'] - grown['rowH']) <= 1, grown
                    assert not errors, errors
                    print('DS1 button unify browser check passed')
                finally:
                    browser.close()
        finally:
            session.stop()


if __name__ == '__main__':
    main()
