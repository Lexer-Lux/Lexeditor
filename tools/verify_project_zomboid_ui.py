"""Rendered Project Zomboid UI acceptance using only synthetic Build 42 data."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

STRUCTURED = (
    "animationmeshes", "items", "evolved", "crafts", "fixing", "fluids",
    "vehicles", "sounds", "models", "mannequins", "timedactions",
)
SURFACES = (
    ("metadata", ".pz-metadata"),
    ("animationmeshes", ".pz-record-layout"),
    ("items", ".pz-record-layout"),
    ("evolved", ".pz-record-layout"),
    ("crafts", ".pz-record-layout"),
    ("fixing", ".pz-record-layout"),
    ("fluids", ".pz-record-layout"),
    ("vehicles", ".pz-record-layout"),
    ("sounds", ".pz-record-layout"),
    ("models", ".pz-record-layout"),
    ("mannequins", ".pz-record-layout"),
    ("timedactions", ".pz-record-layout"),
    ("scripts", ".pz-script-layout"),
    ("datamap", ".lex-data-map-view"),
    ("info", ".lex-information-panel"),
)

SEMANTIC_CONTROL = {
    "animationmeshes": 'input[type="checkbox"]',
    "items": 'input[type="number"]',
    "evolved": 'input[type="number"]',
    "crafts": 'input[type="checkbox"]',
    "fixing": 'input[type="number"]',
    "fluids": 'input[type="text"]',
    "vehicles": 'input[type="number"]',
    "sounds": 'select',
    "models": 'select',
    "mannequins": 'input[type="checkbox"]',
    "timedactions": 'input[type="text"]',
}


def write_fixture(root: Path) -> None:
    scripts = root / "42" / "media" / "scripts"
    scripts.mkdir(parents=True)
    (root / "common" / "media").mkdir(parents=True)
    (root / "42" / "mod.info").write_text(
        "name=Rendered PZ UI Fixture\n"
        "id=RenderedPZUI\n"
        "author=Lexeditor Browser Acceptance\n"
        "modversion=1.0\n"
        "description=Synthetic Build 42 rendered acceptance fixture\n"
        "icon=icon.png\n"
        "url=https://example.invalid/lexeditor-pz-ui\n"
        "category=UI\n"
        "versionMin=42.20\n"
        "versionMax=42.20.4\n"
        "require=\n"
        "incompatible=\n"
        "loadModAfter=\n"
        "loadModBefore=\n",
        encoding="utf-8",
    )
    item_rows = []
    for index in range(55):
        item_rows.append(
            f""" item Item{index:03d}
 {{
  DisplayCategory = Tool,
  ItemType = base:normal,
  Weight = {0.25 + index / 100:.2f},
  Icon = Radio,
 }}
