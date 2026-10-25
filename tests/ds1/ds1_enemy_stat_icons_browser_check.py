"""DS1 enemy vitals and poise take game label art, not fallback glyphs.

The enemy Basics tab shows HP, MP, Stamina and Poise labels; each takes
the menu sheet's own cell through /api/label (the HP/MP/Stamina bar
frames and the armor screen's poise icon). A label that falls back to
the shared pill/line glyph (.lex-type-glyph) means its art failed to
load: a kind-name mismatch, an endpoint error, or a missing cell.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from drb_fixture import make_dcx
from ds1_fixture import make_archive
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

# Enemy detail field key -> /api/label kind.
LABELS = {'hp': 'hp', 'mp': 'mp', 'stamina': 'stamina',
          'superArmorDurability': 'poise'}


def main(output=None):
    if output is not None:
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-enemy-stat-icons-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        menu = game / 'menu'
        menu.mkdir(parents=True)
        sheet = make_dds_rgba(512, 1024, [(255, 0, 0, 255)] * (512 * 1024))
        (menu / 'menu_0.tpf.dcx').write_bytes(make_dcx(make_tpf([('Menu04_2', sheet)])))
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        errors = []
        statuses = {}
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1400, 'height': 900})
                    page.set_default_timeout(60000)
                    page.on('pageerror', lambda error: errors.append(str(error)))

                    def note(response):
                        url = response.url
                        if '/api/label?' in url:
                            statuses[url.rsplit('name=', 1)[-1]] = response.status

                    page.on('response', note)
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.locator('[data-tab="enemies"]').click()
                    page.wait_for_function(
                        'state.tab==="enemies" && state.row?.table==="NpcParam" && !state.error')
                    page.locator('.lex-tabbed-panel [data-subtab="basics"]').click()
                    page.wait_for_function('state.monsterTab==="basics"')
                    seen = {}
                    for field_key, kind in LABELS.items():
                        field = page.locator(f'[data-lex-property="{field_key}"]')
                        for _ in range(8):
                            if field.count() and field.first.is_visible():
                                break
                            following = page.locator(
                                '.lex-tabbed-panel .lex-tweaks-pages').get_by_role(
                                'button', name='Next page', exact=True)
                            assert following.count() and following.is_enabled(), \
                                f'{field_key} never shown'
                            following.click()
                        else:
                            raise AssertionError(f'{field_key} never shown')
                        art = field.locator('img.lex-ds1-label-art')
                        assert art.count() == 1, f'{field_key} shows no label art'
                        assert f'name={kind}' in (art.get_attribute('src') or ''), \
                            art.get_attribute('src')
                        page.wait_for_function(
                            '(() => { const img = document.querySelector(\'[data-lex-property="%s"] '
                            'img.lex-ds1-label-art\'); return img && img.naturalWidth > 0; })()' % field_key)
                        glyphs = field.locator('.lex-type-glyph').count()
                        assert glyphs == 0, f'{field_key} falls back to a stat glyph'
                        assert field.first.get_attribute('data-lex-icon') == kind, \
                            (field_key, field.first.get_attribute('data-lex-icon'))
                        seen[field_key] = kind
                    assert seen == LABELS, seen
                    for kind in set(LABELS.values()):
                        assert statuses.get(kind) == 200, (kind, statuses)
                    shot = (output / 'enemy-stat-icons.png') if output else (
                        Path(tempfile.gettempdir()) / 'lexeditor-dev' / 'enemy-stat-icons.png')
                    shot.parent.mkdir(parents=True, exist_ok=True)
                    first = page.locator(
                        '.lex-tabbed-panel .lex-tweaks-pages').get_by_role(
                        'button', name='First page', exact=True)
                    if first.count() and first.is_enabled():
                        first.click()
                    page.locator('.lex-detail-panel').screenshot(path=str(shot))
                    assert not errors, f'page errors: {errors[:3]}'
                finally:
                    browser.close()
        finally:
            session.stop()
        print(json.dumps({'labels': seen, 'labelStatus': statuses,
                          'shot': str(shot), 'browserErrors': errors}))


def test_enemy_stat_icons():
    main()


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
