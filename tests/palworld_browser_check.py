"""Browser acceptance for Palworld package + PalSchema raw patch workspace.

Uses only synthetic package/Patch JSON. No installed game or proprietary Palworld data.
"""
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

from games.palworld.plugin import PalworldSession
from games.palworld.package import default_info

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "palworld-browser"
OUT.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory(prefix="lexeditor-palworld-browser-") as temp_name:
    temp = Path(temp_name)
    game = temp / "Palworld"
    (game / "Pal" / "Content" / "Paks").mkdir(parents=True)
    (game / "Palworld.exe").write_bytes(b"")

    project = temp / "project"
    project.mkdir()
    info = default_info("BrowserFixture")
    info["Dependencies"] = ["PalSchema"]
    info["Tags"] = ["PalSchema"]
    info["InstallRule"] = [{"Type": "PalSchema", "Targets": ["./PalSchema/"]}]
    (project / "Info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")

    raw = project / "PalSchema" / "Balance" / "raw"
    raw.mkdir(parents=True)
    (raw / "aaa_bad.json").write_text('{"DT_Broken":', encoding="utf-8")
    good = raw / "balance.json"
    good.write_text(json.dumps({
        "DT_PalMonsterParameter": {
            "Kitsunebi": {
                "WorkSuitability_EmitFlame": 3,
                "DisplayLabel": "Foxparks",
                "NestedPreserved": {"keep": [1, 2, 3]},
            }
        }
    }, indent=2) + "\n", encoding="utf-8")
    commented = raw / "notes.jsonc"
    commented.write_text('// keep me\n{"DT_Test":{"Row":{"Value":1}}}\n', encoding="utf-8")

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
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(session.url, wait_until="domcontentloaded")
                    page.wait_for_selector("#lexeditor-shell")
                    page.wait_for_function("typeof navigate === 'function' && typeof model === 'object' && model !== null")

                    # A malformed alphabetically-first patch must not prevent the editor from opening.
                    page.evaluate('navigate("palschema")')
                    page.wait_for_selector(".pal-schema-root")
                    selector = page.locator(".pal-patch-toolbar select")
                    assert selector.count() == 1
                    values = selector.locator("option").evaluate_all("nodes=>nodes.map(n=>({value:n.value,text:n.textContent}))")
                    assert values[0]["value"].endswith("aaa_bad.json"), values
                    assert "1 error" in values[0]["text"], values
                    assert selector.input_value().endswith("balance.json"), selector.input_value()

                    # The valid patch is editable through a semantic numeric control.
                    numeric = page.locator('.pal-detail input[type="number"]')
                    assert numeric.count() == 1
                    numeric.fill("4")
                    page.evaluate("save()")
                    page.wait_for_function("!patchDirty()")
                    disk = json.loads(good.read_text("utf-8"))
                    row = disk["DT_PalMonsterParameter"]["Kitsunebi"]
                    assert row["WorkSuitability_EmitFlame"] == 4, row
                    assert row["NestedPreserved"] == {"keep": [1, 2, 3]}, row
                    assert good.with_name(good.name + ".lexeditor.bak").is_file()

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
                    assert page.locator('.pal-detail input[type="number"]').count() == 0

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
