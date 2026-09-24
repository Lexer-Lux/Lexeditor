# -*- coding: utf-8 -*-
"""Rendered acceptance for Stardew Valley using only synthetic game/project fixtures."""
from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else DEV_CACHE / "stardew-valley-browser"
OUT.mkdir(parents=True, exist_ok=True)
SHARED_UI_MODE = os.environ.get("LEXEDITOR_SHARED_UI_MODE", "branch")
LAYOUT_FAILURES: list[dict] = []
SHARED_LAYOUT_WARNINGS: list[dict] = []
(OUT / "started.txt").write_text("Stardew rendered acceptance started.\n", encoding="utf-8")
sys.path.insert(0, str(ROOT))

from plugins.stardew_valley.content_pack import initialize_project  # noqa: E402
from plugins.stardew_valley.plugin import StardewValleySession  # noqa: E402
from core.service_session import request_json  # noqa: E402
from plugins.stardew_valley.source_data import objects_source_path  # noqa: E402


def make_fixture(root: Path) -> tuple[Path, Path]:
    game = root / "game"
    project = root / "project"
    (game / "Content" / "Data").mkdir(parents=True)
    (game / "Content" / "Data" / "Objects.xnb").write_bytes(b"synthetic objects xnb")
    (game / "Stardew Valley.exe").write_bytes(b"fixture")
    (game / "StardewModdingAPI.exe").write_bytes(b"fixture")
    cp = game / "Mods" / "Content Patcher"
    cp.mkdir(parents=True)
    (cp / "manifest.json").write_text(json.dumps({
        "Name": "Content Patcher",
        "UniqueID": "Pathoschild.ContentPatcher",
        "Version": "2.9.1",
        "MinimumApiVersion": "4.4.0",
    }) + "\n", encoding="utf-8")

    records = {}
    for index in range(1, 96):
        object_id = str(1000 + index)
        records[object_id] = {
            "Name": f"FixtureObject{index:03}",
            "DisplayName": f"Fixture Object {index:03}",
            "Description": f"Synthetic object {index:03} used only for browser acceptance.",
            "Price": index * 3,
            "Edibility": -300 if index % 5 == 0 else index,
            "IsDrink": index % 7 == 0,
        }
    records["390"] = {
        "Name": "Stone",
        "DisplayName": "Stone",
        "Description": "A useful material.",
        "Price": 2,
        "Edibility": -300,
        "IsDrink": False,
    }
    source = objects_source_path(game)
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")

    typed_sources = {
        "BigCraftables": {
            "FixtureLamp": {
                "Name": "Fixture Lamp", "Price": 150, "Fragility": 0,
                "CanBePlacedIndoors": True, "CanBePlacedOutdoors": True,
                "IsLamp": True, "SpriteIndex": 4,
                "CustomFields": {"fixture/nested": "preserve"},
            },
        },
        "Crops": {
            "FixtureCrop": {
                "Name": "Fixture Crop", "RegrowDays": 3, "IsRaised": False,
                "IsPaddyCrop": False, "NeedsWatering": True, "HarvestMethod": "Grab",
                "HarvestMinStack": 1, "HarvestMaxStack": 2, "ExtraHarvestChance": 0.2,
                "SpriteIndex": 7, "CountForMonoculture": True, "CountForPolyculture": False,
                "Seasons": ["Spring"], "DaysInPhase": [1, 2, 3],
            },
        },
        "Fences": {
            "FixtureFence": {"Name": "Fixture Fence", "Health": 100.0, "RemovalDebrisType": 12},
        },
        "FloorsAndPaths": {
            "FixturePath": {
                "Name": "Fixture Path", "RemovalDebrisType": 12, "ShadowType": "None",
                "ConnectType": "Path", "CornerSize": 0,
            },
        },
        "Machines": {
            "FixtureMachine": {
                "Name": "Fixture Machine", "OnlyCompleteOvernight": False,
                "AllowLoadWhenFull": True, "WorkingEffectChance": 0.33,
                "OutputRules": [{"Id": "nested-fixture", "MinutesUntilReady": 30}],
            },
        },
        "Weapons": {
            "FixtureSword": {
                "Name": "Fixture Sword", "Type": 3, "SpriteIndex": 2,
                "MinDamage": 8, "MaxDamage": 14, "CritChance": 0.05,
                "CanBeLostOnDeath": True, "MineBaseLevel": -1, "MineMinLevel": -1,
            },
        },
    }
    for asset, payload in typed_sources.items():
        target = source.parent / f"{asset}.json"
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    typed_sources = {
        "BigCraftables": {
            "FixtureLamp": {
                "Name": "Fixture Lamp", "Price": 150, "Fragility": 0,
                "CanBePlacedIndoors": True, "CanBePlacedOutdoors": True,
                "IsLamp": True, "SpriteIndex": 4,
                "CustomFields": {"fixture/nested": "preserve"},
            },
        },
        "Crops": {
            "FixtureCrop": {
                "Name": "Fixture Crop", "RegrowDays": 3, "IsRaised": False,
                "IsPaddyCrop": False, "NeedsWatering": True, "HarvestMethod": "Grab",
                "HarvestMinStack": 1, "HarvestMaxStack": 2, "ExtraHarvestChance": 0.2,
                "SpriteIndex": 7, "CountForMonoculture": True, "CountForPolyculture": False,
                "Seasons": ["Spring"], "DaysInPhase": [1, 2, 3],
            },
        },
        "Fences": {
            "FixtureFence": {"Name": "Fixture Fence", "Health": 100.0, "RemovalDebrisType": 12},
        },
        "FloorsAndPaths": {
            "FixturePath": {
                "Name": "Fixture Path", "RemovalDebrisType": 12, "ShadowType": "None",
                "ConnectType": "Path", "CornerSize": 0,
            },
        },
        "Machines": {
            "FixtureMachine": {
                "Name": "Fixture Machine", "OnlyCompleteOvernight": False,
                "AllowLoadWhenFull": True, "WorkingEffectChance": 0.33,
                "OutputRules": [{"Id": "nested-fixture", "MinutesUntilReady": 30}],
            },
        },
        "Weapons": {
            "FixtureSword": {
                "Name": "Fixture Sword", "Type": 3, "SpriteIndex": 2,
                "MinDamage": 8, "MaxDamage": 14, "CritChance": 0.05,
                "CanBeLostOnDeath": True, "MineBaseLevel": -1, "MineMinLevel": -1,
            },
        },
    }
    for asset, payload in typed_sources.items():
        target = source.parent / f"{asset}.json"
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    shutil.copytree(ROOT / "plugins" / "stardew_valley" / "project_template", project)
    initialize_project(project)
    return game, project


