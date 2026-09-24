"""Rendered browser acceptance for the FF7R2 Rebirth plugin.

Uses the real loopback service and a structural synthetic PlayerParameter fixture.
No proprietary game data and no installed Rebirth copy are required.
"""
from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
from pathlib import Path
import shutil
import sys
import tempfile

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ff7r2_fixture import battle_item_possession_fixture, battle_player_parameter_fixture, fixture
from plugins.ff7r2.plugin import Ff7r2Session


OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else DEV_CACHE / "ff7r2-browser"
OUT.mkdir(parents=True, exist_ok=True)
PLAYER = Path("End/Content/DataObject/Resident/PlayerParameter.uasset")
BATTLE_PLAYER = Path("End/Content/DataObject/Resident/BattlePlayerParameter.uasset")
BATTLE_ITEM = Path("End/Content/DataObject/Resident/BattleItemPossession.uasset")


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
    battle_player_source = project / "source" / BATTLE_PLAYER
    battle_player_source.parent.mkdir(parents=True, exist_ok=True)
    battle_player_source.write_bytes(battle_player_parameter_fixture())
    battle_source = project / "source" / BATTLE_ITEM
    battle_source.parent.mkdir(parents=True, exist_ok=True)
    battle_source.write_bytes(battle_item_possession_fixture())
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

                cloud_row = page.locator(".lex-column-list-row").filter(has_text="Cloud").first
                cloud_hp_cell = cloud_row.locator('[data-column-key="HPMax"]')
                cloud_hp_cell.dblclick()
                table_hp = cloud_hp_cell.locator('input[aria-label="HPMax table value"]')
                expect(table_hp).to_be_visible()
                table_hp.fill("1100")
                table_hp.press("Enter")
                page.wait_for_function(
                    "()=>document.querySelector('input[aria-label=\"HPMax\"]')?.value.replaceAll(',','').replaceAll(' ','')==='1100'")
                page.screenshot(path=str(OUT / "characters-desktop.png"), full_page=True)

                hp = page.locator('input[aria-label="HPMax"]')
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

                page.evaluate('navigate("battleparams")')
                page.wait_for_selector(".ff7r2-battle-player-table")
                expect(page.get_by_text("BattleCharacterTest", exact=True).first).to_be_visible()
                expect(page.get_by_role("searchbox", name="Search BattlePlayerParameter records")).to_be_visible()
                expect(page.get_by_text(
                    "Public declarations prove the storage schema, but not the gameplay behavior, enum domains or safe edit ranges. This page therefore stops at structured source inspection.",
                    exact=True,
                )).to_be_visible()
                battle_values = page.locator(".ff7r2-battle-player-detail input.lex-readonly-field")
                assert battle_values.evaluate_all(
                    "els=>els.some(el=>el.value.includes('0: AbilityTest'))"
                )
                assert page.locator(".ff7r2-battle-player-detail input:not([readonly])").count() == 0
                page.screenshot(path=str(OUT / "battle-params.png"), full_page=True)

                page.evaluate('navigate("formulae")')
                page.wait_for_selector(".ff7r2-formulae-table")
                expect(page.get_by_text("EnemyTest", exact=True).first).to_be_visible()
                expect(page.get_by_role("searchbox", name="Search BattleItemPossession records")).to_be_visible()
                formula_values = page.locator(".ff7r2-formulae-detail input.lex-readonly-field")
                assert formula_values.evaluate_all(
                    "els=>els.some(el=>el.value.includes('0: Potion')&&el.value.includes('1: Ether'))"
                )
                expect(page.get_by_text(
                    "Generated runtime types include StealSuccessRateAdd, but its arithmetic/order is not exposed.",
                    exact=True,
                )).to_be_visible()
                expect(page.get_by_text(
                    "Generated runtime types distinguish StealFailed, AlreadyStolen and NothingToSteal; their branch conditions are not exposed.",
                    exact=True,
                )).to_be_visible()
                assert page.locator(".ff7r2-formulae-detail input:not([readonly])").count() == 0
                page.screenshot(path=str(OUT / "formulae.png"), full_page=True)

                page.evaluate('navigate("datamap")')
                page.wait_for_selector(".lex-data-map")
                expect(page.get_by_text("BattlePlayerParameter.uasset", exact=False)).to_be_visible()
                battle_player_row = page.locator(".lex-column-list-row").filter(has_text="BattlePlayerParameter.uasset")
                expect(battle_player_row).to_have_count(1)
                assert battle_player_row.locator(".lex-integration-status.partial").count() == 1
                expect(page.get_by_text("BattleItemPossession.uasset (#471)", exact=False)).to_be_visible()
                expect(page.get_by_text("CardGameCommonParameter.uasset + CardGameAIParam.uasset (#477)", exact=False)).to_be_visible()
                for issue in ("#470", "#472", "#473", "#477"):
                    issue_row = page.locator(".lex-column-list-row").filter(has_text=issue)
                    expect(issue_row).to_have_count(1)
                    assert issue_row.locator(".lex-integration-status.not-integrated").count() == 1
                steal_row = page.locator(".lex-column-list-row").filter(has_text="#471")
                expect(steal_row).to_have_count(1)
                assert steal_row.locator(".lex-integration-status.partial").count() == 1
                assert page.locator(".lex-integration-status.partial").count() >= 3

                evidence_rows = page.evaluate("""async()=> {
                  const response = await fetch('/api/datamap');
                  return (await response.json()).rows;
                }""")
                issue_evidence = {}
                for row in evidence_rows:
                    for issue in (470, 471, 472, 473, 477):
                        if f"#{issue}" in row["filename"]:
                            issue_evidence[issue] = row
                assert "bDisableChocoboRide" in issue_evidence[470]["notes"]
                assert "array elements read-only" in issue_evidence[471]["notes"].lower()
                assert "ZabutonActorClass" in issue_evidence[472]["notes"]
                assert "AreaNaviMapScale" in issue_evidence[473]["notes"]
                assert "LocationNaviMapScale" in issue_evidence[473]["notes"]
                assert "_PassClass" in issue_evidence[477]["notes"]
                assert "CardPlacementActor" in issue_evidence[477]["notes"]
                player_map_file = page.get_by_text(
                    "End/Content/DataObject/Resident/PlayerParameter.uasset", exact=True)
                expect(player_map_file).to_be_visible()
                player_map_file.click()
                open_characters = page.get_by_role("button", name="Open characters")
                expect(open_characters).to_be_visible()
                page.screenshot(path=str(OUT / "data-map.png"), full_page=True)
                open_characters.click()
                page.wait_for_selector(".ff7r2-table")
                expect(page.get_by_text("Cloud", exact=True).first).to_be_visible()
                page.evaluate('navigate("datamap")')
                page.wait_for_selector(".lex-data-map")

                page.evaluate('navigate("info")')
                expect(page.get_by_text("IOSTORE TOOLING", exact=True)).to_be_visible()
                expect(page.get_by_text("NATIVE MOD LOAD ORDER", exact=True)).to_be_visible()
                precedence_field = page.locator(".lex-detail-field").filter(has_text="PRECEDENCE").first
                expect(precedence_field).to_be_visible()
                assert "~mods is not available" in precedence_field.locator("input.lex-readonly-field").input_value()
                retoc_field = page.locator(".lex-detail-field").filter(has_text="RETOC").first
                expect(retoc_field).to_be_visible()
                retoc_value = retoc_field.locator("input.lex-readonly-field")
                assert "v0.1.5" in retoc_value.input_value(), retoc_value.input_value()
                preflight = page.locator(".lex-detail-field").filter(has_text="PACKAGING PREFLIGHT").first
                expect(preflight).to_be_visible()
                candidate_button = page.get_by_role("button", name="Build isolated candidate")
                expect(candidate_button).to_be_visible()
                expect(candidate_button).to_be_disabled()
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
                # CSS zoom approximates desktop-host UI scale. A full-page
                # capture multiplies Chromium's document height and adds an
                # artificial blank tail that is not visible in the host.
                page.screenshot(path=str(OUT / "characters-150-percent.png"), full_page=False)
                page.close()
            finally:
                browser.close()

    assert source.read_bytes() == fixture(), "Browser save modified the extracted source"
    assert battle_player_source.read_bytes() == battle_player_parameter_fixture(), "Browser view modified BattlePlayerParameter"
    assert battle_source.read_bytes() == battle_item_possession_fixture(), "Browser view modified BattleItemPossession"
    assert not errors, errors

print("FF7R2 rendered browser acceptance passed")
