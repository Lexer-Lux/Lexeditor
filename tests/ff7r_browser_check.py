"""Rendered FF7R editor acceptance using production HTML and synthetic data only.

This intentionally does not use an installed game, network, native WebView host,
or proprietary cooked assets. It exercises the real FF7R editor and shared UI
with in-memory API fixtures, then writes screenshots for human inspection.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]

MISC = "Fixture/GameContents/DataObject/MiscData"
EQUIPMENT = "Fixture/GameContents/DataObject/Equipment"
ITEM = "Fixture/GameContents/DataObject/Item"
MATERIA = "Fixture/GameContents/DataObject/Materia"
PLAYER = "Fixture/GameContents/DataObject/PlayerParameter"
ABILITY = "Fixture/GameContents/DataObject/BattleAbility"
ENEMY = "Fixture/GameContents/Field/Test/EnemyParameter"
LOOT = "Fixture/GameContents/DataObject/BattleItemPossession"
TWEAK = "Lexeditor/RuntimeTweaks"
TEXT = "Fixture/GameContents/Text/US/Resident_txtres"


def prop(name: str, kind: str = "INT32", *, array: bool = False,
         editable: bool = True, minimum=None, maximum=None) -> dict:
    if minimum is None and kind in {"BYTE", "INT16", "UINT16", "INT32"}:
        minimum = 0 if kind in {"BYTE", "UINT16"} else -2147483648
    if maximum is None and kind in {"BYTE", "INT16", "UINT16", "INT32"}:
        maximum = 255 if kind == "BYTE" else 2147483647
    if kind == "BOOL":
        minimum, maximum = 0, 1
    return {
        "name": name,
        "label": name.replace("_Array", "").replace("_", " "),
        "type": kind,
        "typeCode": 0,
        "array": array,
        "editable": editable,
        "min": minimum,
        "max": maximum,
    }


def table(asset: str, properties: list[dict], rows: list[tuple[str, dict]]) -> dict:
    return {
        "asset": asset,
        "sourceSha256": "1" * 64,
        "activeSha256": "2" * 64,
        "usingProject": False,
        "exportName": Path(asset).name,
        "names": ["Potion", "Ether", "Enabled", "Disabled"],
        "textLookup": {},
        "properties": properties,
        "records": [
            {"id": index, "tag": tag, "values": values}
            for index, (tag, values) in enumerate(rows)
        ],
    }


def fixtures() -> dict:
    data = {
        MISC: table(
            MISC,
            [prop("Power"), prop("Enabled", "BOOL")],
            [(f"MISC_{i:03}", {"Power": 10 + i, "Enabled": i % 2 == 0}) for i in range(54)],
        ),
        EQUIPMENT: table(
            EQUIPMENT,
            [prop("BuyValue"), prop("SaleValue"), prop("CanSale", "BYTE"), prop("MaxCount")],
            [("EQ_001", {"BuyValue": 500, "SaleValue": 250, "CanSale": 1, "MaxCount": 1})],
        ),
        ITEM: table(
            ITEM,
            [prop("BuyValue"), prop("SaleValue"), prop("CanSale", "BYTE"), prop("MaxCount")],
            [("IT_001", {"BuyValue": 50, "SaleValue": 25, "CanSale": 1, "MaxCount": 99})],
        ),
        MATERIA: table(
            MATERIA,
            [prop("BuyValue"), prop("SaleValue"), prop("CanSale", "BYTE"), prop("MaxCount")],
            [("MA_001", {"BuyValue": 1000, "SaleValue": 500, "CanSale": 1, "MaxCount": 99})],
        ),
        PLAYER: table(
            PLAYER,
            [prop(name) for name in ("HPMax", "MPMax", "Strength", "Magic", "Vitality", "Spilit")],
            [("Cloud", {"HPMax": 1000, "MPMax": 100, "Strength": 50, "Magic": 40, "Vitality": 45, "Spilit": 42})],
        ),
        ABILITY: table(
            ABILITY, [prop("ATB")],
            [("Braver", {"ATB": 1}), ("FocusedThrust", {"ATB": 1})],
        ),
        ENEMY: table(
            ENEMY,
            [prop(name) for name in ("HPMax", "BPMax", "Strength", "Magic", "Vitality", "Spilit")],
            [("GuardScorpion", {"HPMax": 9000, "BPMax": 100, "Strength": 40, "Magic": 30, "Vitality": 50, "Spilit": 40})],
        ),
        LOOT: table(
            LOOT,
            [
                prop("NormalItem_Array", "ENUM", array=True),
                prop("NormalPercent_Array", "BYTE", array=True),
                prop("RareItem_Array", "ENUM", array=True),
                prop("RarePercent_Array", "BYTE", array=True),
                prop("StealItem_Array", "ENUM", array=True),
                prop("StealValue_Array", "BYTE", array=True),
            ],
            [("Battle_001", {
                "NormalItem_Array": ["Potion"], "NormalPercent_Array": [60],
                "RareItem_Array": ["Ether"], "RarePercent_Array": [10],
                "StealItem_Array": ["Potion"], "StealValue_Array": [25],
            })],
        ),
        TWEAK: table(
            TWEAK,
            [prop("Enabled", "BOOL"), prop("Multiplier", "FLOAT", minimum=0.25, maximum=4.0)],
            [("Runtime", {"Enabled": True, "Multiplier": 1.25})],
        ),
    }
    text = {
        "asset": TEXT,
        "language": "US",
        "sourceUassetSha256": "3" * 64,
        "sourceUexpSha256": "4" * 64,
        "activeUassetSha256": "5" * 64,
        "activeUexpSha256": "6" * 64,
        "usingProject": False,
        "records": [
            {"id": 0, "key": "TXT_EQ", "text": "Fixture Blade", "subentries": []},
            {"id": 1, "key": "DESC_EQ", "text": "A fixture sword.", "subentries": [{"id": "ACTOR", "text": "Cloud"}]},
            {"id": 2, "key": "TXT_IT", "text": "Fixture Potion", "subentries": []},
            {"id": 3, "key": "DESC_IT", "text": "A fixture item.", "subentries": []},
            {"id": 4, "key": "TXT_MA", "text": "Fixture Materia", "subentries": []},
            {"id": 5, "key": "DESC_MA", "text": "A fixture materia.", "subentries": []},
        ],
    }
    assets = [
        {"asset": MISC, "name": "Misc Fixture", "group": "DataObject"},
        {"asset": EQUIPMENT, "name": "Equipment", "group": "DataObject"},
        {"asset": ITEM, "name": "Item", "group": "DataObject"},
        {"asset": MATERIA, "name": "Materia", "group": "DataObject"},
        {"asset": PLAYER, "name": "PlayerParameter", "group": "DataObject"},
        {"asset": ABILITY, "name": "BattleAbility", "group": "DataObject"},
        {"asset": ENEMY, "name": "EnemyParameter", "group": "DataObject"},
        {"asset": LOOT, "name": "BattleItemPossession", "group": "DataObject"},
        {"asset": TWEAK, "name": "Runtime Tweaks", "group": "Lexeditor Runtime", "synthetic": "runtime-settings"},
    ]
    economy = {
        "available": True,
        "tables": [
            {"available": True, "asset": EQUIPMENT, "name": "Equipment",
             "rows": [{"id": "EQ_001", "name": "Fixture Blade", "textId": "TXT_EQ", "descriptionId": "DESC_EQ"}]},
            {"available": True, "asset": ITEM, "name": "Item",
             "rows": [{"id": "IT_001", "name": "Fixture Potion", "textId": "TXT_IT", "descriptionId": "DESC_IT"}]},
            {"available": True, "asset": MATERIA, "name": "Materia",
             "rows": [{"id": "MA_001", "name": "Fixture Materia", "textId": "TXT_MA", "descriptionId": "DESC_MA"}]},
        ]
    }
    loot = {
        "available": True,
        "asset": LOOT,
        "itemChoices": [{"id": "Potion", "name": "Potion"}, {"id": "Ether", "name": "Ether"}],
        "groups": [
            {"kind": "normal", "itemProperty": "NormalItem_Array", "percentProperty": "NormalPercent_Array"},
            {"kind": "rare", "itemProperty": "RareItem_Array", "percentProperty": "RarePercent_Array"},
            {"kind": "steal", "itemProperty": "StealItem_Array", "quantityProperty": "StealValue_Array"},
        ],
    }
    map_rows = []
    targets = [MISC, EQUIPMENT, ITEM, MATERIA, PLAYER, ABILITY, ENEMY, LOOT, TWEAK]
    coverages = ["structured", "view", "source", "unavailable"]
    for index in range(48):
        coverage = coverages[index % len(coverages)]
        map_rows.append({
            "id": f"fixture-{index}",
            "filename": f"fixture/resource-{index:02}.uasset",
            "target": targets[index % len(targets)],
            "controls": f"Fixture control surface {index:02}",
            "notes": "Synthetic browser acceptance row. " * 3,
            "coverage": coverage,
            "status": "partial" if coverage != "unavailable" else "not-integrated",
        })
    info = {
        "gameRoot": "C:/Synthetic/FF7R",
        "dataObjects": len(assets),
        "textResources": 1,
        "textLanguages": ["US"],
        "pakVersion": "fixture-v4",
        "helper": {"installed": False, "version": "0.2.3"},
        "projectRoot": "C:/Synthetic/FF7R-Project",
        "buildPath": "C:/Synthetic/FF7R-Project/build/Lexeditor-FF7R_P.pak",
        "deployPath": "C:/Synthetic/FF7R/End/Content/Paks/~mods/Lexeditor-FF7R_P.pak",
        "pakMountPoint": "../../../",
        "projectDeployment": {
            "path": "C:/Synthetic/FF7R/End/Content/Paks/~mods/Lexeditor-FF7R_P.pak",
            "exists": True, "managed": True, "state": "managed", "sha256": "a" * 64,
        },
    }
    return {
        "catalog": {"assets": assets, "textAssets": [{"asset": TEXT, "name": "Resident Text", "group": "Text", "language": "US"}]},
        "data": data, "text": {TEXT: text}, "economy": economy, "loot": loot,
        "datamap": {"rows": map_rows}, "info": info,
        "modLoading": json.loads((ROOT / "ui" / "mod-loading.json").read_text(encoding="utf-8")),
        "credits": json.loads((ROOT / "ui" / "credits.json").read_text(encoding="utf-8")),
        "distributionNotices": [],
    }


def document() -> str:
    fixture = fixtures()
    stub = r"""
