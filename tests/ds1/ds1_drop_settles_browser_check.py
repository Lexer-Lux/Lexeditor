"""A section drop lands fast and the page settles: no wedge.

Fitting every shared-lane label alone ran the whole scope sweep per label
(quadratic), so each property drop cost hundreds of milliseconds and dense
details froze for seconds per drag. Each scope now fits once per frame.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_stats_fixture import make_stats_archive
from plugins.ds1.store import RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright

COLUMNS = """() => [...document.querySelectorAll('.lex-tweak-column')].map(
    column => [...column.querySelectorAll(
        ':scope > .lex-detail-section > .lex-detail-section-title')].length)"""


def main():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-drop-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_stats_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 2048, 'height': 1152})
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.locator('button[data-tab="stats"]').click()
                    page.locator('[data-subtab="starting-classes"]').click()
                    page.wait_for_function('state.sub === "starting-classes" && state.row && '
                                           'state.row.table === "CharaInitParam" && !state.error',
                                           timeout=60000)
                    page.wait_for_timeout(800)
                    assert page.evaluate('document.querySelectorAll(".lex-detail-field").length') > 40
                    page.evaluate("dispatchEvent(new CustomEvent('lexeditor-settings-changed',"
                                  "{detail:{developerMode:true}}))")
                    page.evaluate("""() => {
                        window.__long = [];
                        new PerformanceObserver(list => {
                            for (const entry of list.getEntries())
                                window.__long.push(Math.round(entry.duration));
                        }).observe({entryTypes: ['longtask']});
                    }""")
                    before = page.evaluate(COLUMNS)
                    assert len(before) >= 2, before
                    page.drag_and_drop('.lex-detail-section-title >> nth=0',
                                       '.lex-tweak-column >> nth=-1')
                    page.wait_for_timeout(500)
                    after = page.evaluate(COLUMNS)
                    assert after != before, (before, after)
                    fell = page.evaluate('window.__long')
                    assert not fell or max(fell) < 1500, fell
                    page.evaluate('window.__long = []')
                    page.wait_for_timeout(3000)
                    assert page.evaluate('window.__long') == [], page.evaluate('window.__long')
                    overflow = page.evaluate("""() => [...document.querySelectorAll(
                        'main .lex-detail-field')].filter(field => field.offsetParent).filter(field => {
                        const label = field.querySelector(':scope > .lex-detail-field-label');
                        if (!label) return false;
                        return label.getBoundingClientRect().right >
                            field.getBoundingClientRect().right + 1;
                    }).length""")
                    assert overflow == 0, overflow
                    print('DS1 drop settles passed.')
                finally:
                    browser.close()
        finally:
            session.stop()


if __name__ == '__main__':
    main()
