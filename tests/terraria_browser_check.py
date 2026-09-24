"""Rendered browser acceptance for the Terraria plugin using synthetic tModLoader source data."""
from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
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

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else DEV_CACHE / "terraria-browser"
OUT.mkdir(parents=True, exist_ok=True)


def fixture_tmodloader_dll(product_version: str) -> bytes:
    """Minimal PE32+ carrying only a VERSIONINFO resource.

    Lets the Windows version gate verify the supported stable build from a
    synthetic install root. The fixture is never executed.
    """
    import struct

    def u16(value: str) -> bytes:
        return value.encode("utf-16-le") + b"\x00\x00"

    def block(value_length: int, value_type: int, key: str, value: bytes,
              children: bytes) -> bytes:
        key_blob = u16(key)
        pad_before = b"\x00" * ((-(6 + len(key_blob))) % 4)
        pad_after = b"\x00" * ((-len(value)) % 4)
        body = pad_before + value + pad_after + children
        return (struct.pack("<HHH", 6 + len(key_blob) + len(body),
                            value_length, value_type) + key_blob + body)

    quad = [int(part) for part in product_version.split(".")]
    ms = (quad[0] << 16) | quad[1]
    ls = (quad[2] << 16) | quad[3]
    fixed = struct.pack("<13I", 0xFEEF04BD, 0x10000, 0, 0, 0, 0, 0x3F,
                        0x40004, 0, 0, 0, 0, 0)
    fixed = fixed[:8] + struct.pack("<II", ms, ls) + struct.pack("<II", ms, ls) + fixed[24:]
    string = block(len(u16(product_version)) // 2, 1, "ProductVersion",
                   u16(product_version), b"")
    table = block(0, 1, "040904B0", b"", string)
    strings = block(0, 1, "StringFileInfo", b"", table)
    var = block(4, 0, "Translation", struct.pack("<HH", 0x0409, 0x04B0), b"")
    resource = block(len(fixed), 0, "VS_VERSION_INFO", fixed,
                     strings + block(0, 1, "VarFileInfo", b"", var))
    root = struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1) + struct.pack("<II", 16, 0x80000018)
    level1 = struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1) + struct.pack("<II", 1, 0x80000030)
    level2 = struct.pack("<IIHHHH", 0, 0, 0, 0, 0, 1) + struct.pack("<II", 0x0409, 72)
    tree = root + level1 + level2
    data_entry = struct.pack("<IIII", 0x1000 + len(tree) + 16, len(resource), 0, 0)
    full_tree = tree + data_entry
    rsrc = full_tree + resource
    raw_size = (len(rsrc) + 0x1FF) & ~0x1FF
    dos = struct.pack("<30H", 0x5A4D, *([0] * 29))
    dos = dos[:60] + struct.pack("<I", 0x40)
    opt = struct.pack("<HBBIIIIIQIIHHHHHHIIIIHHQQQQII",
                      0x20B, 0, 0, 0, 0, 0, 0, 0, 0x180000000, 0x1000, 0x200,
                      0, 0, 0, 0, 4, 0, 0, 0x2000, 0x200, 0, 2, 0,
                      0x100000, 0x1000, 0x100000, 0x1000, 0, 16)
    directories = [b"\x00" * 8] * 16
    directories[2] = struct.pack("<II", 0x1000, len(rsrc))
    section = struct.pack("<8sIIIIIIHHI", b".rsrc\x00\x00\x00", len(rsrc), 0x1000,
                          raw_size, 0x200, 0, 0, 0, 0, 0x40000040)
    headers = (dos + b"PE\x00\x00"
               + struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, 240, 0x2100)
               + opt + b"".join(directories) + section)
    headers = headers + b"\x00" * (0x200 - len(headers))
    rsrc = rsrc + b"\x00" * (raw_size - len(rsrc))
    return headers + full_tree + resource + rsrc[len(full_tree) + len(resource):]


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


