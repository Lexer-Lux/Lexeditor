"""The record search skips empty-slot placeholders: 'none' finds no rows."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive, make_text_archive  # noqa: E402
from plugins.ds1 import texts  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from plugins.ds1.store import MARKER, RELATIVE  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def test_search_skips_empty_slot_placeholders(tmp_path):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_archive(
        table_ids={'EquipParamGoods': [100, 101]},
        field_values={'EquipParamGoods': {101: {'goodsType': 0}}}))
    (game / texts.RELATIVE).parent.mkdir(parents=True)
    (game / texts.RELATIVE).write_bytes(make_text_archive(
        names={'EquipParamGoods': {100: 'Fixture Stone', 101: 'Fixture Key'},
               'EquipParamWeapon': {100: 'Fixture Sword'}}))
    mod.mkdir()
    (mod / MARKER).touch()
    session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                          'LEXEDITOR_MOD_READ_ONLY': '0', 'LEXEDITOR_NO_MOD': '0'})
    try:
        session.start()
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                page.wait_for_selector('[data-lex-bottom-search="ds1-records-search"]',
                                       timeout=60000)
                page.wait_for_function(
                    "!document.documentElement.classList.contains('lex-loading-live')",
                    timeout=30000)
                total = page.evaluate('state.rows.length')
                assert total > 1
                page.wait_for_function(
                    "document.querySelectorAll('.lex-paged-list-detail "
                    ".lex-list-row[data-key]').length === " + str(total),
                    timeout=15000)
                box = page.locator('[data-lex-bottom-search="ds1-records-search"]')
                names = ("[...document.querySelectorAll('.lex-paged-list-detail .lex-list-row[data-key]')].map(row => "
                         "row.innerText.split('\\n')[0])")
                box.fill('none')
                page.wait_for_function('state.query === "none"', timeout=15000)
                page.wait_for_function(
                    "document.querySelectorAll('.lex-paged-list-detail .lex-list-row[data-key]').length === 0", timeout=15000)
                box.fill('stone')
                page.wait_for_function('state.query === "stone"', timeout=15000)
                page.wait_for_function(
                    "document.querySelectorAll('.lex-paged-list-detail .lex-list-row[data-key]').length === 1", timeout=15000)
                assert page.evaluate(names) == ['Fixture Stone']
                # fill('') never fires input; clear the way a reader does.
                box.click()
                box.press('ControlOrMeta+a')
                box.press('Backspace')
                page.wait_for_function('state.query === ""', timeout=15000)
                page.wait_for_function(
                    f"document.querySelectorAll('.lex-paged-list-detail .lex-list-row[data-key]').length === {total}",
                    timeout=15000)
            finally:
                browser.close()
    finally:
        session.stop()
        assert session.wait_closed()