def patch_value(project: Path, object_id: str, field: str):
    data = json.loads((project / "content.json").read_text(encoding="utf-8"))
    for change in data.get("Changes", []):
        if change.get("LogName") == "Lexeditor Data/Objects overrides":
            return change.get("Fields", {}).get(object_id, {}).get(field)
    return None


def typed_patch_value(project: Path, target: str, record_id: str, field: str):
    data = json.loads((project / "content.json").read_text(encoding="utf-8"))
    log_name = f"Lexeditor {target} overrides"
    for change in data.get("Changes", []):
        if change.get("LogName") == log_name:
            return change.get("Fields", {}).get(record_id, {}).get(field)
    return None


def geometry(page, label: str) -> dict:
    metrics = page.evaluate("""() => {
      const main=document.querySelector('#main');
      const root=main?.firstElementChild;
      const pager=document.querySelector('.lex-pager');
      const zoom=(()=>{const value=parseFloat(getComputedStyle(document.body).zoom);return Number.isFinite(value)&&value>0?value:1;})();
      const offenders=[...document.querySelectorAll('body *')].map(node=>{
        const box=node.getBoundingClientRect();
        return {
          tag:node.tagName.toLowerCase(),
          id:node.id||'',
          className:typeof node.className==='string'?node.className:'',
          left:Math.round(box.left*10)/10,
          right:Math.round(box.right*10)/10,
          width:Math.round(box.width*10)/10
        };
      }).filter(row=>row.right>innerWidth+1||row.left<-1).slice(0,20);
      return {
        zoom,
        viewport:[innerWidth,innerHeight],
        bodyWidth:document.body.scrollWidth,
        bodyHeight:document.body.scrollHeight,
        mainWidth:main?.clientWidth||0,
        mainScrollWidth:main?.scrollWidth||0,
        rootBottom:root?.getBoundingClientRect().bottom||0,
        pagerBottom:pager?.getBoundingClientRect().bottom||0,
        offenders
      };
    }""")
    failures = []
    shared_warnings = []
    # body.style.zoom scales getBoundingClientRect numbers while
    # innerWidth/innerHeight stay in unscaled CSS pixels. A fill-viewport
    # screen can never pass a mixed-unit comparison, so normalize the
    # measured rects into CSS pixels before comparing.
    scale = metrics.get("zoom", 1) or 1
    bodyWidth = metrics["bodyWidth"] / scale
    bodyHeight = metrics["bodyHeight"] / scale
    mainWidth = metrics["mainWidth"] / scale
    mainScrollWidth = metrics["mainScrollWidth"] / scale
    rootBottom = metrics["rootBottom"] / scale
    pagerBottom = (metrics["pagerBottom"] or 0) / scale
    for row in metrics.get("offenders", []):
        row["left"] = round(row["left"] / scale, 1)
        row["right"] = round(row["right"] / scale, 1)
        row["width"] = round(row["width"] / scale, 1)
    if bodyWidth > metrics["viewport"][0] + 2:
        shared_warnings.append("shared shell horizontal overflow")
    if bodyHeight > metrics["viewport"][1] + 2:
        shared_warnings.append("shared document vertical overflow")
    if mainScrollWidth > mainWidth + 2:
        failures.append("main horizontal overflow")
    if rootBottom > metrics["viewport"][1] + 2:
        if SHARED_UI_MODE == "branch" and "-datamap" in label:
            shared_warnings.append("branch shared Data Map bottom overflow")
        else:
            failures.append("screen bottom clipped")
    if pagerBottom and pagerBottom > metrics["viewport"][1] + 2:
        failures.append("pager clipped")
    if failures:
        LAYOUT_FAILURES.append({"label": label, "failures": failures, "metrics": metrics})
    if shared_warnings:
        SHARED_LAYOUT_WARNINGS.append({"label": label, "warnings": shared_warnings, "metrics": metrics})
    return metrics