def wait_editor_ready(page) -> None:
    # The shared framework intentionally keeps an input-blocking loading screen
    # up for a configurable minimum. Visual acceptance starts after it is gone.
    page.locator(".lex-plugin-loading-screen").wait_for(state="detached", timeout=6000)


def capture(page, screenshots: list[str], name: str) -> None:
    wait_editor_ready(page)
    path = OUT / name
    page.screenshot(path=str(path), full_page=True)
    screenshots.append(path.name)


def reveal_settings_locator(page, target, label: str) -> None:
    for _ in range(12):
        if target.count() and target.is_visible():
            return
        pager = page.locator("#main .lex-tweaks-pages").last
        if not pager.count():
            break
        next_button = pager.get_by_role("button", name="Next page")
        if not next_button.count() or next_button.is_disabled():
            break
        next_button.click()
        page.wait_for_timeout(80)
    assert target.count() and target.is_visible(), (label, page.locator("#main").inner_text())


def reveal_settings_text(page, text: str) -> None:
    reveal_settings_locator(page, page.get_by_text(text, exact=False).first, text)


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
        (install_root / "tModLoader.dll").write_bytes(
            fixture_tmodloader_dll("2026.07.3.0"))
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

        from plugins.terraria.plugin import TerrariaSession
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
                    assert page.get_by_label("Display name", exact=True).is_visible()
                    translation = page.get_by_label("Translation mod", exact=True)
                    translation.scroll_into_view_if_needed()
                    assert translation.is_visible()
                    package_checks = page.locator('.lex-detail-section').filter(has_text="PACKAGE").locator('input[type="checkbox"]')
                    assert package_checks.count() == 6
                    rows = package_checks.evaluate_all("""nodes => nodes.map(node => {
                      const row=node.closest('.lex-detail-field').getBoundingClientRect();
                      const box=node.getBoundingClientRect();
                      return {rowLeft:row.left,rowRight:row.right,boxLeft:box.left,boxRight:box.right};
                    })""")
                    assert all(item["boxLeft"] >= item["rowLeft"] and item["boxRight"] <= item["rowRight"] for item in rows), rows
                    no_horizontal_overflow(page, "metadata-desktop")
                    capture(page, screenshots, "metadata-desktop.png")

                    page.evaluate('navigate("dependencies")')
                    build_button = page.get_by_role("button", name="Build Mod")
                    build_button.scroll_into_view_if_needed()
                    assert build_button.is_visible()
                    no_horizontal_overflow(page, "dependencies-desktop")
                    capture(page, screenshots, "dependencies-desktop.png")

                    page.locator("#plugin-info").click()
                    page.get_by_text("MOD LOADER", exact=True).wait_for()
                    reveal_settings_locator(
                        page,
                        page.locator('input.lex-readonly-field[value*="External Steam runtime"]').first,
                        "External Steam runtime",
                    )
                    info_body = page.locator(".lex-information-panel .lex-detail-panel-body")
                    info_body.locator(".lex-plugin-mod-loading").wait_for()
                    info_body.locator(".lex-plugin-credits").wait_for()
                    placement = info_body.evaluate("""body => {
                      const loader=body.querySelector('.lex-plugin-mod-loading')?.getBoundingClientRect();
                      const credits=body.querySelector('.lex-plugin-credits')?.getBoundingClientRect();
                      return loader&&credits ? {loaderBottom:loader.bottom,creditsTop:credits.top} : null;
                    }""")
                    assert placement and placement["creditsTop"] >= placement["loaderBottom"] - 1, placement
                    no_horizontal_overflow(page, "info-desktop")
                    capture(page, screenshots, "info-desktop.png")

                    page.locator("#plugin-data-map").click()
                    page.locator(".lex-data-map-view").wait_for()
                    assert page.locator(".lex-integration-status").count() >= 3
                    data_search = page.get_by_role("searchbox", name="Search the data map")
                    data_search.fill("build.txt")
                    page.wait_for_timeout(100)
                    assert page.locator(".lex-column-list-row").count() >= 1
                    no_horizontal_overflow(page, "data-map-desktop")
                    capture(page, screenshots, "data-map-desktop.png")
                    data_search.fill("")

                    page.evaluate('navigate("content")')
                    page.locator(".lex-tabbed-panel").wait_for()
                    assert int(page.locator(".lex-page-total").first.inner_text()) >= 2
                    page.get_by_role("button", name="Next page").first.click()
                    page.wait_for_timeout(100)
                    assert page.locator(".lex-paged-list-detail").get_attribute("data-lex-page") == "1"
                    page.get_by_role("button", name="First page").first.click()
                    name_sort = page.locator('button.lex-column-sort[data-lex-title="Sort by Name"]')
                    family_sort = page.locator('button.lex-column-sort[data-lex-title="Sort by Family"]')
                    name_sort.wait_for(timeout=5000)
                    family_sort.wait_for(state="visible", timeout=5000)
                    boxes = page.wait_for_function("() => { const rect = t => document.querySelector(`button.lex-column-sort[data-lex-title=\"${t}\"]`)?.getBoundingClientRect(); const a = rect(\"Sort by Name\"), b = rect(\"Sort by Family\"); if (!a || !b || !a.width || !b.width) return null; return [{x: a.x, width: a.width}, {x: b.x, width: b.width}]; }", timeout=5000).json_value()
                    assert boxes[0] and boxes[1] and boxes[0]["x"] + boxes[0]["width"] <= boxes[1]["x"] + 1, boxes
                    name_sort.click()
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

                    # Reopen the whole editor, not only the file API, and prove the saved
                    # structured value survives a fresh UI boot.
                    page.reload(wait_until="domcontentloaded")
                    page.locator(".lex-detail-panel").first.wait_for()
                    wait_editor_ready(page)
                    page.evaluate('navigate("content")')
                    page.get_by_role("searchbox", name="Search managed Terraria content").fill("AcceptanceItem")
                    page.get_by_text("AcceptanceItem", exact=True).first.click()
                    page.wait_for_function("structuredCurrent?.path?.endsWith('AcceptanceItem.cs')")
                    assert page.get_by_label("Damage", exact=True).input_value() == "17"
                    damage = page.get_by_label("Damage", exact=True)
                    damage.fill("23")
                    assert page.locator("#global-save").is_enabled()
                    page.locator("#global-save").click(button="right")
                    page.get_by_role("button", name="Discard Changes").click()
                    page.wait_for_function("structuredCurrent?.values?.damage === 17")
                    page.wait_for_function(
                        "document.querySelector('input[aria-label=\"Damage\"]')?.value === \"17\"")
                    assert page.get_by_label("Damage", exact=True).input_value() == "17"
                    no_horizontal_overflow(page, "content-desktop")
                    capture(page, screenshots, "content-managed-desktop.png")
                    page.get_by_role("tab", name="Create").click()
                    page.get_by_text("Create Content", exact=True).wait_for()
                    assert page.get_by_label("Content family").is_visible()
                    create_button = page.get_by_role("button", name="Create content")
                    create_button.scroll_into_view_if_needed()
                    assert create_button.is_visible()
                    capture(page, screenshots, "content-create-desktop.png")
                    page.get_by_role("tab", name="Scaffolds").click()
                    page.get_by_text("Logic Scaffold", exact=True).wait_for()
                    capture(page, screenshots, "content-scaffolds-desktop.png")

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
                    capture(page, screenshots, "localization-desktop.png")

                    page.evaluate('navigate("source")')
                    assert int(page.locator(".lex-page-total").first.inner_text()) >= 2
                    page.get_by_role("button", name="Next page").first.click()
                    page.get_by_role("button", name="First page").first.click()
                    source_search = page.get_by_role("searchbox", name="Search Terraria source files")
                    source_search.fill("AcceptanceCommand.cs")
                    page.locator(".lex-column-list-row").filter(has_text="AcceptanceCommand.cs").first.click()
                    page.wait_for_function("sourceCurrent?.path?.endsWith('AcceptanceCommand.cs')")
                    page.get_by_role("button", name="Delete source").scroll_into_view_if_needed()
                    assert page.get_by_role("button", name="Delete source").is_visible()
                    source_width = page.evaluate("""() => {
                      const detail=document.querySelector('#main .lex-detail-panel');
                      const editor=document.querySelector('#main .lex-code-field');
                      if(!detail||!editor)return null;
                      return {detail:detail.getBoundingClientRect().width,editor:editor.getBoundingClientRect().width};
                    }""")
                    assert source_width and source_width["editor"] >= source_width["detail"] * 0.65, source_width
                    no_horizontal_overflow(page, "source-desktop")
                    capture(page, screenshots, "source-desktop.png")

                    page.evaluate('navigate("assets")')
                    assert int(page.locator(".lex-page-total").first.inner_text()) >= 2
                    page.get_by_role("button", name="Next page").first.click()
                    page.get_by_role("button", name="First page").first.click()
                    asset_search = page.get_by_role("searchbox", name="Search Terraria assets")
                    asset_search.fill("BrowserExtra17")
                    page.locator(".lex-column-list-row").filter(has_text="BrowserExtra17").first.click()
                    page.wait_for_function("assetCurrent?.path?.includes('BrowserExtra17')")
                    page.get_by_role("button", name="Delete asset").scroll_into_view_if_needed()
                    assert page.get_by_role("button", name="Delete asset").is_visible()
                    no_horizontal_overflow(page, "assets-desktop")
                    capture(page, screenshots, "assets-desktop.png")

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

                    page.evaluate('navigate("metadata")')
                    page.wait_for_function("!document.querySelector('#main [role=\"status\"]')", timeout=5000)
                    reveal_settings_text(page, "TRANSLATION MOD")
                    page.evaluate('navigate("dependencies")')
                    page.get_by_role("button", name="Build Mod").scroll_into_view_if_needed()
                    assert page.get_by_role("button", name="Build Mod").is_visible()
                    page.evaluate('navigate("content")')
                    page.get_by_role("tab", name="Create").click()
                    create_button = page.get_by_role("button", name="Create content")
                    create_button.scroll_into_view_if_needed()
                    assert create_button.is_visible()
                    page.evaluate('navigate("source")')
                    page.get_by_role("searchbox", name="Search Terraria source files").fill("AcceptanceCommand.cs")
                    page.locator(".lex-column-list-row").filter(has_text="AcceptanceCommand.cs").first.click()
                    page.wait_for_function("sourceCurrent?.path?.endsWith('AcceptanceCommand.cs')")
                    delete = page.get_by_role("button", name="Delete source")
                    delete.scroll_into_view_if_needed()
                    assert delete.is_visible()
                    capture(page, screenshots, "source-narrow-150.png")
                    page.evaluate('navigate("assets")')
                    page.get_by_role("searchbox", name="Search Terraria assets").fill("BrowserExtra17")
                    page.locator(".lex-column-list-row").filter(has_text="BrowserExtra17").first.click()
                    page.wait_for_function("assetCurrent?.path?.includes('BrowserExtra17')")
                    page.get_by_role("button", name="Delete asset").scroll_into_view_if_needed()
                    assert page.get_by_role("button", name="Delete asset").is_visible()
                    capture(page, screenshots, "assets-narrow-150.png")

                    page.evaluate("document.body.style.zoom='1'")
                    page.set_viewport_size({"width": 1000, "height": 760})
                    page.locator("#plugin-data-map").click()
                    page.locator(".lex-data-map-view").wait_for()
                    no_horizontal_overflow(page, "data-map-medium")
                    capture(page, screenshots, "data-map-medium.png")
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
