# -*- coding: utf-8 -*-
"""Rendered acceptance for Stardew Valley using only synthetic game/project fixtures."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "stardew-valley-browser"
OUT.mkdir(parents=True, exist_ok=True)
LAYOUT_FAILURES: list[dict] = []
(OUT / "started.txt").write_text("Stardew rendered acceptance started.\n", encoding="utf-8")
sys.path.insert(0, str(ROOT))

from games.stardew_valley.content_pack import initialize_project  # noqa: E402
from games.stardew_valley.plugin import StardewValleySession  # noqa: E402
from service_session import request_json  # noqa: E402
from games.stardew_valley.source_data import objects_source_path  # noqa: E402


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

    shutil.copytree(ROOT / "games" / "stardew_valley" / "project_template", project)
    initialize_project(project)
    return game, project


def patch_value(project: Path, object_id: str, field: str):
    data = json.loads((project / "content.json").read_text(encoding="utf-8"))
    for change in data.get("Changes", []):
        if change.get("LogName") == "Lexeditor Data/Objects overrides":
            return change.get("Fields", {}).get(object_id, {}).get(field)
    return None


def geometry(page, label: str) -> dict:
    metrics = page.evaluate("""() => {
      const main=document.querySelector('#main');
      const root=main?.firstElementChild;
      const pager=document.querySelector('.lex-pager');
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
    if metrics["bodyWidth"] > metrics["viewport"][0] + 2:
        failures.append("body horizontal overflow")
    if metrics["bodyHeight"] > metrics["viewport"][1] + 2:
        failures.append("body vertical overflow")
    if metrics["mainScrollWidth"] > metrics["mainWidth"] + 2:
        failures.append("main horizontal overflow")
    if metrics["rootBottom"] > metrics["viewport"][1] + 2:
        failures.append("screen bottom clipped")
    if metrics["pagerBottom"] and metrics["pagerBottom"] > metrics["viewport"][1] + 2:
        failures.append("pager clipped")
    if failures:
        LAYOUT_FAILURES.append({"label": label, "failures": failures, "metrics": metrics})
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
    assert "No Data/Objects records match" in page.locator(".sv-detail").inner_text()
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
        price_editor = price_cell.locator('input[type="number"]')
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
        assert page.locator('[data-lex-property="Price"] input[type="number"]').input_value() == "88"

        drink_cell = stone.locator('[data-column-key="IsDrink"]').first
        drink_cell.dblclick()
        drink_editor = drink_cell.locator('input[type="checkbox"]')
        drink_editor.check()
        page.wait_for_timeout(150)
        assert page.locator('[data-lex-property="IsDrink"] input[type="checkbox"]').is_checked()

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
      window.requestAnimationFrame = callback => {
        window.__svAuditHeldFrame = callback;
        return 1;
      };
    }""")
    page.locator(button_selector).click()
    loading = page.locator("#main .sv-state", has_text=expected)
    loading.wait_for(state="visible", timeout=2000)
    take(page, screenshot_name)
    page.evaluate("""() => {
      const callback = window.__svAuditHeldFrame;
      window.requestAnimationFrame = window.__svAuditRealRAF;
      delete window.__svAuditHeldFrame;
      delete window.__svAuditRealRAF;
      callback?.(performance.now());
    }""")


def exercise_data_map(page, label: str) -> None:
    assert_navigation_loading(page, "#plugin-data-map", "Loading Data Map", f"loading-datamap-{label}.png")
    page.wait_for_selector(".lex-data-map-table .lex-column-list-row")
    assert page.locator(".lex-coverage-icon").count() > 0
    assert page.locator(".lex-pager").count() == 1
    geometry(page, label + "-datamap")
    take(page, f"datamap-{label}.png")
    row = page.locator(".lex-data-map-table .lex-column-list-row").filter(has_text="Objects.xnb").first
    row.click()
    open_button = page.get_by_role("button", name="Open objects", exact=True)
    if open_button.count():
        open_button.click()
        page.wait_for_selector(".sv-table")


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
                for width, height, zoom in ((1440, 900, 1.0), (900, 620, 1.0), (1100, 760, 1.35)):
                    label = f"{width}x{height}-z{zoom}"
                    page, errors = open_editor(browser, session.url, width, height, zoom)
                    try:
                        exercise_objects(page, project, label, mutate=(width == 1440 and zoom == 1.0))
                        exercise_data_map(page, label)
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
        print(json.dumps(results, indent=2))
        if LAYOUT_FAILURES:
            raise AssertionError("Rendered layout failures:\n" + json.dumps(LAYOUT_FAILURES, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
