"""FF8's Tweaks page is the shared one, with ReShade on a subtab of its own.

Without a desktop host there is no ReShade for players, so no subtab; with a
host snapshot the shared page adds the subtab and renders the shared RESHADE
section (master switch plus one row per effect). The snapshot is canned: the
section's own controls are covered once, this check covers the wiring.
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_TEMPDIR = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-reshade-check-")
os.environ["LEXEDITOR_FF8_EDITOR_SETTINGS"] = str(Path(_TEMPDIR.name) / "e.json")

from plugins.ff8.server import create_server
from playwright.sync_api import sync_playwright

BOOTED = "typeof state==='object' && !state.booting && !state.bootFailed"
SNAPSHOT = """() => {
  window.pywebview = {api: {mod_reshade: async () => ({
      available: true, installed: false, gameFound: true, developerMode: false,
      hasDefaults: true, error: "",
      effects: [{file: "Sharpen.fx", id: "Sharpen", label: "Sharpen", tooltip: "",
        techniques: [{name: "Sharpen", label: "Sharpen", tooltip: ""}],
        controls: [{name: "Strength", type: "float", widget: "slider",
          label: "Strength", tooltip: "", default: 0.5, min: 0, max: 1, step: 0.01}],
        enabled: true, values: {Strength: 0.5}}]})}};
}"""


def main():
    server = create_server(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            page.wait_for_function(BOOTED, timeout=90000)
            page.locator('nav [data-tab="settings"]').click()
            page.locator('.lex-subtab-bar button', has_text="Gameplay").wait_for()
            page.wait_for_timeout(300)
            subtab = page.locator('.lex-subtab-bar button', has_text="ReShade")
            assert subtab.count() == 0, "no host, no ReShade for players: no subtab"
            page.reload()
            page.wait_for_function(BOOTED, timeout=90000)
            page.evaluate(SNAPSHOT)
            page.locator('nav [data-tab="settings"]').click()
            subtab.wait_for()
            subtab.click()
            page.locator(".lex-reshade").wait_for()
            assert page.locator('[aria-label="ReShade on or off"]').count() == 1
            assert "ReShade is off" in page.locator(".lex-reshade").inner_text()
            assert page.locator('[aria-label="Sharpen on or off"]').count() == 1
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        _TEMPDIR.cleanup()
    print("FF8 Tweaks ReShade subtab: none without a host, the shared section with one.")


if __name__ == "__main__":
    main()
