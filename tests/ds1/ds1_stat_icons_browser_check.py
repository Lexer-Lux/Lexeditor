"""DS1 HP and stamina take their bar frames, not stat icons.

NpcParam vitals and starting-class vitals map to the menu sheet's real
frames (dark red and dark green boxes, gold outline); the detail shows
the loaded label art, not the vit/end stat glyphs.
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

VITALS = {'hp': 'hp', 'stamina': 'stamina'}


def main():
    assert _FIELD_ICONS[('NpcParam', 'hp')] == 'hp'
    assert _FIELD_ICONS[('NpcParam', 'stamina')] == 'stamina'
    assert _FIELD_ICONS[('CharaInitParam', 'baseHp')] == 'hp'
    assert _FIELD_ICONS[('CharaInitParam', 'baseSp')] == 'stamina'
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-stat-icons-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / texts.RELATIVE).parent.mkdir(parents=True)
        (game / texts.RELATIVE).write_bytes(make_text_archive())
        (game / texts.MENU_RELATIVE).write_bytes(make_menu_archive())
        menu = game / 'menu'
        menu.mkdir(parents=True)
        sheet = make_dds_rgba(336, 608, [(255, 0, 0, 255)] * (336 * 608))
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
                    page.evaluate("navigate('npcs','npcs')")
                    page.wait_for_function("state.tab==='npcs'&&state.rows&&state.rows.length")
                    row = page.locator('.lex-list-row[data-key="NpcParam:251000"]')
                    row.scroll_into_view_if_needed()
                    row.click()
                    page.wait_for_function(
                        "state.row && `${state.row.table}:${state.row.id}` === 'NpcParam:251000'")
                    page.locator('.lex-tabbed-panel [data-subtab="basics"]').click()
                    for field_key, kind in VITALS.items():
                        field = page.locator(f'[data-lex-property="{field_key}"]')
                        page.wait_for_selector(f'[data-lex-property="{field_key}"]')
                        art = field.locator('img.lex-ds1-label-art')
                        assert art.count() == 1, f'{field_key} shows no label art'
                        assert f'name={kind}' in (art.get_attribute('src') or ''), \
                            art.get_attribute('src')
                        page.wait_for_function(
                            '(() => { const img = document.querySelector(\'[data-lex-property="%s"] '
                            'img.lex-ds1-label-art\'); return img && img.naturalWidth > 0; })()' % field_key)
                        assert field.locator('.lex-type-glyph').count() == 0, \
                            f'{field_key} falls back to a stat glyph'
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 stat icons: vitals take their bar frames passed.')


if __name__ == '__main__':
    main()
