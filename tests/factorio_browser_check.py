"""Rendered Factorio acceptance against the real plugin service and synthetic project."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "factorio"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "factorio-browser"
OUT.mkdir(parents=True, exist_ok=True)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_json(url: str, timeout: float = 15) -> dict:
    deadline = time.monotonic() + timeout
    error = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            error = exc
            time.sleep(0.05)
    raise RuntimeError(f"Factorio fixture service did not become ready: {error}")


def post_json(url: str, value: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(value).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


results = []
with tempfile.TemporaryDirectory(prefix="lexeditor-factorio-browser-") as temp_name:
    temp = Path(temp_name)
    project = temp / "project"
    shutil.copytree(FIXTURE, project)
    game = temp / "Factorio"
    for mod in ("base", "space-age", "quality", "elevated-rails"):
        folder = game / "data" / mod
        folder.mkdir(parents=True)
        (folder / "info.json").write_text(json.dumps({
            "name": mod, "version": "2.1.19",
        }), encoding="utf-8")

    # Make the synthetic project large enough to exercise several shared pages.
    source = project / "source" / "data-raw-dump.json"
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["tile"] = {
        "fixture-tile": {"type": "tile", "name": "fixture-tile"},
    }
    for index in range(40):
        item = f"fixture-item-{index:02d}"
        recipe = f"fixture-recipe-{index:02d}"
        raw["item"][item] = {
            "type": "item", "name": item, "stack_size": 100,
        }
        raw["recipe"][recipe] = {
            "type": "recipe", "name": recipe,
            "enabled": True, "energy_required": 0.5,
            "maximum_productivity": 3.0, "categories": ["crafting"],
            "ingredients": [{"type": "item", "name": "iron-plate", "amount": 1}],
            "results": [{"type": "item", "name": item, "amount": 1}],
        }
    source.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()

    port = free_port()
    base_url = f"http://127.0.0.1:{port}/"
    env = os.environ.copy()
    env.update({
        "LEXEDITOR_PORT": str(port),
        "LEXEDITOR_PLUGIN_HOSTED": "1",
        "LEXEDITOR_WINDOW_HOST": "webview2",
        "LEXEDITOR_FACTORIO_PROJECT": str(project),
        "FACTORIO_GAME_ROOT": str(game),
    })
    process = subprocess.Popen(
        [sys.executable, "-m", "plugins.factorio.server"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    try:
        identity = wait_json(base_url + "api/plugin")
        assert identity["pluginId"] == "factorio"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base_url, wait_until="domcontentloaded")
                page.wait_for_selector(".lex-column-list-row")
                page.wait_for_timeout(350)

                # All requested datasets must render through shared Table+Detail.
                for label in ("Recipes", "Items", "Machines", "Technologies"):
                    page.get_by_role("button", name=label, exact=True).click()
                    page.wait_for_selector(".lex-column-list-row")
                    assert page.locator(".lex-paged-list-detail").count() == 1, label
                    assert page.locator(".lex-detail").count() >= 1, label

                # Shared search/paging must reach more than the first page.
                page.get_by_role("button", name="Recipes", exact=True).click()
                next_page = page.get_by_role("button", name="Next page", exact=True)
                assert next_page.is_enabled()
                next_page.click()
                page.wait_for_timeout(150)
                assert page.locator(".lex-page-number").input_value() == "2"
                page.get_by_role("button", name="First page", exact=True).click()
                page.wait_for_timeout(150)

                # Prove shared table-cell edit -> save -> reopen on a real record.
                search = page.get_by_label("Search Factorio Recipes", exact=True)
                search.fill("iron-gear-wheel")
                page.wait_for_timeout(150)
                row = page.locator(".lex-column-list-row").filter(
                    has_text="iron-gear-wheel").first
                row.locator('[data-column-key="energyRequired"]').dblclick()
                cell_input = row.locator(
                    '[data-column-key="energyRequired"] input[type="number"]')
                cell_input.fill("0.75")
                cell_input.press("Enter")
                page.wait_for_function("dirtyCount() === 1")
                page.evaluate("save()")
                page.wait_for_function("dirtyCount() === 0")
                page.evaluate("reopen()")
                page.wait_for_timeout(250)
                search = page.get_by_label("Search Factorio Recipes", exact=True)
                search.fill("iron-gear-wheel")
                page.wait_for_timeout(120)
                assert page.get_by_label(
                    "Crafting time", exact=True).input_value() == "0.75"

                # Discard must restore the last saved value, not the source value.
                craft = page.get_by_label("Crafting time", exact=True)
                craft.fill("1.25")
                craft.blur()
                page.wait_for_function("dirtyCount() === 1")
                page.evaluate("discard()")
                page.wait_for_function("dirtyCount() === 0")
                page.wait_for_timeout(200)
                search = page.get_by_label("Search Factorio Recipes", exact=True)
                search.fill("iron-gear-wheel")
                page.wait_for_timeout(120)
                assert page.get_by_label(
                    "Crafting time", exact=True).input_value() == "0.75"

                # Empty filtered state is rendered rather than leaving stale detail.
                search.fill("definitely-no-such-factorio-record")
                page.get_by_text("No recipes match", exact=True).wait_for()
                search = page.get_by_label("Search Factorio Recipes", exact=True)
                search.fill("")
                page.wait_for_selector(".lex-column-list-row")

                # Exercise each requested editor family before export.
                page.get_by_role("button", name="Items", exact=True).click()
                item_search = page.get_by_label("Search Factorio Items", exact=True)
                item_search.fill("iron-plate")
                page.locator('.lex-column-list-row[data-key="iron-plate"]').click()
                page.wait_for_timeout(120)
                stack = page.get_by_label("Stack size", exact=True)
                stack.fill("250")
                stack.blur()
                page.wait_for_function("dirtyCount() === 1")

                page.get_by_role("button", name="Machines", exact=True).click()
                machine_search = page.get_by_label("Search Factorio Machines", exact=True)
                machine_search.fill("assembling-machine-1")
                page.locator('.lex-column-list-row[data-key="assembling-machine-1"]').click()
                page.wait_for_timeout(120)
                speed = page.get_by_label("Crafting speed", exact=True)
                speed.fill("1.25")
                speed.blur()
                page.wait_for_function("dirtyCount() === 2")

                page.get_by_role("button", name="Technologies", exact=True).click()
                tech_search = page.get_by_label("Search Factorio Technologies", exact=True)
                tech_search.fill("automation")
                page.locator('.lex-column-list-row[data-key="automation"]').click()
                page.wait_for_timeout(120)
                count = page.get_by_label("Research unit count", exact=True)
                count.fill("25")
                count.blur()
                unit_time = page.get_by_label("Research unit time", exact=True)
                unit_time.fill("10")
                unit_time.blur()
                page.wait_for_function("dirtyCount() === 3")

                tech_search.fill("automation-2")
                page.locator('.lex-column-list-row[data-key="automation-2"]').click()
                page.wait_for_timeout(120)
                prerequisites = page.get_by_label("Technology prerequisites", exact=True)
                prerequisites.select_option([])
                page.wait_for_function("dirtyCount() === 4")

                page.evaluate("save()")
                page.wait_for_function("dirtyCount() === 0")
                page.evaluate("reopen()")
                page.wait_for_timeout(250)

                page.get_by_role("button", name="Items", exact=True).click()
                item_search = page.get_by_label("Search Factorio Items", exact=True)
                item_search.fill("iron-plate")
                page.locator('.lex-column-list-row[data-key="iron-plate"]').click()
                page.wait_for_timeout(100)
                assert page.get_by_label("Stack size", exact=True).input_value() == "250"

                page.get_by_role("button", name="Machines", exact=True).click()
                machine_search = page.get_by_label("Search Factorio Machines", exact=True)
                machine_search.fill("assembling-machine-1")
                page.locator('.lex-column-list-row[data-key="assembling-machine-1"]').click()
                page.wait_for_timeout(100)
                assert page.get_by_label("Crafting speed", exact=True).input_value() == "1.25"

                page.get_by_role("button", name="Technologies", exact=True).click()
                tech_search = page.get_by_label("Search Factorio Technologies", exact=True)
                tech_search.fill("automation")
                page.locator('.lex-column-list-row[data-key="automation"]').click()
                page.wait_for_timeout(100)
                assert page.get_by_label("Research unit count", exact=True).input_value() == "25"
                assert page.get_by_label("Research unit time", exact=True).input_value() == "10"
                tech_search.fill("automation-2")
                page.locator('.lex-column-list-row[data-key="automation-2"]').click()
                page.wait_for_timeout(100)
                assert page.get_by_label(
                    "Technology prerequisites", exact=True
                ).locator("option:checked").count() == 0

                # Info/version/DLC and deterministic export action.
                page.evaluate('navigate("info")')
                assert page.get_by_label(
                    "DETECTED VERSION", exact=True).input_value() == "2.1.19"
                assert page.get_by_label(
                    "SPACE AGE", exact=True
                ).input_value() == "installed; active in imported mod set"
                page.get_by_role("button", name="Export Mod", exact=True).click()
                page.get_by_text("Candidate built only", exact=False).wait_for()
                export_name = page.locator(
                    ".factorio-export-result strong").inner_text()
                assert export_name == "lexeditor-factorio-fixture_0.1.0.zip"

                # Data Map must retain partial and explicitly unsupported rows.
                page.evaluate('navigate("datamap")')
                page.wait_for_selector(".lex-data-map-table")
                table_text = page.locator(".lex-data-map-table").inner_text()
                assert "data.raw.recipe" in table_text
                assert page.locator(
                    ".lex-data-map-table .lex-integration-status.partial"
                ).count() > 0
                assert page.locator(
                    ".lex-data-map-table .lex-integration-status"
                ).first.get_attribute("aria-label") in {
                    "Integrated", "Partial", "Not integrated",
                }
                page.get_by_role(
                    "combobox", name="Filter files by integration",
                    exact=True).select_option("not-integrated")
                page.wait_for_timeout(150)
                unavailable_text = page.locator(
                    ".lex-data-map-table").inner_text()
                assert "data.raw.tile" in unavailable_text
                assert "other data.raw prototype types" in unavailable_text

                # Desktop and narrow rendered evidence.
                page.evaluate('navigate("recipes")')
                page.set_viewport_size({"width": 1440, "height": 900})
                page.screenshot(
                    path=str(OUT / "factorio-recipes-1440.png"), full_page=True)
                desktop = page.evaluate("""()=>({
                  body:document.body.scrollHeight, viewport:innerHeight,
                  rows:document.querySelectorAll('.lex-column-list-row').length,
                  detail:!!document.querySelector('.lex-detail')
                })""")
                assert desktop["body"] <= desktop["viewport"] + 2, desktop
                assert desktop["rows"] > 0 and desktop["detail"], desktop

                page.set_viewport_size({"width": 900, "height": 620})
                page.wait_for_timeout(250)
                narrow = page.evaluate("""()=>({
                  body:document.body.scrollHeight, viewport:innerHeight,
                  main:document.querySelector('#main').getBoundingClientRect().toJSON(),
                  identities:[...document.querySelectorAll(
                    '.lex-column-list-row:not(.lex-filler-row) [data-column-key="name"] .lex-column-cell-content'
                  )].map(node=>({text:node.textContent.trim(),client:node.clientWidth,scroll:node.scrollWidth}))
                })""")
                assert narrow["body"] <= narrow["viewport"] + 2, narrow
                assert narrow["identities"], narrow
                assert all(row["scroll"] <= row["client"] + 1 for row in narrow["identities"]), narrow
                assert page.locator(".lex-toast").count() == 0
                page.screenshot(
                    path=str(OUT / "factorio-recipes-900.png"), full_page=True)

                # WebView UI scale is browser/page zoom. Model 150% at a physical
                # 1200x800 surface as an 800x533 CSS viewport rendered at DPR 1.5,
                # rather than CSS zoom (which scales boxes without native relayout).
                scaled_context = browser.new_context(
                    viewport={"width": 800, "height": 533},
                    device_scale_factor=1.5,
                )
                try:
                    scaled_page = scaled_context.new_page()
                    scaled_errors: list[str] = []
                    scaled_page.on(
                        "pageerror", lambda error: scaled_errors.append(str(error)))
                    scaled_page.goto(base_url, wait_until="domcontentloaded")
                    scaled_page.wait_for_selector(".lex-column-list-row")
                    scaled_page.get_by_role(
                        "button", name="Last page", exact=True).click()
                    scaled_page.wait_for_timeout(200)
                    scale_control = scaled_page.get_by_label("UI scale", exact=True)
                    scale_control.evaluate("""input=>{
                      input.value='150';
                      input.setAttribute('aria-valuetext','150%');
                      const output=input.parentElement?.querySelector('output');
                      if(output) output.textContent='150%';
                    }""")
                    scaled = scaled_page.evaluate("""()=>{
                      const masterNode=document.querySelector('.lex-barrelled-master');
                      const master=masterNode?.getBoundingClientRect();
                      const identityNodes=[...document.querySelectorAll(
                        '.lex-column-list-row:not(.lex-filler-row) [data-column-key="name"] .lex-column-cell-content'
                      )];
                      return {
                        body:document.body.scrollHeight,
                        viewport:innerHeight,
                        master:master?.toJSON(),
                        detail:document.querySelector('.lex-detail')?.getBoundingClientRect().toJSON(),
                        identities:identityNodes.map(node=>({
                          text:node.textContent.trim(),client:node.clientWidth,scroll:node.scrollWidth
                        })),
                        visibleIdentities:master ? identityNodes.filter(node=>{
                          const rect=node.getBoundingClientRect();
                          return rect.bottom>master.top+1 && rect.top<master.bottom-1
                            && rect.right>master.left && rect.left<master.right;
                        }).map(node=>node.textContent.trim()) : [],
                        center:document.querySelector('.lex-shell-center-actions')?.getBoundingClientRect().toJSON(),
                        right:document.querySelector('.lex-shell-right-actions')?.getBoundingClientRect().toJSON()
                      };
                    }""")
                    assert scaled["body"] <= scaled["viewport"] + 2, scaled
                    assert scaled["master"] and scaled["master"]["height"] >= 100, scaled
                    assert scaled["detail"], scaled
                    assert scaled["master"]["bottom"] <= scaled["detail"]["top"] + 1, scaled
                    assert scaled["visibleIdentities"], scaled
                    assert scaled["identities"], scaled
                    assert all(
                        row["scroll"] <= row["client"] + 1
                        for row in scaled["identities"]), scaled
                    assert scaled["center"]["right"] <= scaled["right"]["left"] + 1, scaled
                    assert scaled_page.locator(".lex-toast").count() == 0
                    assert not scaled_errors, scaled_errors
                    scaled_page.screenshot(
                        path=str(OUT / "factorio-recipes-150pct.png"),
                        full_page=True)
                finally:
                    scaled_context.close()

                assert not errors, errors
                results.append({
                    "identity": identity,
                    "desktop": desktop,
                    "narrow": narrow,
                    "scaled150": scaled,
                    "pagination": "recipes page 2 reached",
                    "edit": "recipe/item/machine/technology edits saved and reopened",
                    "references": "automation-2 prerequisites cleared through validated multi-select",
                    "discard": "recipe 1.25 discarded back to saved 0.75",
                    "export": export_name,
                    "status": "passed",
                })
                page.close()
            finally:
                browser.close()

        # Inspect the delivered candidate, not just the button response.
        candidate = project / "build" / "lexeditor-factorio-fixture_0.1.0.zip"
        assert candidate.is_file()
        with zipfile.ZipFile(candidate) as archive:
            info = json.loads(archive.read(
                "lexeditor-factorio-fixture_0.1.0/info.json"))
            patch = archive.read(
                "lexeditor-factorio-fixture_0.1.0/data-final-fixes.lua").decode("utf-8")
        assert info["factorio_version"] == "2.1"
        assert "? fixture-source" in info["dependencies"]
        assert "? space-age" in info["dependencies"]
        assert "? disabled-source" not in info["dependencies"]
        assert "p.energy_required = 0.75" in patch
        assert "p.stack_size = 250" in patch
        assert "p.crafting_speed = 1.25" in patch
        assert "p.unit.count = 25" in patch
        assert "p.unit.time = 10" in patch
        assert "p.prerequisites = {}" in patch
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash

        candidate_sha256 = hashlib.sha256(candidate.read_bytes()).hexdigest()
        results[-1]["candidateSha256"] = candidate_sha256
        (OUT / "FACTORIO-2.1-ACCEPTANCE.txt").write_text(
            f"""Factorio 2.1.x isolated acceptance for PR #492