"""
        )
    text = """module LexUI
{
 animationsMesh TestAnimationMesh
 {
  animationDirectory = media/anims_X/LexUI,
  animationPrefix = Lex_,
  keepMeshAnimations = true,
  meshFile = Skinned/LexUI,
  postProcess = +TRIANGULATE,
 }
%s
 evolvedrecipe TestSoup
 {
  BaseItem = Base.PotOfSoup,
  ResultItem = Base.PotOfSoup,
  MaxItems = 4,
  CanAddSpicesEmpty = true,
  MinimumWater = 0.0,
 }
 craftRecipe MakeTestThing
 {
  AllowBatchCraft = true,
  AutoLearnAll = Woodwork:2;Maintenance:1,
  AutoLearnAny = Woodwork:5;Carving:4,
  CanWalk = false,
  category = General,
  Icon = Radio,
  ResearchSkillLevel = -1,
  SkillRequired = Woodwork:3,
  Tags = InHandCraft,
  Time = 50,
  timedAction = Craft,
  Tooltip = SmokeRecipeTooltip,
  inputs { item 1 [Base.Plank], }
 }
 fixing RepairTestThing
 {
  Require = Base.Hammer,
  Fixer = Base.DuctTape=2;Woodwork=1,
  ConditionModifier = 1.0,
 }
 fluid TestFluid
 {
  ColorReference = Azure,
  DisplayName = Fluid_Name_TestFluid,
  Properties { HungerChange = -5, }
 }
 vehicle TestCar
 {
  engineForce = 3000,
  engineIdleSpeed = 750,
  engineLoudness = 100,
  engineQuality = 100,
  engineRepairLevel = 4,
  engineRPMType = jeep,
  gearRatioCount = 5,
  hasLighter = true,
  isSmallVehicle = false,
  part Engine { category = engine, }
 }
 sound TestSound
 {
  category = Item,
  is3D = true,
  loop = false,
  master = Primary,
  maxInstancesPerEmitter = 2,
  clip { file = media/sound/test.ogg, volume = 0.7, }
 }
 model TestModel
 {
  cullFace = Back,
  invertX = false,
  postProcess = +TRIANGULATE,
  scale = 1.0,
  shader = vehicle,
  static = true,
  undoCoreScale = false,
  mesh = LexUI/TestModel,
  attachment Grip { offset = 0.0 0.0 0.0, }
 }
 mannequin TestMannequin
 {
  animSet = mannequin,
  animState = female,
  female = true,
  model = FemaleBody,
  outfit = Casual,
  pose = pose01,
  texture = FemaleBody01,
 }
 timedAction TestTimedAction
 {
  actionAnim = Loot,
  completionSound = BuildFence,
  muscleStrainParts = Neck;Torso_Upper,
  prop1 = Base.HammerModel,
 }
 entity ReadOnlyEntity
 {
  componentType = example,
 }
}
""" % "".join(item_rows)
    (scripts / "rendered-ui.txt").write_text(text, encoding="utf-8")


def layout(page) -> dict:
    return page.evaluate(
        """() => {
          const list=document.querySelector('.lex-barrel-grid>.lex-list');
          const detail=document.querySelector('.lex-detail');
          const last=detail?.querySelector('.lex-detail-field:last-of-type, .lex-detail-section:last-child');
          const box=detail?.getBoundingClientRect(), lastBox=last?.getBoundingClientRect();
          return {
            innerWidth, innerHeight,
            docWidth:document.documentElement.scrollWidth,
            docHeight:document.documentElement.scrollHeight,
            listScroll:list?.scrollHeight||0,
            listClient:list?.clientHeight||0,
            detailScroll:detail?.scrollHeight||0,
            detailClient:detail?.clientHeight||0,
            lastBottom:lastBox?.bottom||0,
            detailBottom:box?.bottom||0
          };
        }"""
    )


def assert_layout(page, label: str) -> dict:
    value = layout(page)
    assert value["docWidth"] <= value["innerWidth"] + 2, (label, value)
    assert value["docHeight"] <= value["innerHeight"] + 2, (label, value)
    if value["listClient"]:
        assert value["listScroll"] <= value["listClient"] + 2, (label, value)
    return value


def screenshot(page, folder: Path | None, name: str) -> None:
    if folder is None:
        return
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder / f"{name}.png"), full_page=False)


def navigate(page, tab: str, selector: str) -> None:
    page.evaluate("(value) => navigate(value)", tab)
    page.locator(selector).wait_for(state="visible")
    page.wait_for_timeout(80)


def assert_detail_reachable(page, label: str) -> dict | None:
    bodies = page.locator(".lex-detail-panel-body")
    if not bodies.count():
        return None
    body = bodies.last
    value = body.evaluate(
        """node => {
          node.scrollTop = node.scrollHeight;
          return {scrollTop:node.scrollTop, scrollHeight:node.scrollHeight, clientHeight:node.clientHeight};
        }"""
    )
    assert value["scrollTop"] + value["clientHeight"] >= value["scrollHeight"] - 2, (label, value)
    return value


def assert_table_fit(page, label: str) -> None:
    table = page.locator(".pz-record-table")
    if not table.count():
        return
    identity = table.locator('.lex-column-list-cell[data-column-key="id"] .lex-column-cell-text').first
    if identity.count():
        fit = identity.evaluate("(node) => ({client:node.clientWidth, scroll:node.scrollWidth, text:node.textContent})")
        assert fit["scroll"] <= fit["client"] + 1, (label, fit)
    for header in table.locator(".lex-column-list-head-cell .lex-column-sort").all():
        fit = header.evaluate("(node) => ({client:node.clientWidth, scroll:node.scrollWidth, text:node.textContent})")
        assert fit["scroll"] <= fit["client"] + 1, (label, fit)


def assert_stacked_master_detail(page, label: str) -> None:
    master = page.locator(".lex-barrelled-master").first
    detail = page.locator(".lex-detail").last
    if not master.count():
        return
    master_box = master.bounding_box()
    detail_box = detail.bounding_box()
    assert master_box and detail_box, (label, master_box, detail_box)
    assert master_box["height"] >= 100 and detail_box["height"] >= 120, (label, master_box, detail_box)
    assert master_box["y"] + master_box["height"] <= detail_box["y"] + 3, (label, master_box, detail_box)


def assert_tab_labels_fit(page, label: str) -> None:
    for node in page.locator("#lexeditor-shell .lex-tab-label-text").all():
        fit = node.evaluate("(node) => ({client:node.clientWidth, scroll:node.scrollWidth, text:node.textContent})")
        assert fit["scroll"] <= fit["client"] + 1, (label, fit)


def render_surface_set(page, folder: Path | None, prefix: str, width: int, height: int, zoom: float = 1.0) -> dict:
    # Native Lexeditor uses WebView2 ZoomFactor, not CSS zoom. Browser zoom keeps
    # 100vh equal to the visible viewport while reducing the CSS-pixel viewport
    # available for layout. Emulate that geometry directly: a physical 1100x760
    # window at 150% is about 733x507 CSS pixels.
    effective_width = max(1, round(width / zoom))
    effective_height = max(1, round(height / zoom))
    page.set_viewport_size({"width": effective_width, "height": effective_height})
    results = {}
    assert_tab_labels_fit(page, prefix)
    for index, (tab, selector) in enumerate(SURFACES, start=1):
        navigate(page, tab, selector)
        results[tab] = assert_layout(page, f"{tab}-{prefix}")
        assert_table_fit(page, f"{tab}-{prefix}")
        assert_detail_reachable(page, f"{tab}-{prefix}")
        if effective_width <= 850:
            assert_stacked_master_detail(page, f"{tab}-{prefix}")
        screenshot(page, folder, f"{prefix}-{index:02d}-{tab}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    from plugins.project_zomboid import server

    with tempfile.TemporaryDirectory(prefix="lexeditor-pz-rendered-") as temp:
        base = Path(temp)
        project = base / "Rendered PZ UI Fixture"
        user_root = base / "Zomboid"
        write_fixture(project)
        previous_project = os.environ.get("LEXEDITOR_PROJECT_ZOMBOID_PROJECT")
        previous_user = os.environ.get("LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT")
        os.environ["LEXEDITOR_PROJECT_ZOMBOID_PROJECT"] = str(project)
        os.environ["LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT"] = str(user_root)
        service = server.create_server(0)
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1400, "height": 850})
                    errors: list[str] = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(f"http://127.0.0.1:{service.server_port}/", wait_until="domcontentloaded")
                    page.locator(".pz-metadata").wait_for(state="visible")
                    loading = page.locator(".lex-plugin-loading-screen")
                    if loading.count():
                        loading.wait_for(state="detached", timeout=10000)
                    page.wait_for_function("!document.documentElement.classList.contains('lex-loading-live')")
                    screenshot(page, args.screenshots, "00-initial-metadata")
                    tab_texts = page.locator(".lex-plugin-tab").all_inner_texts()
                    assert all("…" not in value and not value.endswith("...") for value in tab_texts), tab_texts
                    assert page.locator('link[href="editor.css"]').count() == 1
                    assert page.locator('script[src="editor.js"]').count() == 1

                    # Render the plugin-owned loading and error states, then restore the live page.
                    page.evaluate("renderLoading('Rendered acceptance loading state')")
                    assert page.locator(".pz-loading").get_by_text("Rendered acceptance loading state").count() == 1
                    page.evaluate("render()")
                    page.locator(".pz-metadata").wait_for(state="visible")
                    page.evaluate("renderLoadError(new Error('Rendered acceptance error state'))")
                    error_panel = page.locator(".lex-information-panel")
                    assert "Project Zomboid could not load" in error_panel.inner_text()
                    assert "Rendered acceptance error state" in error_panel.inner_text()
                    screenshot(page, args.screenshots, "00-error-state")
                    page.evaluate("render()")

                    # Metadata is intentionally tall: semantic controls, help, and its last field stay reachable.
                    navigate(page, "metadata", ".pz-metadata")
                    assert page.locator(".pz-metadata input, .pz-metadata textarea").count() >= 10
                    assert page.locator(".pz-metadata .lex-info-help").count() >= 10
                    assert_layout(page, "metadata-desktop")
                    screenshot(page, args.screenshots, "01-metadata-desktop")

                    # Every structured family must be a real shared Table + Detail view with editable cells.
                    for index, tab in enumerate(STRUCTURED, start=2):
                        navigate(page, tab, ".pz-record-layout")
                        assert page.locator(".pz-record-table.lex-column-list").count() == 1, tab
                        assert page.locator(".pz-record-detail").count() == 1, tab
                        assert page.locator(".pz-record-table .lex-cell-editable").count() >= 1, tab
                        assert page.locator(f".pz-record-detail {SEMANTIC_CONTROL[tab]}").count() >= 1, tab
                        assert page.locator(".pz-record-detail .lex-info-help").count() >= 1, tab
                        identity_text = page.locator('.pz-record-table .lex-column-list-cell[data-column-key="id"] .lex-column-cell-text').first
                        identity_fit = identity_text.evaluate("(node) => ({client:node.clientWidth, scroll:node.scrollWidth, text:node.textContent})")
                        assert identity_fit["scroll"] <= identity_fit["client"] + 1, (tab, identity_fit)
                        for header in page.locator(".pz-record-table .lex-column-list-head-cell .lex-column-sort").all():
                            header_fit = header.evaluate("(node) => ({client:node.clientWidth, scroll:node.scrollWidth, text:node.textContent})")
                            assert header_fit["scroll"] <= header_fit["client"] + 1, (tab, header_fit)
                        assert_layout(page, f"{tab}-desktop")
                        screenshot(page, args.screenshots, f"{index:02d}-{tab}-desktop")

                    # Item data is deliberately multi-page. Exercise search, sort, selection, paging, cell edit and discard.
                    navigate(page, "items", ".pz-record-layout")
                    assert int(page.locator(".lex-page-total").inner_text()) >= 2
                    search = page.get_by_label("Search Items")
                    search.fill("Item054")
                    page.wait_for_function("document.querySelectorAll('.pz-record-table .lex-list-row').length===1")
                    assert page.get_by_text("Item054", exact=True).count() >= 1
                    search.fill("")
                    page.wait_for_function("document.querySelectorAll('.pz-record-table .lex-list-row').length>1")
                    page.locator('.pz-record-table .lex-column-list-head-cell[data-column-key="Weight"]').click()
                    page.wait_for_function("structuredState.items.sort.key==='Weight'")
                    page.locator(".pz-record-table .lex-list-row").nth(1).click()
                    page.get_by_label("Next page").click()
                    page.wait_for_function("structuredState.items.page===1")
                    page.get_by_label("First page").click()
                    page.wait_for_function("structuredState.items.page===0")

                    first_weight = page.locator('.pz-record-table .lex-column-list-cell[data-column-key="Weight"]').first
                    first_weight.dblclick()
                    editor = first_weight.locator("input")
                    editor.fill("0.75")
                    editor.press("Enter")
                    page.wait_for_function("dirtyCount()===1")
                    assert not page.locator("#global-save").is_disabled()
                    assert page.locator('.pz-record-detail input[aria-label="Weight"]').input_value() == "0.75"
                    page.locator("#global-save").click(button="right")
                    page.get_by_role("button", name="Discard Changes").click()
                    page.wait_for_function("dirtyCount()===0")
                    assert page.locator('.pz-record-detail input[aria-label="Weight"]').input_value() == "0.25"

                    # Two edits in the same script file prove SHA refresh across sequential record saves.
                    page.locator('.pz-record-detail input[aria-label="Weight"]').fill("0.75")
                    page.locator('.pz-record-detail input[aria-label="Weight"]').press("Tab")
                    page.locator(".pz-record-table .lex-list-row").nth(1).click()
                    page.locator('.pz-record-detail input[aria-label="Weight"]').fill("0.85")
                    page.locator('.pz-record-detail input[aria-label="Weight"]').press("Tab")
                    page.wait_for_function("dirtyCount()===2")
                    page.keyboard.press("Control+S")
                    # dirtyCount reaches zero while saveAllChanges is still
                    # reloading every PZ endpoint. The shared shell keeps the
                    # UI inert until that async save/reload completes, so wait
                    # for the same user-visible completion boundary before
                    # deliberately reloading the page again.
                    page.wait_for_function(
                        "dirtyCount()===0 && !document.body.classList.contains('lex-save-busy')",
                        timeout=30000,
                    )
                    page.reload(wait_until="domcontentloaded")
                    page.locator(".pz-metadata").wait_for()
                    navigate(page, "items", ".pz-record-layout")
                    page.get_by_label("Search Items").fill("Item000")
                    page.wait_for_function("document.querySelectorAll('.pz-record-table .lex-list-row').length===1")
                    assert page.locator('.pz-record-detail input[aria-label="Weight"]').input_value() == "0.75"
                    page.get_by_label("Search Items").fill("Item001")
                    page.wait_for_timeout(120)
                    assert page.locator('.pz-record-detail input[aria-label="Weight"]').input_value() == "0.85"
                    page.get_by_label("Search Items").fill("NO_SUCH_RECORD")
                    assert page.get_by_text("No items match this search.", exact=True).count() == 1
                    # Clear keystroke-by-keystroke with a value check: a fit
                    # re-render can detach the search input mid-fill and the
                    # framework drops input events from detached nodes.
                    search_clear = page.get_by_label("Search Items")
                    for _ in range(5):
                        search_clear.click()
                        search_clear.press("ControlOrMeta+A")
                        search_clear.press("Backspace")
                        page.wait_for_timeout(200)
                        if search_clear.input_value() == "":
                            break
                    assert search_clear.input_value() == ""
                    page.wait_for_function("document.querySelectorAll('.pz-record-table .lex-list-row').length>1")
                    page.locator(".pz-record-detail .lex-info-help").first.wait_for(state="visible")

                    # Help must be keyboard reachable and expose gameplay-oriented text.
                    help_mark = page.locator(".pz-record-detail .lex-info-help").first
                    help_mark.focus()
                    page.locator(".lex-help-popover").wait_for(state="visible")
                    assert len(page.locator(".lex-help-popover").inner_text().strip()) > 20
                    page.keyboard.press("Escape")

                    # Script Inventory is independently paged/searchable and includes the read-only entity family.
                    navigate(page, "scripts", ".pz-script-layout")
                    assert page.locator(".pz-script-table.lex-column-list").count() == 1
                    assert int(page.locator(".lex-page-total").inner_text()) >= 2
                    script_search = page.get_by_label("Search Build 42 script records")
                    script_search.fill("ReadOnlyEntity")
                    page.wait_for_function("document.querySelectorAll('.pz-script-table .lex-list-row').length===1")
                    assert page.get_by_text("ReadOnlyEntity", exact=True).count() >= 1
                    script_search.fill("")
                    page.wait_for_function("document.querySelectorAll('.pz-script-table .lex-list-row').length>1")
                    assert_layout(page, "scripts-desktop")
                    screenshot(page, args.screenshots, "13-scripts-desktop")

                    # Shell Data Map uses the shared real SVG integration marks and routes to actual editors.
                    page.locator("#plugin-data-map").click()
                    page.locator(".lex-data-map-view").wait_for()
                    assert page.locator(".lex-integration-status .lex-status-mark").count() >= 1
                    assert page.locator(".lex-data-map-open").count() >= 1
                    assert_layout(page, "datamap-desktop")
                    screenshot(page, args.screenshots, "14-datamap-desktop")

                    # Shell Info owns deployment and shared mod-loader documentation.
                    page.locator("#plugin-info").click()
                    page.locator(".lex-information-panel").wait_for()
                    assert page.get_by_text("MOD LOADER", exact=True).count() == 1
                    assert page.get_by_role("button", name="Deploy Local Mod").count() == 1
                    assert page.locator('input.lex-readonly-field[value="Project Zomboid native Build 42 mod system."]').count() == 1
                    assert_layout(page, "info-desktop")
                    screenshot(page, args.screenshots, "15-info-desktop")

                    # Every surface must remain usable at a narrow desktop size.
                    narrow = render_surface_set(page, args.screenshots, "narrow", 820, 700)
                    navigate(page, "items", ".pz-record-layout")
                    narrow_rows = page.locator(".pz-record-table .lex-list-row")
                    assert narrow_rows.count() >= 2
                    narrow_key = narrow_rows.nth(1).get_attribute("data-key")
                    narrow_rows.nth(1).click()
                    page.wait_for_function("(key) => structuredState.items.selected===key", arg=narrow_key)
                    assert page.locator(".pz-record-table").bounding_box()["height"] >= 100
                    assert page.locator(".pz-record-detail").bounding_box()["height"] >= 120

                    # Every surface must also survive the desktop host's maximum 150% UI scale.
                    scaled = render_surface_set(page, args.screenshots, "scale150", 1100, 760, 1.5)
                    navigate(page, "items", ".pz-record-layout")
                    assert page.locator(".pz-record-table").bounding_box()["height"] >= 100
                    assert page.locator(".pz-record-detail").bounding_box()["height"] >= 120
                    assert not errors, errors
                    print({
                        "screens": len(SURFACES),
                        "renderedConfigurations": len(SURFACES) * 3,
                        "items": 55,
                        "narrow": narrow,
                        "scaled": scaled,
                        "result": "Project Zomboid rendered UI acceptance passed",
                    })
                finally:
                    browser.close()
        finally:
            service.shutdown()
            service.server_close()
            thread.join(timeout=5)
            if previous_project is None:
                os.environ.pop("LEXEDITOR_PROJECT_ZOMBOID_PROJECT", None)
            else:
                os.environ["LEXEDITOR_PROJECT_ZOMBOID_PROJECT"] = previous_project
            if previous_user is None:
                os.environ.pop("LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT", None)
            else:
                os.environ["LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT"] = previous_user
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
