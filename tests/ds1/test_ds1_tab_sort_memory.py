"""A column click sorts only its own tab; every tab opens alphabetical.

The DS1 record lists used to share one global sort, so sorting Items by a
column re-sorted Drops too, and entering Drops showed that other tab's
order instead of the alphabetical default. Each tab now keeps its own
order, alphabetical until the reader picks one.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

MASTER_ROWS = ("()=>[...document.querySelectorAll("
               "'.lex-barrelled-master .lex-column-list .lex-list-row')]"
               ".map(row=>row.innerText.split('\\n')[0]).filter(name=>name && name!=='\u200b')")


def test_column_sort_stays_in_its_own_tab():
    errors = []
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-sort-') as temp:
        game, mod = Path(temp) / 'game', Path(temp) / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        # Three consumables and three lots, all distinctly named.
        (game / RELATIVE).write_bytes(make_archive(field_values={
            'EquipParamGoods': {101: {'goodsType': 0}, 102: {'goodsType': 0}}}))
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.wait_for_function('state.tab==="items" && state.rows.length>=2')
                    page.wait_for_function("document.querySelectorAll('.lex-barrelled-master .lex-list-row').length>=2")
                    before = page.evaluate(MASTER_ROWS)
                    assert len(before) >= 2 and len(set(before)) >= 2, before
                    assert before == sorted(before), before
                    page.locator('.lex-barrelled-master [data-column-key="name"] button').click()
                    page.wait_for_function('state.sorts["items-consumables"]?.dir===-1')
                    flipped = page.evaluate(MASTER_ROWS)
                    assert flipped[0] == before[-1], (before, flipped)
                    page.locator('[data-tab="drops"]').click()
                    page.wait_for_function('state.tab==="drops" && state.rows.length>=2')
                    page.wait_for_function("document.querySelectorAll('.lex-barrelled-master .lex-list-row').length>=2")
                    assert page.evaluate('state.sorts["drops-drops"] ?? null') is None
                    drops = page.evaluate(MASTER_ROWS)
                    assert len(drops) >= 2, drops
                    assert drops == sorted(drops), drops
                    page.locator('[data-tab="items"]').click()
                    page.wait_for_function('state.tab==="items" && state.rows.length>=2')
                    page.wait_for_function("document.querySelectorAll('.lex-barrelled-master .lex-list-row').length>=2")
                    assert page.evaluate('state.sorts["items-consumables"].dir') == -1
                    assert page.evaluate(MASTER_ROWS)[0] == before[-1]
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
