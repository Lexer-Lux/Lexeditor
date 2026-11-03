"""DS1 Effects: the effect detail uses panel tabs, one per SpEffect section."""
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_effects_fixture import make_effects_archive
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright
def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-effect-tabs-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_effects_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        (game.parent / 'library').mkdir(exist_ok=True)
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0',
                              'LEXEDITOR_DS1_MODS_ROOT': str(game.parent / 'library')})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=60000)
                    page.wait_for_selector('.lex-plugin-loading-screen', state='detached')
                    page.locator('[data-tab="effects"]').click()
                    page.wait_for_function("state.tab==='effects' && state.row?.table==='SpEffectParam'")
                    tabs = page.locator('.lex-detail .lex-tabbed-panel [data-subtab]')
                    names = tabs.evaluate_all('nodes=>nodes.map(n=>n.dataset.subtab)')
                    for want in ('timing', 'vitals', 'offense', 'defense',
                                 'immunity', 'move', 'links', 'gear',
                                 'covenants', 'other', 'locked', 'usage'):
                        assert want in names, (want, names)
                    assert len(set(names)) == len(names), names
                    # One tab on screen: switching tabs swaps the fields, and the
                    # tab is the header, so no section title repeats it.
                    page.locator('.lex-detail .lex-tabbed-panel [data-subtab="offense"]').click()
                    page.wait_for_function("state.effectTab==='offense'")
                    assert page.locator('[data-field-key="poizonAttackPower"]:visible').count() == 1
                    assert page.locator('[data-field-key="maxHpRate"]:visible').count() == 0
                    page.locator('.lex-detail .lex-tabbed-panel [data-subtab="vitals"]').click()
                    page.wait_for_function("state.effectTab==='vitals'")
                    assert page.locator('[data-field-key="maxHpRate"]:visible').count() == 1
                    assert page.locator('[data-field-key="poizonAttackPower"]:visible').count() == 0
                    assert page.locator('.lex-detail .lex-tabbed-panel .lex-detail-section-title').count() == 0
                    pager = page.locator('.lex-detail .lex-tabbed-panel .lex-tweaks-pages button:enabled')
                    assert pager.count() == 0, pager.evaluate_all('nodes=>nodes.map(n=>n.textContent)')
                    page.screenshot(path=str(Path(tempfile.gettempdir()) / 'lex-ds1-effect-tabs.png'))
                finally:
                    browser.close()
        finally:
            session.stop()
        print('DS1 effect panel tabs: one tab per section passed.')
if __name__ == '__main__':
    main()
