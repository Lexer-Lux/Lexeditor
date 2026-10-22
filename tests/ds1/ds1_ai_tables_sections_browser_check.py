"""DS1 AI tables: think properties grouped into labeled categories.

A think record's detail shows its fields under seven category sections
in a fixed order instead of one Properties pile, and each category
holds its own fields.
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

CATEGORIES = ['Logic & goals', 'Battle distances', 'Return home', 'Senses',
              'Call for help', 'Team tactics', 'Movement']
SPOT = {'Battle distances': 'nearDist', 'Senses': 'eye_dist', 'Movement': 'disablePathMove'}


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-ai-tables-') as folder:
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
                    page.evaluate("navigate('ai','ai')")
                    page.wait_for_function("state.tab==='ai'&&state.rows&&state.rows.length")
                    row = page.locator('.lex-list-row[data-key="NpcThinkParam:100"]')
                    row.scroll_into_view_if_needed()
                    row.click()
                    page.wait_for_function(
                        "state.row && `${state.row.table}:${state.row.id}` === 'NpcThinkParam:100'")
                    titles = page.locator(
                        '.lex-detail-section-title-text').all_text_contents()
                    order = [title for title in titles if title in CATEGORIES]
                    assert order == CATEGORIES, titles
                    for category, field in SPOT.items():
                        section = page.locator(
                            f'.lex-detail-section:has(.lex-detail-section-title-text:text-is("{category}"))')
                        assert section.locator(f'[data-lex-property="{field}"]').count() >= 1, \
                            f'{field} sits under {category}'
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 AI tables: think properties grouped into categories passed.')


if __name__ == '__main__':
    main()
