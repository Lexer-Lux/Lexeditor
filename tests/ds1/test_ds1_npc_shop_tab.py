"""Each merchant's NPC detail grows a Shop panel tab with their stock.

The male Undead Merchant is npcType 0, so his admission to the NPCs tab
also proves merchants no longer need npcType 2 to be editable. His two
fixture shop lines (real Smithbox names) render with inline price and
stock; the female merchant, with no attributed fixture lines, shows no
Shop tab.
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


def test_merchant_shop_panel_tab():
    errors = []
    raw = make_archive(
        table_ids={
            'NpcParam': [120000, 120100, 251000, 251001, 223000, 321001, 502, 999999],
            'ShopLineupParam': [1100, 1101],
        },
        field_values={
            'ShopLineupParam': {
                1100: {'value': 500, 'sellQuantity': 3},
                1101: {'value': 750, 'sellQuantity': -1},
            },
        })
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-shop-') as temp:
        game, mod = Path(temp) / 'game', Path(temp) / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0',
                              'LEXEDITOR_MOD_READ_ONLY': '0'})
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.evaluate('navigate("npcs", "npcs", "NpcParam:251001")')
                    page.wait_for_function('state.row && state.row.id === 251001', timeout=60000)
                    # A type-0 merchant stands on the NPCs tab with a Shop tab.
                    names = page.evaluate('state.rows.map(row => row.id)')
                    assert 251001 in names, names
                    page.locator('.lex-tabbed-panel [data-subtab="shop"]').click()
                    page.wait_for_function('state.monsterTab === "shop"')
                    lines = page.locator('.lex-detail-panel .lex-detail-field')
                    assert lines.count() == 2, lines.count()
                    assert 'Orange Guidance Soapstone' in lines.nth(0).inner_text()
                    assert 'Repair Powder' in lines.nth(1).inner_text()
                    price = lines.nth(0).locator('input').nth(0)
                    assert price.input_value() == '500'
                    # Price edits commit to the shop line and undo cleanly.
                    price.fill('525')
                    price.press('Tab')
                    page.wait_for_function('state.pending === 0 && fieldHistory.undoStack.length === 1')
                    assert page.evaluate(
                        "fetch('/api/row?table=ShopLineupParam&id=1100&sub=shops')"
                        ".then(r => r.json()).then(j => j.row.fields.find(f => f.key === 'value').value)"
                    ) == 525
                    page.evaluate('fieldHistory.undo()')
                    page.wait_for_function('fieldHistory.undoStack.length === 0')
                    page.wait_for_function(
                        'state.npcShop && state.npcShop.rows[0].value === 500')
                    # The item name opens the full shop line.
                    lines.nth(1).locator('.lex-hoverable').click()
                    page.wait_for_function(
                        'state.tab === "shops" && state.row && state.row.id === 1101', timeout=60000)
                    # No attributed lines, no Shop tab.
                    page.evaluate('navigate("npcs", "npcs", "NpcParam:251000")')
                    page.wait_for_function('state.row && state.row.id === 251000', timeout=60000)
                    assert page.locator('.lex-tabbed-panel [data-subtab="shop"]').count() == 0
                finally:
                    browser.close()
        finally:
            session.stop()
    assert errors == []
