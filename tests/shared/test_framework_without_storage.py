"""The shared UI loads in a page that refuses storage.

The loading screen read sessionStorage at load without a guard. A document
whose storage is refused - sandboxed, embedded, a browser blocking it - threw
there, LexeditorUI was never defined, and every game came up blank. Half the
browser checks failed on exactly that.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


def test_framework_loads_when_storage_is_refused():
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script("""
              for (const name of ['sessionStorage', 'localStorage'])
                Object.defineProperty(window, name, {get() { throw new DOMException('Access is denied', 'SecurityError'); }});
            """)
            page.route("http://fixture/**", lambda route: route.fulfill(
                body='<body><div id="lexeditor-shell"></div><main></main></body>', content_type="text/html"))
            # A game page: the shell host is what makes the loading screen run.
            page.goto("http://fixture/?lexQuote=Hello")
            page.add_script_tag(path=str(ROOT / "ui/framework.js"))
            assert page.evaluate("typeof LexeditorUI") == "object", errors
            assert not [error for error in errors if "Storage" in error or "Access is denied" in error], errors
        finally:
            browser.close()
