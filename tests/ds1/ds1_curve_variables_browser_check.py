"""Stats curves: the bare graph fills the tab with colored variables.

A calculation graph owns its panel with no section header around it;
the plot takes the panel height. Formula roles light with their
families (thresholds orange, values violet, shapes teal) and hovering
a drawer variable highlights its formula atoms and back, like FF8.
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_stats_fixture import make_stats_archive  # noqa: E402
from plugins.ds1.store import RELATIVE, MARKER  # noqa: E402
from plugins.ds1.plugin import DS1Session  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def main():
    errors = []
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-curve-') as temp:
        temp = Path(temp)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_stats_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game),
                              'LEXEDITOR_DS1_PROJECT': str(mod),
                              'LEXEDITOR_NO_MOD': '0', 'LEXEDITOR_MOD_READ_ONLY': '0'})
        try:
            session.start()
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]', timeout=120000)
                    page.wait_for_function(
                        'document.querySelector(".lex-plugin-loading-screen") === null',
                        timeout=60000)
                    page.locator('button[data-tab="stats"]').click()
                    page.wait_for_function(
                        'state.tab==="stats" && state.sub==="curves"'
                        ' && state.rows.length>0 && state.row?.table==="CalcCorrectGraph"'
                        ' && !state.error', timeout=60000)
                    time.sleep(1.0)
                    # No section header between the panel title and the graph.
                    assert page.locator(
                        '.lex-detail-panel-body .lex-detail-section-title').count() == 0
                    fill = page.evaluate('''() => {
                        const body = document.querySelector(
                            '.lex-detail-panel-body');
                        const plot = document.querySelector('.lex-curve-plot');
                        return {body: body.getBoundingClientRect().height,
                                plot: plot.getBoundingClientRect().height};
                    }''')
                    assert fill['plot'] >= fill['body'] - 12, fill
                    # Roles wear family colors on the line and in the drawer.
                    for key, color in (('t', 'rgb(255, 158, 94)'),
                                       ('v', 'rgb(199, 146, 234)'),
                                       ('s', 'rgb(95, 215, 215)')):
                        assert page.locator(
                            f'.lex-curve-math-atom .lex-curve-variable-{key}').count() >= 1, key
                        seen = page.evaluate(
                            '''(key) => getComputedStyle(document.querySelector(
                                `.lex-curve-variable-name.lex-curve-variable-${key}`)).color''',
                            key)
                        assert seen == color, (key, seen)
                    # Drawer -> formula and back.
                    editor = page.locator('.lex-curve-editor')
                    editor.hover()
                    editor.locator(
                        ".lex-curve-variable[data-curve-variable='t']").nth(0).hover()
                    assert editor.locator(
                        '.lex-curve-math-atom .lex-curve-variable-t'
                        '.lex-curve-variable-highlight').count() >= 1
                    editor.locator(
                        '.lex-curve-math-atom .lex-curve-variable-v').nth(0).hover(force=True)
                    assert editor.locator(
                        ".lex-curve-variable[data-curve-variable='v']"
                        ".lex-curve-variable-active").count() >= 1
                    assert not errors, errors
                    print('DS1 curve variables browser check passed')
                finally:
                    browser.close()
        finally:
            session.stop()


if __name__ == '__main__':
    main()
