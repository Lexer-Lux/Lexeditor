"""Huge enums render a searchable finder, not a dropdown.

With 205 effects in the archive, a monster's passive-effect field shows its
current choice on a finder face; the picker filters as the reader types and
the pick commits like any other edit.
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

KEY = 'spEffectID0'


def main():
    errors = []
    raw = make_archive({'SpEffectParam': list(range(100, 305))})
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-finder-') as temp:
        temp = Path(temp)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(raw)
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
                    page = browser.new_page(viewport={'width': 1100, 'height': 800})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(session.url)
                    page.wait_for_selector('body[data-ds1-ready="true"]')
                    page.locator('[data-tab="enemies"]').click()
                    page.wait_for_function('state.tab==="enemies" && state.row?.table==="NpcParam"')
                    face = page.locator(f'button.ds1-finder-face[data-field-key="{KEY}"]:visible')
                    assert face.count() == 1
                    assert page.evaluate(
                        '[...document.querySelectorAll("select[data-field-key]")]'
                        '.every(node => node.options.length <= 200)')
                    face.scroll_into_view_if_needed()
                    before = page.evaluate(
                        f'state.row.fields.find(item => item.key === "{KEY}").value')
                    face.click()
                    search = page.locator('.lex-choice-popover-search')
                    search.wait_for()
                    assert page.locator('.lex-choice-popover > button').count() > 200
                    target = page.evaluate('''() => {
                      const current = document.querySelector(
                        'button.ds1-finder-face[data-field-key="spEffectID0"]')
                        .querySelector('span').textContent;
                      const labels = [...document.querySelectorAll('.lex-choice-popover > button')]
                        .map(node => node.getAttribute('aria-label'));
                      return labels.find(label => label !== current);
                    }''')
                    assert target, 'picker shows no alternative choice'
                    search.fill(target)
                    choice = page.locator('.lex-choice-popover > button:not([hidden])').first
                    picked = choice.get_attribute('aria-label')
                    wanted = page.evaluate(
                        '''label => Object.entries(state.row.fields.find(item => item.key === "spEffectID0").enum)
                          .find(([, name]) => name === label)[0]''', arg=picked)
                    assert str(before) != str(wanted)
                    choice.click()
                    page.wait_for_function(
                        '(want) => state.pending === 0 && String(state.row.fields'
                        f'.find(item => item.key === "{KEY}").value) === want', arg=str(wanted))
                    assert picked in face.inner_text()
                    assert page.locator('.lex-choice-popover').count() == 0
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
    print('DS1 effect finder: face, searchable picker and commit passed.')


if __name__ == '__main__':
    main()
