"""Picking a character keeps the characters pane's page, and the wheel wraps it.

Lexer: "every time I click on a different enemy to see its animations it
pushes me back to the very first page in this leftmost panel."
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from hkx_fixture import build_tag0
from tae_fixture import build_anibnd
from plugins.ds1.store import RELATIVE
from plugins.ds1.plugin import DS1Session
from playwright.sync_api import sync_playwright


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-anim-char-page-') as folder:
        temp = Path(folder)
        game = temp / 'game'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        (game / 'chr').mkdir(parents=True)
        anibnd = build_anibnd({'Skeleton.hkx': build_tag0()})
        for index in range(40):
            (game / 'chr' / f'c{index:04d}.anibnd.dcx').write_bytes(anibnd)
        session = DS1Session({'LEXEDITOR_DS1_ROOT': str(game), 'LEXEDITOR_NO_MOD': '1',
                              'LEXEDITOR_MOD_READ_ONLY': '1'})
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
                    page.locator('button[data-tab="animations"]').click()
                    page.wait_for_function('state.tab === "animations" && !state.error')
                    page.wait_for_selector('[data-anim-chars] .lex-list-row')
                    count = page.evaluate('(state.animChars||[]).length')
                    assert count == 40, count
                    page.evaluate("""() => {
                        document.querySelector('[data-anim-chars] [aria-label="Next page"]').click();
                    }""")
                    page.wait_for_function('state.animCharPage === 1')
                    before = page.evaluate('state.animCharId')
                    page.locator('[data-anim-chars] .lex-list-row').first.click()
                    page.wait_for_function(f'state.animCharId !== "{before}"')
                    kept = page.evaluate('state.animCharPage')
                    assert kept == 1, f'characters pane reset to page {kept + 1} on pick'
                    pages = page.evaluate(
                        "Number(document.querySelector('[data-anim-chars] .lex-page-total')"
                        ".textContent)")
                    assert pages > 1, pages
                    last = pages - 1
                    wheel = page.locator('[data-anim-chars] .lex-paged-pane-content')
                    wheel.hover()
                    # Clicking Next past the last page wraps to the first.
                    for _ in range(pages + 1):
                        if page.evaluate('state.animCharPage') == 0:
                            break
                        page.evaluate(
                            'document.querySelector('
                            "'[data-anim-chars] [aria-label=\"Next page\"]').click()")
                        page.wait_for_timeout(120)
                    assert page.evaluate('state.animCharPage') == 0
                    # The wheel turns pages, and wraps past either end.
                    page.mouse.wheel(0, 240)
                    page.wait_for_function('state.animCharPage === 1')
                    page.wait_for_timeout(300)
                    for _ in range(pages + 1):
                        if page.evaluate('state.animCharPage') == 0:
                            break
                        page.mouse.wheel(0, 240)
                        page.wait_for_timeout(300)
                    assert page.evaluate('state.animCharPage') == 0
                    page.wait_for_timeout(300)
                    page.mouse.wheel(0, -240)
                    page.wait_for_function(f'state.animCharPage === {last}')
                    page.wait_for_timeout(300)
                    page.mouse.wheel(0, 240)
                    page.wait_for_function('state.animCharPage === 0')
                    if output:
                        page.screenshot(path=str(output / 'anim-char-page.png'))
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            session.stop()
            assert session.wait_closed()
    print('DS1 animation character page passed.')


if __name__ == '__main__':
    main()
