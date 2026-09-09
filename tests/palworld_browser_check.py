"""Browser acceptance for Palworld package + PalSchema raw patch workspace.

Uses only synthetic package/Patch/schema JSON. No installed game or proprietary Palworld data.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.palworld.plugin import PalworldSession
from games.palworld.package import default_info

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "palworld-browser"
OUT.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory(prefix="lexeditor-palworld-browser-") as temp_name:
    temp = Path(temp_name)
    game = temp / "Palworld"
    (game / "Pal" / "Content" / "Paks").mkdir(parents=True)
    (game / "Palworld.exe").write_bytes(b"")

    schema_root = game / "Mods" / "NativeMods" / "UE4SS" / "Mods" / "PalSchema" / "schemas"
    (schema_root / "raw").mkdir(parents=True)
    (schema_root / "raw" / "DT_PalMonsterParameter.schema.json").write_text(json.dumps({
        "type": "object",
        "additionalProperties": {
            "type": "object",
            "properties": {
                "WorkSuitability_EmitFlame": {"type": "integer", "description": "IntProperty"},
                "DisplayLabel": {"type": "string", "description": "FString"},
                "Mode": {
                    "type": "string",
                    "description": "EnumProperty",
                    "$ref": "../enums.schema.json#/definitions/ETestMode",
                },
                "AddedCount": {"type": "integer", "description": "IntProperty"},
                "NestedPreserved": {"type": "object", "description": "StructProperty", "properties": {}},
            },
        },
    }, indent=2) + "\n", encoding="utf-8")
    (schema_root / "enums.schema.json").write_text(json.dumps({
        "definitions": {"ETestMode": {"type": "string", "enum": ["ModeA", "ModeB"]}}
    }, indent=2) + "\n", encoding="utf-8")

    project = temp / "project"
    project.mkdir()
    info = default_info("BrowserFixture")
    info["Dependencies"] = ["PalSchema"]
    info["Tags"] = ["PalSchema"]
    info["InstallRule"] = [{"Type": "PalSchema", "Targets": ["./PalSchema/"]}]
    (project / "Info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")

    raw = project / "PalSchema" / "Balance" / "raw"
    raw.mkdir(parents=True)
    bad = raw / "aaa_bad.json"
    good = raw / "balance.json"
    commented = raw / "notes.jsonc"

    def reset_patch_fixtures() -> None:
        bad.write_text('{"DT_Broken":', encoding="utf-8")
        good.write_text(json.dumps({
            "DT_PalMonsterParameter": {
                "Kitsunebi": {
                    "WorkSuitability_EmitFlame": 3,
                    "DisplayLabel": "Foxparks",
                    "Mode": "ModeA",
                    "NestedPreserved": {"keep": [1, 2, 3]},
                }
            }
        }, indent=2) + "\n", encoding="utf-8")
        commented.write_text('// keep me\n{"DT_Test":{"Row":{"Value":1}}}\n', encoding="utf-8")
        backup = good.with_name(good.name + ".lexeditor.bak")
        if backup.exists():
            backup.unlink()

    errors = []
    with PalworldSession({
        "LEXEDITOR_PALWORLD_ROOT": str(game),
        "LEXEDITOR_PALWORLD_PROJECT": str(project),
    }) as session:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=shutil.which("chromium") or None,
                headless=True,
                args=["--no-sandbox"],
            )
            try:
                for width, height in ((900, 620), (1280, 800)):
                    reset_patch_fixtures()
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url, wait_until="domcontentloaded")
                    page.wait_for_function("typeof navigate === 'function' && typeof model === 'object' && model !== null && typeof shell === 'object' && shell !== null")

                    # A malformed alphabetically-first patch must not prevent the editor from opening.
                    page.evaluate('navigate("palschema")')
                    page.wait_for_selector(".pal-schema-root")
                    assert page.locator(".pal-schema-state").inner_text() == "SCHEMA-AWARE"
                    selector = page.locator(".pal-patch-toolbar select")
                    assert selector.count() == 1
                    values = selector.locator("option").evaluate_all("nodes=>nodes.map(n=>({value:n.value,text:n.textContent}))")
                    assert values[0]["value"].endswith("aaa_bad.json"), values
                    assert "1 error" in values[0]["text"], values
                    assert selector.input_value().endswith("balance.json"), selector.input_value()

                    # The valid patch uses the generated integer schema and is writable.
                    numeric = page.locator('.pal-schema-columns .pal-detail input[type="number"]')
                    assert numeric.count() >= 1
                    assert "integer" in page.locator(".pal-detail").inner_text().lower()
                    numeric.first.fill("4")
                    page.evaluate("save()")
                    page.wait_for_function("!patchDirty()")
                    disk = json.loads(good.read_text("utf-8"))
                    row = disk["DT_PalMonsterParameter"]["Kitsunebi"]
                    assert row["WorkSuitability_EmitFlame"] == 4, row
                    assert row["NestedPreserved"] == {"keep": [1, 2, 3]}, row
                    assert good.with_name(good.name + ".lexeditor.bak").is_file()

                    # Generated enum definitions become a semantic select and remain schema validated.
                    page.locator(".pal-patch-row").filter(has_text="Mode").click()
                    page.wait_for_timeout(100)
                    enum_select = page.locator(".pal-schema-columns .pal-detail select").filter(has_text="ModeA")
                    assert enum_select.count() >= 1
                    enum_select.first.select_option("ModeB")
                    page.evaluate("save()")
                    page.wait_for_function("!patchDirty()")
                    assert json.loads(good.read_text("utf-8"))["DT_PalMonsterParameter"]["Kitsunebi"]["Mode"] == "ModeB"

                    # Add-property is local/dirty first, then persisted atomically through normal Save.
                    page.locator(".pal-patch-row").filter(has_text="WorkSuitability_EmitFlame").click()
                    page.wait_for_selector(".pal-add-field-select")
                    add_select = page.locator(".pal-add-field-select")
                    assert "AddedCount" in add_select.locator("option").all_text_contents()
                    add_select.select_option("AddedCount")
                    add_value = page.locator('.pal-detail input.pal-add-value[type="number"]')
                    assert add_value.count() == 1
                    add_value.fill("11")
                    page.get_by_role("button", name="Add property", exact=True).click()
                    page.wait_for_function("patchDirty()")
                    assert "AddedCount" not in json.loads(good.read_text("utf-8"))["DT_PalMonsterParameter"]["Kitsunebi"]
                    page.evaluate("save()")
                    page.wait_for_function("!patchDirty()")
                    assert json.loads(good.read_text("utf-8"))["DT_PalMonsterParameter"]["Kitsunebi"]["AddedCount"] == 11

                    # Selecting the malformed patch shows its error locally instead of killing the workspace.
                    selector.select_option(values[0]["value"])
                    page.wait_for_selector(".pal-patch-toolbar .pal-issue.error")
                    assert "Invalid PalSchema" in page.locator(".pal-patch-toolbar .pal-issue.error").inner_text()
                    assert page.locator(".pal-schema-root").count() == 1

                    # JSONC remains discoverable/read-only and its comment survives untouched.
                    jsonc_value = next(row["value"] for row in values if row["value"].endswith("notes.jsonc"))
                    selector.select_option(jsonc_value)
                    page.wait_for_function("palPatch !== null && palPatch.writable === false")
                    assert "keep me" in commented.read_text("utf-8")
                    assert page.locator('.pal-schema-columns .pal-detail input[type="number"]').count() == 0

                    metrics = page.evaluate("""()=>({body:document.body.scrollHeight,viewport:innerHeight,main:document.querySelector('main').scrollHeight,mainHeight:document.querySelector('main').clientHeight})""")
                    assert metrics["body"] <= height + 2, (width, metrics)
                    assert metrics["main"] <= metrics["mainHeight"] + 2, (width, metrics)
                    page.screenshot(path=str(OUT / f"palworld-{width}.png"), full_page=True)
                    page.close()
            finally:
                browser.close()

        if not session.wait_closed():
            raise AssertionError("Palworld browser child service did not close")

assert not errors, errors
print("Palworld browser acceptance passed")
