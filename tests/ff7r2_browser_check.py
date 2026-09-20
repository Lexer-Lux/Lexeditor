"""Rendered browser acceptance for the FF7R2 Rebirth plugin.

Uses the real loopback service and a structural synthetic PlayerParameter fixture.
No proprietary game data and no installed Rebirth copy are required.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ff7r2_fixture import fixture
from games.ff7r2.plugin import Ff7r2Session


OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "ff7r2-browser"
OUT.mkdir(parents=True, exist_ok=True)
PLAYER = Path("End/Content/DataObject/Resident/PlayerParameter.uasset")


def layout_metrics(page):
    return page.evaluate("""()=>({
      body:document.body.scrollHeight,
      viewport:innerHeight,
      main:document.querySelector("main").scrollHeight,
      mainHeight:document.querySelector("main").clientHeight
    })""")


with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-browser-") as temp_name:
    temp = Path(temp_name)
    project = temp / "RebirthBrowser"
    project.mkdir()
    (project / "lexeditor-project.json").write_text(
        '{"format":1,"game":"ff7r2"}\\n', encoding="utf-8")
    source = project / "source" / PLAYER
    source.parent.mkdir(parents=True)
    source.write_bytes(fixture())
    environment = {"LEXEDITOR_FF7R2_PROJECT": str(project)}

    errors = []
    with Ff7r2Session(environment) as session:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=shutil.which("chromium") or None,
                headless=True,
                args=["--no-sandbox"],
            )
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(session.url, wait_until="domcontentloaded")
                page.wait_for_selector(".lex-paged-list-detail")
                page.locator(".lex-plugin-loading-screen").wait_for(state="detached", timeout=5000)
                expect(page.get_by_text("Cloud", exact=True).first).to_be_visible()
                assert page.locator(".lex-column-list-row").count() >= 10
                search = page.get_by_role("searchbox", name="Search PlayerParameter records")
                search.fill("Tifa")
                expect(page.get_by_text("Tifa", exact=True).first).to_be_visible()
                search.fill("Cloud")
                expect(page.get_by_text("Cloud", exact=True).first).to_be_visible()
                search.fill("")
                page.wait_for_function("()=>document.querySelectorAll('.lex-column-list-row').length>=10")
                expect(page.get_by_text("Cloud", exact=True).first).to_be_visible()
                expect(page.locator('.lex-column-list-head-cell[data-column-key="key"]')).to_be_visible()
                assert page.locator('.lex-column-list-head-cell[data-column-key="Spilit"]').count() == 0
                spilit_pin = page.locator('[data-lex-pin-column="Spilit"]').first
                expect(spilit_pin).to_be_visible()
                spilit_pin.click()
                expect(page.locator('.lex-column-list-head-cell[data-column-key="Spilit"]')).to_be_visible()
                spilit_pin = page.locator('[data-lex-pin-column="Spilit"]').first
                spilit_pin.click()
                hp = page.locator('input[aria-label="HPMax"]')
                expect(hp).to_have_count(1)
                assert hp.input_value().replace(",", "").replace(" ", "") == "1000", hp.input_value()
                page.screenshot(path=str(OUT / "characters-desktop.png"), full_page=True)

                hp.fill("1234")
                hp.press("Tab")
                expect(page.locator("#global-save")).to_be_enabled()
                page.locator("#global-save").click()
                page.wait_for_function(
                    "()=>document.querySelector('#global-save')?.disabled===true")
                assert (project / "content" / PLAYER).is_file()
                page.evaluate("reopenPlayer()")
                page.wait_for_function(
                    "()=>document.querySelector('input[aria-label=\"HPMax\"]')?.value.replaceAll(',','').replaceAll(' ','')==='1234'")
                assert page.locator('input[aria-label="HPMax"]').input_value().replace(",", "").replace(" ", "") == "1234"

                page.evaluate('switchProjectSource("vanilla")')
                page.wait_for_function(
                    "()=>document.querySelector('input[aria-label=\"HPMax\"]')?.value.replaceAll(',','').replaceAll(' ','')==='1000'")
                source_hp = page.locator('input[aria-label="HPMax"]')
                expect(source_hp).to_be_disabled()
                page.evaluate('switchProjectSource("mine")')
                page.wait_for_function(
                    "()=>document.querySelector('input[aria-label=\"HPMax\"]')?.value.replaceAll(',','').replaceAll(' ','')==='1234'")

                page.evaluate('navigate("datamap")')
                page.wait_for_selector(".lex-data-map")
                expect(page.get_by_text("BattlePlayerParameter.uasset", exact=False)).to_be_visible()
                expect(page.get_by_text("Faster Queen", exact=False)).to_be_visible()
                page.screenshot(path=str(OUT / "data-map.png"), full_page=True)

                page.evaluate('navigate("info")')
                expect(page.get_by_text("IOSTORE TOOLING", exact=True)).to_be_visible()
                expect(page.get_by_text("not automatically integrated", exact=False).first).to_be_visible()
                page.screenshot(path=str(OUT / "information.png"), full_page=True)

                page.evaluate('navigate("tweaks")')
                expect(page.get_by_text("ReShade", exact=True).first).to_be_visible()
                expect(page.get_by_text("Shader Injector", exact=True).first).to_be_visible()
                page.screenshot(path=str(OUT / "tweaks.png"), full_page=True)

                page.evaluate('navigate("characters")')
                page.set_viewport_size({"width": 900, "height": 700})
                page.wait_for_timeout(100)
                metrics = layout_metrics(page)
                assert metrics["body"] <= metrics["viewport"] + 2, metrics
                assert metrics["main"] <= metrics["mainHeight"] + 2, metrics
                page.screenshot(path=str(OUT / "characters-narrow.png"), full_page=True)

                page.set_viewport_size({"width": 1440, "height": 900})
                page.evaluate('document.documentElement.style.zoom="150%"')
                page.wait_for_timeout(100)
                expect(page.locator('input[aria-label="HPMax"]')).to_be_visible()
                page.screenshot(path=str(OUT / "characters-150-percent.png"), full_page=True)
                page.close()
            finally:
                browser.close()

    assert source.read_bytes() == fixture(), "Browser save modified the extracted source"
    assert not errors, errors

print("FF7R2 rendered browser acceptance passed")
