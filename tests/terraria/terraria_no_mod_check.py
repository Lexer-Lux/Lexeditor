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
INSTRUCTION = "Choose Create Mod in the Mod menu"
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
                    if INSTRUCTION not in text:
                        failures.append(f"{label} tab does not say how to make a mod: {text[:160]!r}")
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
    print("PASS: every Terraria tab explains the missing mod source")
    print("PASS: screenshots:", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
