"""FF8 Tweaks grows a ReShade subtab backed by the shared section.

Without a desktop host the page says to open it in the desktop app; with a
host snapshot it renders the shared RESHADE section (master switch plus one
row per effect). The snapshot here is canned: the shared section's own
controls are covered once, this check covers FF8's wiring.
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_TEMPDIR = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-reshade-check-")
os.environ["LEXEDITOR_FF8_EDITOR_SETTINGS"] = str(Path(_TEMPDIR.name) / "e.json")

from plugins.ff8.server import create_server
from playwright.sync_api import sync_playwright

BOOTED = "typeof state==='object' && !state.booting && !state.bootFailed"
SNAPSHOT = """() => {
  const original = LexeditorUI.callWindow;
  LexeditorUI.callWindow = async (method, ...args) => {
    if (method === "mod_reshade") return {
      available: true, installed: false, gameFound: true, developerMode: false,
      hasDefaults: true, error: "",
      effects: [{file: "Sharpen.fx", id: "Sharpen", label: "Sharpen", tooltip: "",
        techniques: [{name: "Sharpen", label: "Sharpen", tooltip: ""}],
        controls: [{name: "Strength", type: "float", widget: "slider",
          label: "Strength", tooltip: "", default: 0.5, min: 0, max: 1, step: 0.01}],
        enabled: true, values: {Strength: 0.5}}]};
    return original?.(method, ...args);
  };
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
            subtab = page.locator('.lex-subtab-bar button', has_text="ReShade")
            subtab.wait_for()
            subtab.click()
            page.locator("#main", has_text="desktop app").wait_for()
            assert page.locator(".lex-reshade").count() == 0
            page.evaluate(SNAPSHOT)
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
    print("FF8 Tweaks ReShade subtab: host notice without a host, shared section with one.")


if __name__ == "__main__":
    main()
