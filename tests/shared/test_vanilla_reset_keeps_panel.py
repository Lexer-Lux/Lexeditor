"""Right-click reset to vanilla keeps the reader in place.

Resetting a value to vanilla by right-clicking must take the same
scroll-preserving path as clicking the vanilla rail entry, and a value that
already matches vanilla must not trigger the game-owned apply at all (which
rebuilds the panel for no change).
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def _page(play):
    browser = play.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1100, "height": 800})
    page.route("http://fixture/**", lambda r: r.fulfill(
        body="<main></main>", content_type="text/html"))
    page.goto("http://fixture/")
    page.add_style_tag(path=str(ROOT / "ui" / "framework.css"))
    page.add_script_tag(path=str(ROOT / "ui" / "framework.js"))
    page.add_script_tag(content="""
      window.__applyCalls = [];
      window.__model = {amount: 60000};
      const VANILLA = 50000;
      const main = document.querySelector('main');
      main.setAttribute('style', 'height:300px;overflow:auto;');
      window.__render = () => {
        const U = LexeditorUI;
        const top = document.createElement('div');
        top.setAttribute('style', 'height:600px;');
        const input = document.createElement('input');
        input.type = 'number';
        input.value = String(window.__model.amount);
        input.setAttribute('aria-label', 'Amount');
        input.addEventListener('input', e => {
          const v = Number(e.target.value);
          if (Number.isFinite(v)) window.__model.amount = v;
        });
        // A game-owned apply rebuilds the whole view, like FF8's does, and the
        // rebuild resets the reader's scroll, like a list that repages.
        const source = U.provenanceControl({control: input,
          current: () => window.__model.amount, vanilla: VANILLA,
          apply: v => { window.__applyCalls.push(v); window.__model.amount = Number(v);
            document.querySelector('main').scrollTop = 0;
            window.__render(); U.refreshReferences(); }});
        const panel = U.detailPanel({title: 'Amount',
          body: [U.detailField({label: 'Amount', control: source})]});
        const bottom = document.createElement('div');
        bottom.setAttribute('style', 'height:600px;');
        main.replaceChildren(top, panel, bottom);
      };
      window.__render();
    """)
    return browser, page


def _right_click(page):
    page.evaluate("""() => document.querySelector('.lex-detail-field input').dispatchEvent(
      new MouseEvent('contextmenu', {bubbles: true, cancelable: true, button: 2}))""")


def test_modified_value_resets_through_rail_path_and_keeps_scroll():
    with sync_playwright() as play:
        browser, page = _page(play)
        try:
            page.evaluate("() => document.querySelector('main').scrollTop = 500")
            assert page.evaluate("() => document.querySelector('main').scrollTop") == 500
            _right_click(page)
            page.wait_for_timeout(400)
            assert page.evaluate("() => window.__model.amount") == 50000
            assert page.evaluate("() => window.__applyCalls") == [50000]
            assert page.evaluate("() => document.querySelector('main').scrollTop") == 500
            assert page.evaluate(
                "() => document.querySelector('.lex-detail-field input').value") == "50000"
        finally:
            browser.close()


def test_unmodified_value_resets_without_game_apply():
    with sync_playwright() as play:
        browser, page = _page(play)
        try:
            page.evaluate("() => { window.__model.amount = 50000; window.__render(); }")
            page.wait_for_timeout(200)
            assert page.evaluate("() => window.__applyCalls") == []
            _right_click(page)
            page.wait_for_timeout(400)
            assert page.evaluate("() => window.__model.amount") == 50000
            assert page.evaluate("() => window.__applyCalls") == []
        finally:
            browser.close()
