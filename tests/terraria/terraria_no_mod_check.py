"""A Terraria game with no mod source must explain itself on every tab.

The plugin edits a tModLoader source project, so a game with no mod has no
files to list anywhere. Before this check the Mod Metadata and Dependencies
tabs said so, and Content, Localization, Source and Assets showed empty tables
that read as a broken editor. The owner reported exactly that: "literally
nothing in any of the tabs".

This runs the plugin's own service with a project path that does not exist. No
game and no mod source are needed.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.service_session import LocalPluginSession  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

OUTPUT = Path(__import__("tempfile").gettempdir()) / "lexeditor-dev" / "terraria-no-mod"
# The panel names the state, says the page is read-only, and hands the reader
# the action. The paths the service looked in belong to the panel's own help.
STATE = "no mod yet"
ACTION = "Create a mod"
TABS = (
    ("metadata", "Mod Metadata"),
    ("dependencies", "Dependencies & Build"),
    ("content", "Content"),
    ("localization", "Localization"),
    ("source", "Source"),
    ("assets", "Assets"),
)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="lexeditor-terraria-no-mod-") as temp_name:
        temp = Path(temp_name)
        environment = {
            "LEXEDITOR_TERRARIA_PROJECT": str(temp / "ModSources" / "NoSuchMod"),
            "LEXEDITOR_TERRARIA_SAVE_ROOT": str(temp / "tModLoader"),
            "LEXEDITOR_TERRARIA_ROOT": str(temp / "tModLoaderInstall"),
            "LEXEDITOR_MOD_READ_ONLY": "1",
            "LEXEDITOR_NO_MOD": "1",
        }
        session = LocalPluginSession(module="plugins.terraria.server", plugin_id="terraria",
                                     app_root=ROOT, check=lambda: [], extra_env=environment)
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
                page.goto(session.url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector('[data-tab="metadata"]', timeout=30000)
                page.wait_for_timeout(2500)
                for tab, label in TABS:
                    page.locator(f'[data-tab="{tab}"]').first.click()
                    page.wait_for_timeout(800)
                    text = page.locator("#main").inner_text()
                    page.screenshot(path=str(OUTPUT / f"{tab}.png"), full_page=True)
                    if STATE not in text.lower():
                        failures.append(f"{label} tab does not say the game has no mod: {text[:160]!r}")
                    if "read-only" not in text.lower():
                        failures.append(f"{label} tab does not say the page is read-only: {text[:160]!r}")
                    if page.locator("#main button").filter(has_text=ACTION).count() != 1:
                        failures.append(f"{label} tab does not offer to create a mod: {text[:160]!r}")
                    help_text = page.locator("#main .lex-info-help").first.get_attribute("aria-label") or ""
                    if "tModLoader source projects" not in help_text:
                        failures.append(f"{label} help does not explain what this plugin edits: {help_text[:160]!r}")
                # The title names the read-only source, not a missing mod.
                heading = page.locator("#main .lex-detail-panel-title").first.inner_text()
                if "Vanilla" not in heading:
                    failures.append(f"the no-mod panel is titled {heading!r}, not Vanilla")
                page.locator("#plugin-data-map").click()
                page.wait_for_selector(".lex-data-map", timeout=20000)
                page.wait_for_timeout(800)
                page.screenshot(path=str(OUTPUT / "data-map.png"), full_page=True)
                map_text = page.locator("#main").inner_text()
                if "No mod source yet" not in map_text:
                    failures.append(f"Data Map does not explain the missing mod: {map_text[:160]!r}")
                browser.close()
        finally:
            session.stop()

    for error in errors:
        failures.append(error)
    if failures:
        print("FAIL: Terraria with no mod source")
        for failure in failures:
            print(" -", failure)
        return 1
    print("PASS: every Terraria tab names the read-only no-mod state and offers to create a mod")
    print("PASS: screenshots:", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
