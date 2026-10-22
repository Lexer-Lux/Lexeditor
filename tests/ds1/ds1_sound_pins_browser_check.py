"""Sound pins never duplicate or empty their columns.

Lexer: pinning Bank made a second, empty Bank column next to the built-in
one, and the built-in never showed as pinned. Same for Length.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from ds1_sound_fixture import bank_bytes
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

HEADS = ("[...document.querySelectorAll('.lex-barrelled-master "
         ".lex-column-list-head-cell')].map(c=>c.dataset.columnKey)")


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-sound-pins-') as folder:
        game = Path(folder) / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'sound').mkdir(parents=True)
        (game / 'sound' / 'frpg_main.fsb').write_bytes(bank_bytes())
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1'})
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
                    page.locator('button[data-tab="sound"]').click()
                    page.wait_for_function('state.tab === "sound" && !state.error')
                    page.locator('[data-subtab="music"]').click()
                    page.wait_for_function('state.sub === "music" && state.rows.length === 2 && !state.error')
                    page.wait_for_selector('.lex-barrelled-master .lex-list-row')
                    assert page.evaluate(HEADS) == ['name', 'bank', 'length']
                    for key in ('bank', 'length'):
                        page.locator(f'.lex-detail-field[data-lex-layout-field="{key}"] '
                                     '.lex-column-pin').click()
                        page.wait_for_timeout(400)
                        # No second column: the pin matches the built-in.
                        assert page.evaluate(HEADS) == ['name', 'bank', 'length'], key
                        pin = page.locator(f'.lex-detail-field[data-lex-layout-field="{key}"] '
                                           '.lex-column-pin')
                        assert pin.get_attribute('aria-pressed') == 'true'
                    cells = page.locator('.lex-list-row[data-key] [data-column-key="bank"]').evaluate_all(
                        'nodes=>nodes.map(n=>n.innerText.trim())')
                    assert cells == ['sound/frpg_main.fsb'] * 2, cells
                    lengths = page.locator('.lex-list-row[data-key] [data-column-key="length"]').evaluate_all(
                        'nodes=>nodes.map(n=>n.innerText.trim())')
                    assert all(text and ':' in text for text in lengths), lengths
                    # Size has no built-in column: its pin adds one with values.
                    page.locator('.lex-detail-field[data-lex-layout-field="size"] '
                                 '.lex-column-pin').click()
                    page.wait_for_timeout(400)
                    assert page.evaluate(HEADS) == ['name', 'bank', 'length', 'pin:size']
                    sizes = page.locator('.lex-list-row[data-key] [data-column-key="pin:size"]').evaluate_all(
                        'nodes=>nodes.map(n=>n.innerText.trim())')
                    assert sizes == ['1,062'] * 2, sizes
                    if output:
                        page.screenshot(path=str(output / 'sound-pins.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 sound pins passed.')


if __name__ == '__main__':
    main()
