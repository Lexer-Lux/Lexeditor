"""DS1 load bands: Add/Delete wear the shared header-button style.

The band header buttons are boxed lex-header-icon buttons with icon
glyphs and hover titles, like every other detail header, while their
accessible names stay put so the split and merge forms open as before.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_native_fixture import make_native_archive
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory(prefix='ds1-band-buttons-') as folder:
        root = Path(folder)
        game, mod = root / 'game', root / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_native_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        (root / 'library').mkdir()
        env = {'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
               'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0',
               'LEXEDITOR_DS1_MODS_ROOT': str(root / 'library')}
        session = DS1Session(env)
        errors = []
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.set_default_timeout(60000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url, wait_until='domcontentloaded')
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.get_by_text('Misc.', exact=True).first.click()
                    page.wait_for_function('state.tab==="misc" && state.row && !state.error')
                    page.locator('[data-subtab="encumbrance"]').click()
                    page.wait_for_function(
                        'state.tab==="misc" && state.sub==="encumbrance" && state.row'
                        ' && state.row.id===1001 && !state.error')
                    for action, name in (('add', 'Add band'), ('delete', 'Delete band')):
                        button = page.locator(f'[data-band-action="{action}"]')
                        assert button.count() == 1
                        assert 'lex-header-icon' in (button.get_attribute('class') or '')
                        assert button.locator('svg').count() == 1
                        assert button.get_attribute('aria-label') == name
                        assert (button.get_attribute('data-lex-title') or '').strip() != ''
                        box = button.evaluate("""n => { const style = getComputedStyle(n);
                            const rect = n.getBoundingClientRect();
                            return {background: style.backgroundColor, border: style.borderStyle,
                                    width: rect.width, height: rect.height}; }""")
                        assert box['background'] != 'rgba(0, 0, 0, 0)', box
                        assert box['border'] != 'none', box
                        assert (box['width'], box['height']) == (28, 28), box
                    # The named forms still open from the icon buttons.
                    page.get_by_role('button', name='Add band', exact=True).click()
                    page.get_by_label('Split at (%)', exact=True).wait_for()
                    page.get_by_role('button', name='Cancel', exact=True).click()
                    page.wait_for_function('state.bandForm===null && state.row.id===1001')
                    page.get_by_role('button', name='Delete band', exact=True).click()
                    page.get_by_label('Merge into', exact=True).wait_for()
                    page.get_by_role('button', name='Cancel', exact=True).click()
                    page.wait_for_function('state.bandForm===null && state.row.id===1001')
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
        print('DS1 band header buttons passed.')


if __name__ == '__main__':
    main()