window.__fixture = FIXTURE;
window.__requests = [];
window.__saveCounter = 0;
history.replaceState = () => {};
history.pushState = () => {};
const cloneFixture = value => JSON.parse(JSON.stringify(value));
window.fetch = async function(input, options={}) {
  // set_content() leaves location.href as about:blank; resolve against the
  // document's explicit synthetic <base> instead, exactly as real relative
  // browser requests would.
  const url = new URL(String(input), document.baseURI);
  const path = url.pathname;
  const body = options.body ? JSON.parse(options.body) : null;
  window.__requests.push({path, method: options.method || "GET", body});
  let data = null, status = 200;
  if(path === "/api/catalog") data = window.__fixture.catalog;
  else if(path === "/api/datamap") data = window.__fixture.datamap;
  else if(path === "/api/info") data = window.__fixture.info;
  else if(path === "/mod-loading.json" || path === "/shared/mod-loading.json") data = window.__fixture.modLoading;
  else if(path === "/credits.json" || path === "/shared/credits.json") data = window.__fixture.credits;
  else if(path === "/distribution-notices.json" || path === "/shared/distribution-notices.json") data = window.__fixture.distributionNotices;
  else if(path === "/api/economy") data = window.__fixture.economy;
  else if(path === "/api/loot") data = window.__fixture.loot;
  else if(path === "/api/data") {
    data = window.__fixture.data[url.searchParams.get("asset")];
    if(!data){data={error:"Synthetic DataObject not found"};status=404;}
  }
  else if(path === "/api/text") {
    data = window.__fixture.text[url.searchParams.get("asset")];
    if(!data){data={error:"Synthetic text resource not found"};status=404;}
  }
  else if(path === "/api/save") {
    const table = window.__fixture.data[body.asset];
    if(!table){data={error:"Synthetic save target not found"};status=404;}
    else {
      for(const edit of body.edits || []) {
        const row = table.records[edit.entry], value = edit.value;
        if(edit.index === undefined || edit.index === null) row.values[edit.property] = value;
        else row.values[edit.property][edit.index] = value;
      }
      table.activeSha256 = String(++window.__saveCounter).padStart(64,"b");
      table.usingProject = true;
      data = {saved:(body.edits||[]).length, activeSha256:table.activeSha256};
    }
  }
  else if(path === "/api/text/save") {
    const pack = window.__fixture.text[body.asset];
    if(!pack){data={error:"Synthetic text save target not found"};status=404;}
    else {
      for(const edit of body.edits || []) {
        const row=pack.records[edit.entry];
        if(edit.subId){
          const sub=(row.subentries||[]).find(value=>value.id===edit.subId);
          if(sub)sub.text=edit.text;
        } else row.text=edit.text;
      }
      pack.activeUassetSha256 = String(++window.__saveCounter).padStart(64,"c");
      pack.activeUexpSha256 = String(++window.__saveCounter).padStart(64,"d");
      pack.usingProject = true;
      data = {saved:(body.edits||[]).length,
              activeUassetSha256:pack.activeUassetSha256,
              activeUexpSha256:pack.activeUexpSha256};
    }
  }
  else if(path === "/api/deploy/remove") {
    const deployment=window.__fixture.info.projectDeployment;
    deployment.exists=false;deployment.managed=false;deployment.state="absent";deployment.sha256="";
    data={...deployment,removed:true};
  }
  else if(path === "/api/build") data={path:"C:/Synthetic/build/Lexeditor-FF7R_P.pak",size:1234};
  else if(path === "/api/deploy") data={path:window.__fixture.info.deployPath,size:1234,managed:true};
  else {data={error:"Unexpected synthetic request: "+path};status=404;}
  return new Response(JSON.stringify(cloneFixture(data)), {
    status, headers:{"Content-Type":"application/json"}
  });
};
""".replace("FIXTURE", json.dumps(fixture))
    html = (ROOT / "plugins/ff7r/editor.html").read_text(encoding="utf-8")
    html = html.replace("<head>", '<head><base href="https://lexeditor.test/">', 1)
    html = html.replace(
        '<link rel="stylesheet" href="/shared/framework.css">',
        "<style>" + (ROOT / "ui/framework.css").read_text(encoding="utf-8") + "</style>",
    )
    html = html.replace(
        '<script src="/shared/framework.js"></script>',
        "<script>" + stub + "</script><script>"
        + (ROOT / "ui/framework.js").read_text(encoding="utf-8") + "</script>",
    )
    # Match the repository-wide rendered harness: after the shared framework is
    # inlined, replace every plugin-local module exactly where production loads
    # it. This keeps editor.js after LexeditorUI has been defined.
    folder = ROOT / "plugins" / "ff7r"
    html = re.sub(
        r'<script src="(?!/shared/)/?([A-Za-z0-9_./-]+\.js)"></script>',
        lambda match: "<script>"
        + (folder / Path(match[1]).name).read_text(encoding="utf-8").replace("</script", "<\\/script")
        + "</script>",
        html,
    )
    html = re.sub(
        r'<link rel="stylesheet" href="(?!/shared/)/?([A-Za-z0-9_./-]+\.css)">',
        lambda match: "<style>"
        + (folder / Path(match[1]).name).read_text(encoding="utf-8")
        + "</style>",
        html,
    )
    return html


def assert_layout(page, width: int, height: int) -> dict:
    metrics = page.evaluate("""() => {
      const main=document.querySelector("#main")?.getBoundingClientRect();
      const header=document.querySelector(".lex-shell-header")?.getBoundingClientRect();
      return {
        viewportWidth:innerWidth, viewportHeight:innerHeight,
        bodyWidth:document.body.scrollWidth, bodyHeight:document.body.scrollHeight,
        mainLeft:main?.left, mainRight:main?.right, mainTop:main?.top, mainBottom:main?.bottom,
        headerBottom:header?.bottom,
      };
    }""")
    assert metrics["bodyWidth"] <= metrics["viewportWidth"] + 2, (width, height, metrics)
    assert metrics["bodyHeight"] <= metrics["viewportHeight"] + 2, (width, height, metrics)
    assert metrics["mainLeft"] >= -1 and metrics["mainRight"] <= metrics["viewportWidth"] + 1, metrics
    assert metrics["headerBottom"] <= metrics["mainTop"] + 1, metrics
    assert metrics["mainBottom"] <= metrics["viewportHeight"] + 1, metrics
    return metrics


def new_page(browser, html: str, physical_width: int, physical_height: int,
             scale: float = 1.0, diagnostic: Path | None = None):
    css_width = round(physical_width / scale)
    css_height = round(physical_height / scale)
    context = browser.new_context(
        viewport={"width": css_width, "height": css_height},
        device_scale_factor=scale,
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def route_request(route):
        request = route.request
        if request.resource_type == "document" and request.url.rstrip("/") == "https://lexeditor.test":
            route.fulfill(status=200, content_type="text/html", body=html)
        else:
            route.abort()

    page.route("**/*", route_request)
    # set_content() creates an opaque document whose sessionStorage access is
    # denied in Chromium. The production shared shell legitimately uses web
    # storage, so render the same synthetic page from a routed HTTPS origin.
    page.goto("https://lexeditor.test/", wait_until="domcontentloaded")
    page.wait_for_timeout(100)
    try:
        booted = page.evaluate(
            "() => { try { return typeof state !== 'undefined'; } catch (_error) { return false; } }"
        )
    except Exception as error:
        errors.append(f"boot probe failed: {error}")
        booted = False
    if not booted:
        details = {
            "reason": "FF7R editor state missing after modular boot",
            "pageErrors": errors,
            "scripts": page.locator("script").count(),
            "body": page.locator("body").inner_text()[:1200],
        }
        if diagnostic is not None:
            diagnostic.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(diagnostic), full_page=True)
            diagnostic.with_suffix(".json").write_text(
                json.dumps(details, indent=2), encoding="utf-8")
        raise AssertionError(details)
    page.wait_for_function("() => state.catalog && state.data && !state.busy")
    page.wait_for_function(
        "() => !document.querySelector('.lex-plugin-loading-screen')",
        timeout=5000,
    )
    return context, page, errors


def exercise_editor(browser, output: Path, html: str) -> list[dict]:
    results = []
    context, page, errors = new_page(
        browser, html, 1200, 800, diagnostic=output / "boot-failure.png")
    try:
        initial = page.evaluate("""() => ({
          tab: state.tab,
          asset: state.asset,
          busy: state.busy,
          records: state.data?.records?.length ?? null,
          properties: (state.data?.properties || []).map(prop => [prop.name, prop.type, prop.editable]),
          mainText: document.querySelector("#main")?.innerText?.slice(0, 2000) || "",
          detailCount: document.querySelectorAll(".ff7r-detail").length,
          numberInputs: [...document.querySelectorAll('input[type="number"]')].map(input => ({
            value: input.value,
            aria: input.getAttribute("aria-label"),
            disabled: input.disabled
          }))
        })""")
        (output / "initial-render.json").write_text(
            json.dumps(initial, indent=2), encoding="utf-8")
        page.screenshot(path=str(output / "initial-render-1200.png"), full_page=True)

        expect(page.locator(".ff7r-table .lex-column-list-row")).not_to_have_count(0)
        power = page.get_by_role("textbox", name="Power", exact=True)
        expect(power).to_have_value("10")

        power.fill("77")
        page.wait_for_function("dirtyCount()===1")
        expect(page.locator("#global-save")).to_be_enabled()
        page.locator("#global-undo").click()
        expect(power).to_have_value("10")
        page.locator("#global-redo").click()
        expect(power).to_have_value("77")

        page.locator("#global-save").click()
        page.wait_for_function("dirtyCount()===0")
        save_requests = page.evaluate(
            "window.__requests.filter(row=>row.path==='/api/save' && row.method==='POST')")
        assert save_requests[-1]["body"]["edits"] == [
            {"entry": 0, "property": "Power", "value": 77}
        ], save_requests[-1]

        page.evaluate("loadAsset(state.asset)")
        page.wait_for_function("state.data && !state.busy")
        power = page.get_by_role("textbox", name="Power", exact=True)
        expect(power).to_have_value("77")
        assert page.evaluate("state.data.usingProject") is True

        power.fill("88")
        page.wait_for_function("dirtyCount()===1")
        page.locator("#global-save").click(button="right")
        expect(page.get_by_role("button", name="Discard Changes", exact=True)).to_be_visible()
        page.get_by_role("button", name="Discard Changes", exact=True).click()
        page.wait_for_function("dirtyCount()===0")
        power = page.get_by_role("textbox", name="Power", exact=True)
        expect(power).to_have_value("77")
        page.screenshot(path=str(output / "edit-save-discard-1200.png"), full_page=True)

        # Every first-class screen gets a real render with the synthetic
        # response shape it expects. This catches tab-specific runtime errors
        # without pretending the fixture proves retail-game semantics.
        for tab in ("equipment", "item", "materia", "characters", "abilities",
                    "enemies", "loot", "tweaks", "text"):
            page.evaluate("tab => { void navigate(tab); }", tab)
            page.wait_for_function(
                "tab => state.tab===tab && !state.busy && !state.textBusy && !(state.tweaksPending>0)",
                arg=tab,
            )
            assert page.evaluate("state.tab") == tab
            text = page.locator("#main").inner_text()
            assert text.strip(), tab
            assert "Resource unavailable" not in text, tab
            if tab in {"equipment", "item", "materia"}:
                assert "Item settings unavailable" not in text, tab
                expect(page.locator(".ff7r-table")).to_be_visible()
                assert page.locator(".ff7r-table .lex-column-list-row").count() > 0, tab
            page.screenshot(path=str(output / f"screen-{tab}.png"), full_page=True)

        # Return to the explicit misc fixture.
        page.evaluate("asset => { state.asset=asset; void loadAsset(asset); }", MISC)
        page.wait_for_function(
            "asset => state.asset===asset && state.data && !state.busy", arg=MISC)
        page.evaluate("() => { void navigate('misc'); }")
        page.wait_for_function("() => state.tab==='misc' && state.data && !state.busy")

        page.locator("#plugin-data-map").click()
        page.wait_for_selector(".lex-data-map-table")
        integration = page.get_by_role("combobox", name="Filter files by integration", exact=True)
        integration.select_option("not-integrated")
        page.wait_for_timeout(200)
        expect(integration).to_have_value("not-integrated")
        view_rows = page.locator(".lex-data-map-table .lex-column-list-row")
        expect(view_rows).to_have_count(12)
        view_text = page.locator(".lex-data-map-table").inner_text()
        assert "fixture/resource-03.uasset" in view_text
        assert "fixture/resource-07.uasset" in view_text
        assert "fixture/resource-00.uasset" not in view_text
        expect(page.locator('.lex-data-map-table .lex-integration-status[aria-label="Not integrated"]')).to_have_count(12)
        page.screenshot(path=str(output / "datamap-view-1200.png"), full_page=True)

        integration.select_option("partial")
        page.wait_for_timeout(150)
        open_button = page.locator(".lex-data-map-open").first
        expect(open_button).to_be_visible()
        open_button.click()
        page.wait_for_function("state.tab==='misc' && state.data && !state.busy")
        assert page.evaluate("state.asset") in set(fixtures()["data"])

        # The map must lead to the first-class screen that owns each target,
        # not funnel everything through Misc or lose virtual resources.
        for target, expected in (
            (EQUIPMENT, "equipment"),
            (ITEM, "item"),
            (LOOT, "loot"),
            (PLAYER, "characters"),
            (ABILITY, "abilities"),
            (ENEMY, "enemies"),
            (TWEAK, "tweaks"),
            (TEXT, "text"),
        ):
            page.evaluate("target => { void openMapRow({target}); }", target)
            page.wait_for_function(
                "expected => state.tab===expected && !state.busy && !state.textBusy && !(state.tweaksPending>0)",
                arg=expected,
            )
            assert page.evaluate("state.tab") == expected, (target, expected)
        page.screenshot(path=str(output / "datamap-routing-1200.png"), full_page=True)

        page.locator("#plugin-info").click()
        page.wait_for_function("state.tab==='info'")
        expect(page.get_by_role("heading", name="Information", exact=True)).to_be_visible()
        page.wait_for_function("""() => {
          const mod=document.querySelector(".lex-plugin-mod-loading");
          const credits=document.querySelector(".lex-plugin-credits");
          return mod?.querySelectorAll("li").length>=3
            && credits?.querySelectorAll(".lex-credit-entry").length>0
            && !mod.querySelector('[role="alert"]')
            && !credits.querySelector('[role="alert"]');
        }""")
        assert "packaged mod-loading file is missing" not in page.locator("#main").inner_text().lower()
        assert "packaged credits file is missing" not in page.locator("#main").inner_text().lower()
        assert page.locator(".lex-information-panel .lex-detail-panel-body > .lex-plugin-mod-loading").count() == 1
        assert page.locator(".lex-information-panel .lex-detail-panel-body > .lex-plugin-credits").count() == 1
        shared = page.locator(".lex-information-panel .lex-detail-panel-body")
        shared.evaluate("node => { node.scrollTop = node.scrollHeight; }")
        page.wait_for_timeout(100)
        page.screenshot(path=str(output / "info-shared-sections-1200.png"), full_page=True)
        remove = page.get_by_role("button", name="Remove deployed PAK", exact=True)
        expect(remove).to_be_enabled()
        remove.click()
        page.wait_for_function("state.info.projectDeployment.state==='absent'")
        expect(page.get_by_role("button", name="Remove deployed PAK", exact=True)).to_be_disabled()
        assert "Removed Lexeditor's deployed PAK" in page.locator("#main").inner_text()
        page.screenshot(path=str(output / "info-remove-1200.png"), full_page=True)

        # Explicit state surfaces: loading, error and empty data.
        page.evaluate("""() => {state.tab="misc";state.busy=true;render();}""")
        assert "Loading DataObject" in page.locator("#main").inner_text()
        page.screenshot(path=str(output / "state-loading.png"), full_page=True)

        page.evaluate("""() => {
          state.busy=false;state.error="Synthetic fixture failure";
          state.data=null;state.dataBaseline=null;render();
        }""")
        assert "Resource unavailable" in page.locator("#main").inner_text()
        assert "Synthetic fixture failure" in page.locator("#main").inner_text()
        page.screenshot(path=str(output / "state-error.png"), full_page=True)

        page.evaluate("""asset => {
          const empty=JSON.parse(JSON.stringify(window.__fixture.data[asset]));
          empty.records=[];state.error="";state.data=empty;
          state.dataBaseline=JSON.parse(JSON.stringify(empty));state.asset=asset;render();
        }""", MISC)
        assert "No record" in page.locator("#main").inner_text()
        page.screenshot(path=str(output / "state-empty.png"), full_page=True)

        page.evaluate("asset => loadAsset(asset)", MISC)
        page.wait_for_function("state.data && !state.busy")
        metrics = assert_layout(page, 1200, 800)
        assert not errors, errors
        results.append({"case": "interactions", "status": "passed", "layout": metrics})
    finally:
        context.close()
    return results


def responsive_checks(browser, output: Path, html: str) -> list[dict]:
    results = []
    for width, height, scale in (
        (900, 620, 1.0),
        (1200, 800, 1.0),
        (1600, 1000, 1.0),
        (1200, 800, 1.5),
    ):
        context, page, errors = new_page(
            browser, html, width, height, scale,
            diagnostic=output / (
                f"boot-failure-{width}x{height}"
                + ("-scale150.png" if scale == 1.5 else ".png")))
        try:
            page.wait_for_timeout(150)
            metrics = assert_layout(page, width, height)
            if scale > 1:
                table = page.locator(".ff7r-table")
                expect(table).to_be_visible()
                assert table.locator(".lex-column-list-row").count() > 0
            page.screenshot(
                path=str(output / (
                    f"responsive-{width}x{height}"
                    + ("-scale150" if scale == 1.5 else "") + ".png")),
                full_page=True,
            )
            page.locator("#plugin-data-map").click()
            page.wait_for_selector(".lex-data-map-table")
            page.wait_for_timeout(150)
            map_metrics = assert_layout(page, width, height)
            if scale > 1:
                map_table = page.locator(".lex-data-map-table")
                expect(map_table).to_be_visible()
                assert map_table.locator(".lex-column-list-row").count() > 0
            page.screenshot(
                path=str(output / (
                    f"datamap-{width}x{height}"
                    + ("-scale150" if scale == 1.5 else "") + ".png")),
                full_page=True,
            )
            assert not errors, errors
            results.append({
                "case": "responsive", "physical": [width, height], "deviceScaleFactor": scale,
                "cssViewport": [round(width / scale), round(height / scale)],
                "data": metrics, "datamap": map_metrics, "status": "passed",
            })
        finally:
            context.close()
    return results


def run(output: Path, executable: str | None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    html = document()
    with sync_playwright() as playwright:
        options = {"headless": True, "args": ["--no-sandbox"]}
        if executable:
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        try:
            results = exercise_editor(browser, output, html)
            results += responsive_checks(browser, output, html)
        finally:
            browser.close()
    (output / "results.json").write_text(json.dumps({
        "fixtureOnly": True,
        "retailGameAcceptance": False,
        "results": results,
    }, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, default=ROOT / "out" / "ff7r-browser")
    parser.add_argument("--chromium", default=None)
    args = parser.parse_args()
    run(args.screenshots, args.chromium)
