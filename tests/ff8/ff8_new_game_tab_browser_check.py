"""The FF8 New Game tab stays hidden unless its plugin setting is on.

Starting data is a niche page, so the tab is behind the FF8-only
showNewGame editor setting, off by default. The Information page carries
the toggle; flipping it saves and reloads with the tab shown or hidden.
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_TEMPDIR = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-new-game-check-")
os.environ["LEXEDITOR_FF8_EDITOR_SETTINGS"] = str(
    Path(_TEMPDIR.name) / "ff8-editor.json")

from plugins.ff8.server import create_server
from playwright.sync_api import sync_playwright

BOOTED = "typeof state==='object' && !state.booting && !state.bootFailed"
INFO_TITLE = "Open FF8 setup and runtime information"
TOGGLE_LABEL = "Show New Game tab"


def boot(page, server):
    page.goto(f"http://127.0.0.1:{server.server_port}/")
    page.wait_for_function(BOOTED, timeout=90000)


def main():
    server = create_server(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            # Default: the setting is off, so the tab is absent.
            boot(page, server)
            assert page.locator('nav [data-tab="starting"]').count() == 0
            assert page.locator('nav [data-tab="settings"]').count() == 1

            # The Information page carries the toggle, off by default.
            page.locator('#plugin-info').click()
            toggle = page.locator(f'[aria-label="{TOGGLE_LABEL}"]')
            toggle.wait_for()
            assert not toggle.is_checked(), "New Game toggle must default to off"

            # Turning it on reloads with the tab present. A plain click: the
            # page navigates on toggle, which check()/uncheck() outlive.
            toggle.click()
            page.wait_for_function(BOOTED, timeout=90000)
            assert page.locator('nav [data-tab="starting"]').count() == 1

            # Turning it off again hides the tab.
            page.locator('#plugin-info').click()
            toggle = page.locator(f'[aria-label="{TOGGLE_LABEL}"]')
            toggle.wait_for()
            assert toggle.is_checked(), "toggle did not persist across reload"
            toggle.click()
            page.wait_for_function(BOOTED, timeout=90000)
            assert page.locator('nav [data-tab="starting"]').count() == 0

            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        _TEMPDIR.cleanup()
    print("New Game tab: hidden by default, shown while its setting is on.")


if __name__ == "__main__":
    main()
