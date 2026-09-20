"""Rendered browser acceptance for the Terraria plugin using synthetic tModLoader source data."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "terraria-browser"
OUT.mkdir(parents=True, exist_ok=True)


def no_horizontal_overflow(page, label: str) -> None:
    data = page.evaluate(
        """() => ({
          inner: innerWidth,
          doc: document.documentElement.scrollWidth,
          main: document.querySelector('#main')?.scrollWidth || 0,
          mainClient: document.querySelector('#main')?.clientWidth || 0
        })"""
    )
    assert data["doc"] <= data["inner"] + 2, (label, data)
    assert data["main"] <= data["mainClient"] + 3, (label, data)


def main() -> None:
    errors: list[str] = []
    screenshots: list[str] = []

    with tempfile.TemporaryDirectory(prefix="lexeditor-terraria-browser-") as temp_name:
        temp = Path(temp_name)
        save_root = temp / "Terraria" / "tModLoader"
        project = save_root / "ModSources" / "TerrariaUiFixture"
        install_root = temp / "tModLoader"
        install_root.mkdir(parents=True)
        (install_root / "start-tModLoader.bat").write_text("@echo off\n", encoding="utf-8")
        (install_root / "tModLoader.dll").write_bytes(b"fixture")
        (install_root / "LaunchUtils").mkdir()

        os.environ["LEXEDITOR_TERRARIA_ROOT"] = str(install_root)
        os.environ["LEXEDITOR_TERRARIA_SAVE_ROOT"] = str(save_root)
        os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(project)

        from tools.terraria_acceptance import populate_acceptance_project
        populate_acceptance_project(project)

        fr = project / "Localization" / "fr-FR.hjson"
        fr.write_text(
            "{\n"
            + "\n".join(
                f'  "Mods.TerrariaUiFixture.Custom.Key{i:02d}": "Valeur {i:02d}"'
                + ("," if i < 41 else "")
                for i in range(42)
            )
            + "\n}\n",
            encoding="utf-8",
        )
        extras = project / "Common" / "Browser"
        extras.mkdir(parents=True)
        for i in range(18):
            (extras / f"BrowserExtra{i:02d}.cs").write_text(
                f"namespace TerrariaUiFixture.Common.Browser; public sealed class BrowserExtra{i:02d} {{}}\n",
                encoding="utf-8",
            )
        sample_png = project / "Content" / "Items" / "AcceptanceItem.png"
        asset_dir = project / "Content" / "Browser"
        asset_dir.mkdir(parents=True)
        for i in range(18):
            shutil.copyfile(sample_png, asset_dir / f"BrowserExtra{i:02d}.png")

        from games.terraria.plugin import TerrariaSession
        with TerrariaSession({
            "LEXEDITOR_TERRARIA_ROOT": str(install_root),
            "LEXEDITOR_TERRARIA_SAVE_ROOT": str(save_root),
            "LEXEDITOR_TERRARIA_PROJECT": str(project),
        }) as session:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    executable_path=shutil.which("chromium") or None,
                    headless=True,
                    args=["--no-sandbox"],
                )
                try:
                    page = browser.new_page(viewport={"width": 1600, "height": 1000})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url, wait_until="domcontentloaded")
                    page.locator(".lex-detail-panel").first.wait_for()
                    no_horizontal_overflow(page, "metadata-desktop")

                    page.locator("#plugin-info").click()
                    page.get_by_text("MOD LOADER", exact=True).wait_for()
                    ownership = page.get_by_text("External Steam runtime", exact=False)
                    for _ in range(8):
                        if ownership.is_visible():
                            break
                        next_page = page.locator("#main .lex-tweaks-pages").get_by_role("button", name="Next page")
                        if not next_page.count() or next_page.is_disabled():
                            break
                        next_page.click()
                        page.wait_for_timeout(80)
                    assert ownership.is_visible(), page.locator("#main").inner_text()
                    no_horizontal_overflow(page, "info-desktop")

                    page.locator("#plugin-data-map").click()
                    page.locator(".lex-data-map-view").wait_for()
                    assert page.locator(".lex-integration-status").count() >= 3
                    data_search = page.get_by_role("searchbox", name="Search the data map")
                    data_search.fill("build.txt")
                    page.wait_for_timeout(100)
                    assert page.locator(".lex-column-list-row").count() >= 1
                    no_horizontal_overflow(page, "data-map-desktop")
                    path = OUT / "data-map-desktop.png"
                    page.screenshot(path=str(path), full_page=True)
                    screenshots.append(path.name)
                    data_search.fill("")

                    page.evaluate('navigate("content")')
                    page.locator(".terraria-content-tabs").wait_for()
                    assert int(page.locator(".lex-page-total").first.inner_text()) >= 2
                    page.get_by_role("button", name="Next page").first.click()
                    page.wait_for_timeout(100)
                    assert page.locator(".lex-paged-list-detail").get_attribute("data-lex-page") == "1"
                    page.get_by_role("button", name="First page").first.click()
                    page.locator('[role="columnheader"][data-column-key="name"]').click()
                    search = page.get_by_role("searchbox", name="Search managed Terraria content")
                    search.fill("AcceptanceItem")
                    page.get_by_text("AcceptanceItem", exact=True).first.click()
                    page.wait_for_function("structuredCurrent?.path?.endsWith('AcceptanceItem.cs')")
                    damage = page.get_by_label("Damage", exact=True)
                    damage.fill("17")
                    page.locator("#global-save").click()
                    page.wait_for_function("document.querySelector('#global-save')?.disabled === true")
                    page.evaluate("loadStructuredContent(structuredCurrent.path)")
                    page.wait_for_function("structuredCurrent?.values?.damage === 17")
                    assert page.get_by_label("Damage", exact=True).input_value() == "17"
                    damage = page.get_by_label("Damage", exact=True)
                    damage.fill("23")
                    assert page.locator("#global-save").is_enabled()
                    page.locator("#global-save").click(button="right")
                    page.get_by_role("button", name="Discard Changes").click()
                    page.wait_for_function("structuredCurrent?.values?.damage === 17")
                    assert page.get_by_label("Damage", exact=True).input_value() == "17"
                    no_horizontal_overflow(page, "content-desktop")
                    path = OUT / "content-desktop.png"
                    page.screenshot(path=str(path), full_page=True)
                    screenshots.append(path.name)

                    page.evaluate('navigate("localization")')
                    page.get_by_role("tab", name="🇫🇷 fr-FR").click()
                    page.wait_for_function("locCurrent?.culture === 'fr-FR'")
                    assert int(page.locator(".lex-page-total").first.inner_text()) >= 2
                    page.get_by_role("button", name="Next page").first.click()
                    page.get_by_role("button", name="First page").first.click()
                    loc_search = page.get_by_role("searchbox", name="Search fr-FR localization")
                    loc_search.fill("Key00")
                    row = page.locator(".lex-column-list-row").filter(has_text="Key00").first
                    row.click()
                    cell = row.locator('[data-column-key="value"]')
                    cell.dblclick()
                    editor = cell.locator("input")
                    editor.fill("Valeur modifiée")
                    editor.press("Enter")
                    page.wait_for_timeout(100)
                    page.locator("#global-save").click()
                    page.wait_for_function("document.querySelector('#global-save')?.disabled === true")
                    page.evaluate("loadLocalizationFile(locCurrent.path, 'Mods.TerrariaUiFixture.Custom.Key00')")
                    page.wait_for_timeout(100)
                    assert "Valeur modifiée" in page.locator("#main").inner_text()
                    no_horizontal_overflow(page, "localization-desktop")

                    page.evaluate('navigate("source")')
                    source_search = page.get_by_role("searchbox", name="Search Terraria source files")
                    source_search.fill("AcceptanceCommand.cs")
                    page.locator(".lex-column-list-row").filter(has_text="AcceptanceCommand.cs").first.click()
                    page.wait_for_function("sourceCurrent?.path?.endsWith('AcceptanceCommand.cs')")
                    page.get_by_role("button", name="Delete source").scroll_into_view_if_needed()
                    assert page.get_by_role("button", name="Delete source").is_visible()
                    no_horizontal_overflow(page, "source-desktop")

                    page.evaluate('navigate("assets")')
                    asset_search = page.get_by_role("searchbox", name="Search Terraria assets")
                    asset_search.fill("BrowserExtra17")
                    page.locator(".lex-column-list-row").filter(has_text="BrowserExtra17").first.click()
                    page.wait_for_function("assetCurrent?.path?.includes('BrowserExtra17')")
                    page.get_by_role("button", name="Delete asset").scroll_into_view_if_needed()
                    assert page.get_by_role("button", name="Delete asset").is_visible()
                    no_horizontal_overflow(page, "assets-desktop")

                    page.evaluate('navigate("metadata")')
                    pip = page.locator(".lex-info-help").first
                    pip.focus()
                    page.wait_for_timeout(100)
                    assert pip.get_attribute("aria-describedby")

                    page.set_viewport_size({"width": 700, "height": 760})
                    page.evaluate("document.body.style.zoom='1.5'")
                    for tab in ("metadata", "dependencies", "content", "localization", "source", "assets"):
                        page.evaluate(f'navigate("{tab}")')
                        page.wait_for_timeout(180)
                        no_horizontal_overflow(page, f"{tab}-narrow-150")
                    page.evaluate('navigate("source")')
                    page.get_by_role("searchbox", name="Search Terraria source files").fill("AcceptanceCommand.cs")
                    page.locator(".lex-column-list-row").filter(has_text="AcceptanceCommand.cs").first.click()
                    page.wait_for_function("sourceCurrent?.path?.endsWith('AcceptanceCommand.cs')")
                    delete = page.get_by_role("button", name="Delete source")
                    delete.scroll_into_view_if_needed()
                    assert delete.is_visible()
                    path = OUT / "source-narrow-150.png"
                    page.screenshot(path=str(path), full_page=True)
                    screenshots.append(path.name)

                    page.evaluate("document.body.style.zoom='1'")
                    page.set_viewport_size({"width": 1000, "height": 760})
                    page.locator("#plugin-data-map").click()
                    page.locator(".lex-data-map-view").wait_for()
                    no_horizontal_overflow(page, "data-map-medium")
                    path = OUT / "data-map-medium.png"
                    page.screenshot(path=str(path), full_page=True)
                    screenshots.append(path.name)
                finally:
                    browser.close()

    if errors:
        raise AssertionError("Browser page errors: " + " | ".join(errors))
    (OUT / "results.json").write_text(
        json.dumps({"screenshots": screenshots, "pageErrors": errors}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"screenshots": screenshots, "pageErrors": errors}))


if __name__ == "__main__":
    main()