Candidate: {candidate.name}
SHA-256: {candidate_sha256}

This is a synthetic acceptance candidate built by the rendered harness. It only
edits existing Factorio base prototype identities. fixture-source and space-age
are optional load-order dependencies; neither is required for this candidate.

1. Confirm Factorio reports a 2.1.x version.
2. Create an empty temporary mods directory outside your normal Factorio profile.
3. Copy only {candidate.name} into that directory.
4. Launch Factorio with: factorio.exe --mod-directory "<temporary mods directory>"
5. In Mods, enable "Lexeditor Factorio Fixture" and let Factorio restart if asked.
6. Confirm startup reaches the main menu with no prototype-stage error. Save the
   startup log if Factorio reports an error.
7. In a disposable game / Factoriopedia, verify these generated overrides:
   - iron-gear-wheel recipe crafting time: 0.75 s
   - iron-plate stack size: 250
   - assembling-machine-1 crafting speed: 1.25
   - automation technology unit count: 25
   - automation technology unit time: 10 s
   - automation-2 has no prerequisite technologies
8. Exit Factorio, remove the generated ZIP from the temporary mod directory, and
   relaunch with the same --mod-directory. Confirm the fixture mod is gone.

For a real Lexeditor project candidate, repeat with the same Factorio 2.1.x
installation and enabled source-mod profile used to produce data-raw-dump.json.
Do not treat this synthetic candidate as proof of compatibility with a particular
third-party mod until that exact profile is loaded in Factorio.
""",
            encoding="utf-8",
        )

        # Stale imported source must block subsequent deployment/export.
        source.write_bytes(source_bytes + b"\n")
        try:
            post_json(base_url + "api/export", {})
            raise AssertionError("export unexpectedly accepted a changed source dump")
        except urllib.error.HTTPError as error:
            body = json.loads(error.read().decode("utf-8"))
            assert error.code == 400
            assert "changed after this editor opened" in body["error"]
        finally:
            source.write_bytes(source_bytes)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash

        shutil.copy2(candidate, OUT / candidate.name)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.returncode not in (0, -15, 1):
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(
                f"Factorio fixture service exited {process.returncode}: {output}")

(OUT / "results.json").write_text(
    json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
