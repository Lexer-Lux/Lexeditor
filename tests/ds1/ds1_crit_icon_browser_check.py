"""DS1 Critical Hit takes the menu sheet's crit glyph, not a bare label.

EquipParamWeapon.throwAtkRate maps to the 'critical' label art; the
weapons Properties tab shows the loaded /api/label art beside Critical
Hit, with no fallback stat glyph.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from drb_fixture import make_dcx
from ds1_fixture import make_archive, make_menu_archive, make_text_archive
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1 import texts
from plugins.ds1.formats import _FIELD_ICONS
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    assert _FIELD_ICONS[('EquipParamWeapon', 'throwAtkRate')] == 'critical'
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-crit-icon-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
        menu = game / 'menu'
        menu.mkdir(parents=True)
        sheet = make_dds_rgba(512, 1024, [(255, 0, 0, 255)] * (512 * 1024))
        (menu / 'menu_0.tpf.dcx').write_bytes(make_dcx(make_tpf([('Menu04_2', sheet)])))
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
                    strip = '.lex-subtab-bar:not(.lex-tabbed-panel .lex-subtab-bar) [data-subtab]'
                    page.locator(strip + '[data-subtab="weapons"]').click()
                    page.wait_for_function('state.sub==="weapons" && state.row && !state.error')
                    page.locator('.lex-tabbed-panel [data-subtab="properties"]').click()
                    field = page.locator('[data-lex-property="throwAtkRate"]')
                    page.wait_for_selector('[data-lex-property="throwAtkRate"]')
                    art = field.locator('img.lex-ds1-label-art')
                    assert art.count() == 1, 'Critical Hit shows no label art'
                    assert 'name=critical' in (art.get_attribute('src') or ''), \
                        art.get_attribute('src')
                    page.wait_for_function(
                        '(() => { const img = document.querySelector('
                        '\'[data-lex-property="throwAtkRate"] img.lex-ds1-label-art\');'
                        ' return img && img.naturalWidth > 0; })()')
                    assert field.locator('.lex-type-glyph').count() == 0, \
                        'Critical Hit falls back to a stat glyph'
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 crit icon: Critical Hit takes the crit glyph passed.')


if __name__ == '__main__':
    main()