def take(page, name: str) -> None:
    page.screenshot(path=str(OUT / name), full_page=True)


def open_editor(browser, url: str, width: int, height: int, zoom: float = 1.0):
    page = browser.new_page(viewport={"width": width, "height": height})
    page_errors: list[str] = []
    console_errors: list[str] = []
    network_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("requestfailed", lambda request: network_errors.append(
        f"{request.method} {request.url}: {request.failure or 'request failed'}"
    ))
    page.on("response", lambda response: network_errors.append(
        f"{response.status} {response.request.method} {response.url}"
    ) if response.status >= 400 else None)

    page.goto(url, wait_until="domcontentloaded")
    try:
        page.wait_for_selector(".lex-paged-list-detail .lex-column-list-row", timeout=20000)
        # Current shared UI may render the editor before its minimum loading
        # transition releases pointer/keyboard interaction. Rows existing is
        # necessary but not sufficient for an interactable rendered screen.
        page.wait_for_function(
            "() => !document.documentElement.classList.contains('lex-loading-live')",
            timeout=10000,
        )
        loading_screen = page.locator(".lex-plugin-loading-screen")
        if loading_screen.count():
            loading_screen.wait_for(state="detached", timeout=10000)
    except Exception:
        label = f"{width}x{height}-z{zoom}"
        diagnostics = {
            "requestedUrl": url,
            "pageUrl": page.url,
            "title": page.title(),
            "status": page.locator('[role="status"]').all_inner_texts(),
            "alerts": page.locator('[role="alert"]').all_inner_texts(),
            "mainText": page.locator("#main").inner_text() if page.locator("#main").count() else "",
            "mainHtml": page.locator("#main").inner_html() if page.locator("#main").count() else "",
            "pageErrors": page_errors,
            "consoleErrors": console_errors,
            "networkErrors": network_errors,
        }
        (OUT / f"boot-diagnostics-{label}.json").write_text(
            json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
        page.screenshot(path=str(OUT / f"boot-failure-{label}.png"), full_page=True)
        raise
    if zoom != 1.0:
        page.evaluate("value => { document.body.style.zoom=String(value); }", zoom)
        page.wait_for_timeout(250)
    return page, page_errors + console_errors + network_errors


def exercise_objects(page, project: Path, label: str, *, mutate: bool) -> None:
    assert page.locator("#plugin-data-map").count() == 1
    assert page.locator("#plugin-info").count() == 1
    assert page.locator("link[href='editor.css']").count() == 1
    assert page.locator("script[src='editor.js']").count() == 1
    assert page.locator(".lex-pager").count() == 1
    geometry(page, label + "-objects")
    take(page, f"objects-{label}.png")

    search = page.locator(".lex-pager-search input").first
    search.fill("NO_SUCH_STARDew_OBJECT")
    page.wait_for_timeout(180)
    assert "No Data/Objects records match" in page.locator(".lex-detail-panel").inner_text()
    search.fill("")
    page.wait_for_timeout(180)

    first_before = page.locator(".lex-column-list-row").first.inner_text()
    next_page = page.get_by_role("button", name="Next page", exact=True)
    assert next_page.is_enabled()
    next_page.click()
    page.wait_for_timeout(220)
    first_after = page.locator(".lex-column-list-row").first.inner_text()
    assert first_after != first_before, (label, "next page did not advance")
    page.wait_for_timeout(220)
    assert page.locator(".lex-column-list-row").first.inner_text() == first_after
    page.get_by_role("button", name="Previous page", exact=True).click()

    page.locator('.lex-column-list-head-cell[data-column-key="Price"] .lex-column-sort').click()
    page.wait_for_timeout(180)
    visible = page.locator('.lex-column-list-row [data-column-key="Price"] .lex-column-cell-content').all_inner_texts()
    prices = [int(value.replace(",", "")) for value in visible if value.strip() not in {"", "-"}]
    assert prices == sorted(prices), (label, prices[:12])

    search.fill("Stone")
    page.wait_for_timeout(220)
    stone = page.locator(".lex-column-list-row").filter(has_text="Stone").first
    assert stone.count() == 1
    stone.click()
    assert "Stone" in page.locator(".lex-detail-panel-heading").inner_text()

    help_marker = page.locator('[data-lex-property="Edibility"] .lex-info-help').first
    help_marker.focus()
    tooltip = page.get_by_role("tooltip")
    tooltip.wait_for()
    help_text = tooltip.inner_text().lower()
    assert "energy" in help_text and "health" in help_text and "2.5" in help_text
    help_marker.press("ArrowDown")
    assert tooltip.evaluate("node => document.activeElement === node")
    tooltip.press("Escape")

    if mutate:
        price_cell = stone.locator('[data-column-key="Price"]').first
        assert "lex-cell-editable" in (price_cell.get_attribute("class") or ""), price_cell.evaluate("node => node.outerHTML")
        assert page.locator("html").get_attribute("data-lex-project-readonly") == "false"
        price_cell.dblclick()
        page.wait_for_timeout(120)
        price_editor = price_cell.locator('input[aria-label="Sell price"]')
        if price_editor.count() != 1:
            diagnostics = {
                "cell": price_cell.evaluate("node => node.outerHTML"),
                "readonly": page.locator("html").get_attribute("data-lex-project-readonly"),
                "selected": stone.get_attribute("aria-selected"),
                "activeElement": page.evaluate("() => document.activeElement?.outerHTML || ''"),
            }
            (OUT / f"cell-edit-failure-{label}.json").write_text(
                json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
            take(page, f"cell-edit-failure-{label}.png")
            raise AssertionError("Price cell did not enter edit mode: " + json.dumps(diagnostics))
        price_editor.fill("88")
        price_editor.press("Enter")
        page.wait_for_timeout(180)
        assert page.locator("#global-save").is_enabled()
        assert page.locator('[data-lex-property="Price"] input[aria-label="Sell price"]').input_value() == "88"

        drink_cell = stone.locator('[data-column-key="IsDrink"]').first
        drink_cell.dblclick()
        drink_editor = drink_cell.locator('input[type="checkbox"]')
        drink_editor.click()
        page.wait_for_timeout(150)
        assert page.get_by_role("checkbox", name="Drink", exact=True).is_checked()

        page.locator("#global-save").click()
        page.wait_for_function("() => document.querySelector('#global-save')?.disabled === true")
        assert patch_value(project, "390", "Price") == 88
        assert patch_value(project, "390", "IsDrink") is True

        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(".lex-column-list-row", timeout=20000)
        page.locator(".lex-pager-search input").first.fill("Stone")
        page.wait_for_timeout(180)
        stone = page.locator(".lex-column-list-row").filter(has_text="Stone").first
        assert "88" in stone.locator('[data-column-key="Price"]').inner_text()

        cell = stone.locator('[data-column-key="Price"]').first
        cell.dblclick()
        cell.locator("input").fill("99")
        cell.locator("input").press("Enter")
        assert page.locator("#global-save").is_enabled()
        page.locator("#global-save").click(button="right")
        page.get_by_role("button", name="Discard Changes", exact=True).click()
        page.wait_for_function("() => document.querySelector('#global-save')?.disabled === true")
        page.locator(".lex-pager-search input").first.fill("Stone")
        page.wait_for_timeout(160)
        assert "88" in page.locator(".lex-column-list-row").filter(has_text="Stone").first.locator('[data-column-key="Price"]').inner_text()

        raw = json.loads((project / "content.json").read_text(encoding="utf-8"))
        raw["ExternalFixtureChange"] = True
        (project / "content.json").write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        stone = page.locator(".lex-column-list-row").filter(has_text="Stone").first
        cell = stone.locator('[data-column-key="Price"]').first
        cell.dblclick()
        cell.locator("input").fill("91")
        cell.locator("input").press("Enter")
        page.locator("#global-save").click()
        dialog = page.get_by_role("alertdialog")
        dialog.wait_for()
        assert "changed" in dialog.inner_text().lower()
        assert page.locator("#global-save").is_enabled()
        dialog.get_by_role("button", name="Close", exact=True).click()
        page.locator("#global-save").click(button="right")
        page.get_by_role("button", name="Discard Changes", exact=True).click()
        page.wait_for_function("() => document.querySelector('#global-save')?.disabled === true")

    divider = page.locator(".lex-panel-layout-divider").first
    before = int(divider.get_attribute("aria-valuenow"))
    divider.focus()
    divider.press("Shift+ArrowRight")
    page.wait_for_timeout(150)
    after = int(divider.get_attribute("aria-valuenow"))
    assert after != before, (label, before, after)
    geometry(page, label + "-resized")


def assert_navigation_loading(page, button_selector: str, expected: str, screenshot_name: str) -> None:
    page.evaluate("""() => {
      window.__svAuditRealRAF = window.requestAnimationFrame;
      window.__svAuditHeldFrames = [];
      window.requestAnimationFrame = callback => {
        window.__svAuditHeldFrames.push(callback);
        return window.__svAuditHeldFrames.length;
      };
    }""")
    page.locator(button_selector).click()
    loading = page.locator("#main .lex-notice", has_text=expected)
    loading.wait_for(state="visible", timeout=2000)
    take(page, screenshot_name)
    page.evaluate("""() => {
      const callbacks = window.__svAuditHeldFrames || [];
      window.requestAnimationFrame = window.__svAuditRealRAF;
      delete window.__svAuditHeldFrames;
      delete window.__svAuditRealRAF;
      const now = performance.now();
      for (const callback of callbacks) callback(now);
    }""")


def exercise_data_map(page, label: str) -> None:
    assert_navigation_loading(page, "#plugin-data-map", "Loading Data Map", f"loading-datamap-{label}.png")
    page.wait_for_selector(".lex-data-map-table .lex-column-list-row")
    if SHARED_UI_MODE == "current-master":
        assert page.locator(".lex-integration-status").count() > 0
    else:
        assert page.locator(".lex-coverage-icon, .lex-integration-status").count() > 0
    assert page.locator(".lex-pager").count() == 1
    geometry(page, label + "-datamap")
    take(page, f"datamap-{label}.png")
    row = page.locator(".lex-data-map-table .lex-column-list-row").filter(has_text="Crops.xnb").first
    assert row.count() == 1, (label, "Crops Data Map row missing")
    row.click()
    open_button = page.get_by_role("button", name="Open objects", exact=True)
    if open_button.count():
        open_button.click()
        page.wait_for_selector(".lex-column-list")
    open_button = page.get_by_role("button", name="Open crops", exact=True)
    assert open_button.count() == 1, (label, "Crops open action missing")
    open_button.click()
    page.wait_for_selector(".lex-column-list")


def exercise_typed_data(page, project: Path, label: str, new_value: int) -> None:
    search = page.locator(".lex-pager-search input").first
    search.fill("Fixture Crop")
    page.wait_for_timeout(180)
    crop = page.locator(".lex-column-list-row").filter(has_text="Fixture Crop").first
    assert crop.count() == 1, (label, "fixture crop missing")
    crop.click()
    panel = page.locator(".lex-detail-panel")
    assert "Fixture Crop" in panel.inner_text()
    assert page.locator('select[aria-label="Harvest method"]').count() == 1
    assert page.locator('input[aria-label="Needs watering"]').count() >= 1
    geometry(page, label + "-crops")
    take(page, f"crops-{label}.png")

    override = page.get_by_role("checkbox", name="Override Regrow days", exact=True)
    if not override.is_checked():
        override.click()
    value = page.locator('input[aria-label="Regrow days"]')
    value.fill(str(new_value))
    assert value.input_value() == str(new_value)
    assert page.locator("#global-save").is_enabled()

    # Unsaved edits must survive a Data Map visit and block switching families.
    page.locator("#plugin-data-map").click()
    page.wait_for_selector(".lex-data-map-table .lex-column-list-row")
    objects = page.locator(".lex-data-map-table .lex-column-list-row").filter(has_text="Objects.xnb").first
    objects.click()
    open_objects = page.get_by_role("button", name="Open objects", exact=True)
    assert open_objects.count() == 1
    open_objects.click()
    dialog = page.get_by_role("alertdialog")
    dialog.wait_for()
    assert "save or discard" in dialog.inner_text().lower()
    dialog.get_by_role("button", name="Close", exact=True).click()

    # Return to the current typed family and persist the edit.
    crops = page.locator(".lex-data-map-table .lex-column-list-row").filter(has_text="Crops.xnb").first
    crops.click()
    page.get_by_role("button", name="Open crops", exact=True).click()
    page.wait_for_selector(".lex-column-list")
    page.locator(".lex-pager-search input").first.fill("Fixture Crop")
    page.wait_for_timeout(120)
    page.locator(".lex-column-list-row").filter(has_text="Fixture Crop").first.click()
    assert page.locator('input[aria-label="Regrow days"]').input_value() == str(new_value)
    page.locator("#global-save").click()
    page.wait_for_function("() => document.querySelector('#global-save')?.disabled === true")
    assert typed_patch_value(project, "Data/Crops", "FixtureCrop", "RegrowDays") == new_value

    # Discard must restore the saved typed value.
    override = page.get_by_role("checkbox", name="Override Regrow days", exact=True)
    assert override.is_checked()
    value = page.locator('input[aria-label="Regrow days"]')
    value.fill(str(new_value + 20))
    assert page.locator("#global-save").is_enabled()
    page.locator("#global-save").click(button="right")
    page.get_by_role("button", name="Discard Changes", exact=True).click()
    page.wait_for_function("() => document.querySelector('#global-save')?.disabled === true")
    page.locator(".lex-pager-search input").first.fill("Fixture Crop")
    page.wait_for_timeout(100)
    page.locator(".lex-column-list-row").filter(has_text="Fixture Crop").first.click()
    assert page.locator('input[aria-label="Regrow days"]').input_value() == str(new_value)


def exercise_info(page, label: str, height: int) -> None:
    assert_navigation_loading(page, "#plugin-info", "Loading plugin information", f"loading-info-{label}.png")
    page.wait_for_selector(".lex-information-panel")
    body = page.locator(".lex-information-panel .lex-detail-panel-body")
    body.evaluate("node => { node.scrollTop = node.scrollHeight; }")
    final = page.get_by_role("button", name="Verify Acceptance Evidence", exact=True)
    final.scroll_into_view_if_needed()
    box = final.bounding_box()
    assert box and box["y"] < height and box["y"] + box["height"] > 0, (label, box)
    geometry(page, label + "-info")
    take(page, f"info-{label}.png")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-stardew-browser-") as name:
        root = Path(name)
        game, project = make_fixture(root)
        xnb_before = (game / "Content" / "Data" / "Objects.xnb").read_bytes()
        with StardewValleySession({
            "LEXEDITOR_STARDEW_ROOT": str(game),
            "LEXEDITOR_STARDEW_PROJECT": str(project),
        }) as session, sync_playwright() as play:
            identity = request_json(session.url + "api/plugin")
            assert identity["pluginId"] == "stardew-valley"
            dashboard = request_json(session.url + "api/dashboard")
            data_map = request_json(session.url + "api/datamap")
            objects = request_json(session.url + "api/objects")
            assert dashboard["game"]["ready"] and len(data_map["rows"]) >= 6 and len(objects["rows"]) >= 96
            browser = play.chromium.launch(headless=True, args=["--no-sandbox"])
            results = []
            try:
                for index, (width, height, zoom) in enumerate(((1440, 900, 1.0), (900, 620, 1.0), (1100, 760, 1.35))):
                    label = f"{width}x{height}-z{zoom}"
                    page, errors = open_editor(browser, session.url, width, height, zoom)
                    try:
                        exercise_objects(page, project, label, mutate=(width == 1440 and zoom == 1.0))
                        exercise_data_map(page, label)
                        exercise_typed_data(page, project, label, 4 + index)
                        exercise_info(page, label, height)
                        assert not errors, (label, errors)
                        results.append({"label": label, "passed": True})
                    finally:
                        page.close()
            finally:
                browser.close()
        assert (game / "Content" / "Data" / "Objects.xnb").read_bytes() == xnb_before
        (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        (OUT / "layout-failures.json").write_text(
            json.dumps(LAYOUT_FAILURES, indent=2) + "\n", encoding="utf-8")
        (OUT / "shared-layout-warnings.json").write_text(
            json.dumps(SHARED_LAYOUT_WARNINGS, indent=2) + "\n", encoding="utf-8")
        (OUT / "shared-ui-mode.txt").write_text(SHARED_UI_MODE + "\n", encoding="utf-8")
        print(json.dumps(results, indent=2))
        if LAYOUT_FAILURES:
            raise AssertionError("Rendered layout failures:\n" + json.dumps(LAYOUT_FAILURES, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
