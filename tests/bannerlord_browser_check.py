"""Rendered Bannerlord plugin smoke checks using only in-memory fixtures."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "bannerlord-browser"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

MODULE = {
    "path": "C:/fixture/SubModule.xml", "name": "Fixture Module", "id": "FixtureMod",
    "version": "v1.0.0", "defaultModule": False, "singleplayer": True, "multiplayer": False,
    "sourceHash": "module-hash",
    "dependencies": [], "communityDependencies": [],
    "legacyDependencies": [{
        "index": 0, "id": "LegacyBrowserDep", "order": "LoadAfterThis",
        "optional": False, "incompatible": False, "version": "",
        "origin": "LoadAfterModules",
        "attributes": {"Id": "LegacyBrowserDep", "Future": "keep-browser"},
    }],
    "modulesToLoadAfterThis": [], "incompatibleModules": [],
    "submodules": [{"index": 0, "name": "Fixture", "dllName": "Fixture.dll", "classType": "Fixture.SubModule", "tags": []}],
    "xmls": [{"index": 0, "id": "Items", "path": "items", "includedGameTypes": []}],
}
PROJECT = {"root": "C:/fixture", "projectFile": {
    "path": "C:/fixture/Fixture.csproj", "name": "Fixture.csproj", "sdk": "Microsoft.NET.Sdk",
    "properties": {"TargetFramework": "net472", "AssemblyName": "Fixture", "Nullable": "disable"},
    "propertyRows": [], "editableProperties": ["TargetFramework", "AssemblyName", "Nullable"],
    "references": [], "packages": [], "items": [],
    "targets": [{"name": "CopyModuleFiles", "afterTargets": "Build", "beforeTargets": "", "condition": "", "tasks": ["Copy"]}],
}}
EMPTY_SKILLS = {"available": False, "attributes": [], "skills": []}
EMPTY_EFFECTS = {"available": False, "effects": []}
EMPTY_PERKS = {"available": False, "perks": []}
EMPTY_XP = {"available": False, "sources": []}
EMPTY_SETTINGS = {"available": False, "settings": []}
RUNTIME = {"available": False, "effects": [], "xpSources": []}

DEPLOYMENT = {
    "projectName": "Fixture Module", "moduleId": "FixtureMod", "runnable": True, "deployed": True,
    "inSync": False, "descriptorInSync": True, "projectVersion": "v1.0.0", "deployedVersion": "v1.0.0",
    "gameRoot": "C:/game", "deployedRoot": "C:/game/Modules/FixtureMod",
    "issues": ["1 deployed ModuleData assets file(s) differ from the project"], "dependencies": [],
    "binaries": [{"name": "Fixture.dll", "classType": "Fixture.SubModule", "exists": True, "size": 1234}],
    "assets": {
        "gui": {"source": 1, "deployed": 1, "missing": [], "different": [], "inSync": True},
        "moduleData": {"source": 1, "deployed": 1, "missing": [], "different": ["items.xml"], "inSync": False},
        "sourceGuiXml": 1, "deployedGuiXml": 1, "missingGuiXml": [], "differentGuiXml": [],
    },
    "runtimeOverrides": {},
}

DATA_MAP = {"rows": [
    {"id": "module", "filename": "SubModule.xml", "area": "Module", "controls": "Module metadata", "coverage": "structured", "status": "integrated", "target": "module", "targets": ["module"], "openable": True, "sourceOpenable": True, "sourceAvailable": True},
    {"id": "gauntlet", "filename": "GUI/Prefabs/Test.xml", "area": "UI", "controls": "Gauntlet widget hierarchy", "coverage": "structured", "status": "integrated", "target": "gauntlet", "targets": ["gauntlet"], "openable": True, "sourceOpenable": True, "sourceAvailable": True, "editorPath": "GUI/Prefabs/Test.xml"},
    {"id": "moduledata", "filename": "ModuleData/items.xml", "area": "Module data", "controls": "Bannerlord object records", "coverage": "structured", "status": "integrated", "target": "moduledata", "targets": ["moduledata"], "openable": True, "sourceOpenable": True, "sourceAvailable": True, "editorPath": "ModuleData/items.xml"},
]}

MODULE_DATA_BAD = {
    "path": "C:/fixture/ModuleData/items.xml", "relativePath": "ModuleData/items.xml", "rootTag": "Items", "recordCount": 1,
    "records": [{"path": "Items[0]/Item[0]", "tag": "Item", "line": 2, "id": "", "name": "", "schemaIssueCount": 1}],
    "elements": [
        {"index": 0, "path": "Items[0]", "tag": "Items", "depth": 0, "line": 1, "hint": "", "attributes": [], "missingRequired": [], "schemaIssues": []},
        {"index": 1, "path": "Items[0]/Item[0]", "tag": "Item", "depth": 1, "line": 2, "hint": "", "attributes": [
            {"name": "enabled", "value": "1", "kind": "bool", "choices": [], "schemaType": "boolean"},
            {"name": "Type", "value": "Weapon", "kind": "enum", "choices": ["Weapon", "Armor"], "schemaType": "string"},
            {"name": "tier", "value": "2", "kind": "number", "choices": [], "schemaType": "int", "integer": True, "min": 0, "max": 6},
        ], "missingRequired": [{"name": "id", "required": True, "schemaType": "string", "choices": [], "kind": "text"}],
         "schemaIssues": ["Missing required attribute: id"]},
    ],
    "schema": {"id": "Items", "path": "C:/game/XmlSchemas/Items.xsd", "matchedByRegistration": True}, "schemaIssueCount": 1,
}
MODULE_DATA_FIXED = {
    **MODULE_DATA_BAD, "recordCount": 1,
    "records": [{"path": "Items[0]/Item[0]", "tag": "Item", "line": 2, "id": "browser_fixture", "name": "", "schemaIssueCount": 0}],
    "elements": [MODULE_DATA_BAD["elements"][0], {
        "index": 1, "path": "Items[0]/Item[0]", "tag": "Item", "depth": 1, "line": 2, "hint": "browser_fixture",
        "attributes": [
            {"name": "enabled", "value": "1", "kind": "bool", "choices": [], "schemaType": "boolean"},
            {"name": "Type", "value": "Weapon", "kind": "enum", "choices": ["Weapon", "Armor"], "schemaType": "string"},
            {"name": "tier", "value": "2", "kind": "number", "choices": [], "schemaType": "int", "integer": True, "min": 0, "max": 6},
            {"name": "id", "value": "browser_fixture", "kind": "text", "choices": [], "required": True, "schemaType": "string"},
        ], "missingRequired": [], "schemaIssues": [],
    }],
    "schemaIssueCount": 0, "saved": 1, "backup": "C:/fixture/ModuleData/items.xml.lexeditor.bak",
}
GAUNTLET = {
    "path": "C:/fixture/GUI/Prefabs/Test.xml", "relativePath": "GUI/Prefabs/Test.xml", "elementCount": 3,
    "elements": [
        {"index": 0, "path": "Prefab[0]", "tag": "Prefab", "depth": 0, "line": 1, "hint": "", "attributes": []},
        {"index": 1, "path": "Prefab[0]/Window[0]", "tag": "Window", "depth": 1, "line": 2, "hint": "", "attributes": []},
        {"index": 2, "path": "Prefab[0]/Window[0]/Widget[0]", "tag": "Widget", "depth": 2, "line": 3, "hint": "@IsEnabled", "attributes": [
            {"name": "IsEnabled", "value": "false", "kind": "bool", "choices": []},
            {"name": "WidthSizePolicy", "value": "StretchToParent", "kind": "enum", "choices": ["Fixed", "StretchToParent", "CoverChildren"]},
            {"name": "SuggestedWidth", "value": "100", "kind": "number", "choices": []},
        ]},
    ],
}


def inline_editor() -> str:
    html = (ROOT / "games/bannerlord/editor.html").read_text(encoding="utf-8")
    html = html.replace("<head>", '<head><base href="http://127.0.0.1:9/">', 1)
    html = html.replace('<link rel="stylesheet" href="/shared/framework.css">',
                        "<style>" + (ROOT / "ui/framework.css").read_text(encoding="utf-8") + "</style>")
    fixtures = {
        "/api/module": MODULE, "/api/project": PROJECT, "/api/skills": EMPTY_SKILLS,
        "/api/effects": EMPTY_EFFECTS, "/api/perks": EMPTY_PERKS, "/api/xp-sources": EMPTY_XP,
        "/api/settings-defaults": EMPTY_SETTINGS, "/api/runtime-overrides": RUNTIME,
        "/api/deployment": DEPLOYMENT, "/api/datamap": DATA_MAP,
        "/api/module-data-files": {"files": ["ModuleData/items.xml"]},
        "/api/gauntlet-files": {"files": ["GUI/Prefabs/Test.xml"]},
    }
    stub = f'''window.__bannerlordRequests=[];
const __fixtures={json.dumps(fixtures)};
const __moduleDataBad={json.dumps(MODULE_DATA_BAD)};
const __moduleDataFixed={json.dumps(MODULE_DATA_FIXED)};
const __gauntlet={json.dumps(GAUNTLET)};
window.fetch=async function(input,options={{}}){{
  const url=new URL(String(input),document.baseURI);const path=url.pathname;
  const method=String(options.method||"GET").toUpperCase();
  if(method==="POST"){{
    const body=options.body?JSON.parse(options.body):{{}};window.__bannerlordRequests.push({{path,body}});
    if(path==="/api/module/save"){{
      const current=__fixtures["/api/module"],metadata=body.metadata||{{}};
      const module={{...current,...metadata,sourceHash:"module-hash-after",
        dependencies:body.dependencies??current.dependencies,
        communityDependencies:body.communityDependencies??current.communityDependencies,
        legacyDependencies:body.legacyDependencies??current.legacyDependencies,
        modulesToLoadAfterThis:body.modulesToLoadAfterThis??current.modulesToLoadAfterThis,
        incompatibleModules:body.incompatibleModules??current.incompatibleModules,
        submodules:body.submodules??current.submodules,xmls:body.xmls??current.xmls}};
      return new Response(JSON.stringify({{saved:1,module}}),{{status:200}});
    }}
    if(path==="/api/source/save"){{
      return new Response(JSON.stringify({{
        path:body.path,absolutePath:`C:/fixture/${{body.path}}`,encoding:"utf-8",text:body.text,size:body.text.length,saved:1,backup:`C:/fixture/${{body.path}}.lexeditor.bak`
      }}),{{status:200}});
    }}
    if(path==="/api/module-data/save")return new Response(JSON.stringify(__moduleDataFixed),{{status:200}});
    if(path==="/api/gauntlet/save")return new Response(JSON.stringify(__gauntlet),{{status:200}});
    if(path==="/api/deploy-assets"){{
      const deployment={{...__fixtures["/api/deployment"],inSync:true,issues:[],assets:{{...__fixtures["/api/deployment"].assets,moduleData:{{source:1,deployed:1,missing:[],different:[],inSync:true}}}}}};
      return new Response(JSON.stringify({{assets:{{target:"C:/game/Modules/FixtureMod",copied:["ModuleData/items.xml"],unchanged:[],backups:[],deleted:[]}},deployment}}),{{status:200}});
    }}
    if(path==="/api/build"||path==="/api/build-deploy")return new Response(JSON.stringify(path.endsWith("deploy")?{{build:{{succeeded:true,output:"Build succeeded",returnCode:0}},assets:{{target:"C:/game/Modules/FixtureMod",copied:[],unchanged:[],backups:[]}},deployment:__fixtures["/api/deployment"]}}:{{succeeded:true,output:"Build succeeded",returnCode:0}}),{{status:200}});
    return new Response(JSON.stringify({{}}),{{status:200}});
  }}
  if(path==="/api/module-data")return new Response(JSON.stringify(__moduleDataBad),{{status:200}});
  if(path==="/api/gauntlet")return new Response(JSON.stringify(__gauntlet),{{status:200}});
  return new Response(JSON.stringify(__fixtures[path]||{{}}),{{status:200}});
}};'''
    html = html.replace('<script src="/shared/framework.js"></script>',
                        "<script>" + stub + "</script><script>" + (ROOT / "ui/framework.js").read_text(encoding="utf-8") + "</script>")
    for name in (
        "editor_alerts.js", "editor_core.js", "editor_balancing.js", "editor_build.js",
        "editor_settings.js", "editor_runtime.js", "editor_gauntlet.js", "editor_moduledata.js",
        "editor_moduledata_validation.js", "editor_boot.js",
    ):
        html = html.replace(f'<script src="/bannerlord/{name}"></script>',
                            "<script>" + (ROOT / "games/bannerlord" / name).read_text(encoding="utf-8") + "</script>")
    return html


def main() -> None:
    errors, results = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=shutil.which("chromium") or None,
                                             headless=True, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 820})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content(inline_editor(), wait_until="domcontentloaded")
            page.wait_for_function("state.module && state.project && state.datamap", timeout=8000)
            assert "Fixture Module" in page.locator("#main").inner_text()

            page.evaluate('navigate("dependencies")')
            legacy_row = page.locator("button.bl-item").filter(has_text="LegacyBrowserDep")
            assert legacy_row.count() == 1
            legacy_row.click()
            detail_text = page.locator(".bl-detail").inner_text()
            assert "Legacy shape" in detail_text
            assert "LoadAfterModules" in detail_text
            assert "historical LoadAfterModules relation is required" in detail_text
            assert page.get_by_role("button", name="+ Legacy", exact=True).count() == 0
            legacy_id = page.locator('.bl-detail .bl-grid input[type="text"]').first
            legacy_id.fill("LegacyBrowserRenamed")
            assert page.evaluate("moduleDirty()") is True
            assert page.evaluate("state.module.legacyDependencies[0].id") == "LegacyBrowserRenamed"
            page.evaluate("save()")
            page.wait_for_function("!moduleDirty()")
            request = page.evaluate("window.__bannerlordRequests.find(row=>row.path==='/api/module/save')")
            assert request["body"]["legacyDependencies"][0]["id"] == "LegacyBrowserRenamed"
            assert request["body"]["legacyDependenciesBaseline"][0]["id"] == "LegacyBrowserDep"
            assert request["body"]["legacyDependenciesBaseline"][0]["attributes"]["Future"] == "keep-browser"
            assert request["body"]["sourceHash"] == "module-hash"
            assert page.evaluate("state.savedModule.legacyDependencies[0].id") == "LegacyBrowserRenamed"
            assert page.evaluate("state.savedModule.sourceHash") == "module-hash-after"

            page.evaluate("""
                window.__bannerlordRequests=[];
                state.source={path:"src/Notes.cs",absolutePath:"C:/fixture/src/Notes.cs",encoding:"utf-8",text:"after"};
                state.savedSourceText="before";
            """)
            page.evaluate("save()")
            page.wait_for_function("!sourceDirty()")
            source_request = page.evaluate("window.__bannerlordRequests.find(row=>row.path==='/api/source/save')")
            assert source_request["body"]["text"] == "after"
            assert source_request["body"]["originalText"] == "before"

            page.evaluate('navigate("deployment")')
            deployment_text = page.locator("#main").inner_text()
            assert "MOD LOADER" in deployment_text
            loader_values = page.locator("#main .lex-detail-field input").evaluate_all(
                "nodes => nodes.map(node => node.value)"
            )
            assert any("Bannerlord's native module loader" in value for value in loader_values), loader_values

            page.evaluate('navigate("moduledata")')
            page.wait_for_function("state.moduleData && state.moduleData.schemaIssueCount===1")
            assert page.locator('.bl-detail input[type="checkbox"]').first.is_checked()
            assert page.get_by_role("button", name="Validate all", exact=True).is_enabled()
            page.get_by_role("button", name="Validate all", exact=True).click()
            page.wait_for_function("state.moduleDataValidation && !state.moduleDataValidating && state.moduleDataValidation.scanned===1")
            assert page.evaluate("state.moduleDataValidation.issues") == 1
            assert "1 schema issue" in page.locator("#main").inner_text()

            missing_panel = page.locator(".bl-list-block").filter(has_text="Missing required attributes")
            missing_panel.locator('input[type="checkbox"]').first.check()
            missing_panel.locator('input[type="text"]').first.fill("browser_fixture")
            assert page.evaluate("moduleDataDirty()") is True
            page.evaluate("save()")
            page.wait_for_function("state.moduleData && state.moduleData.schemaIssueCount===0")
            request = page.evaluate("window.__bannerlordRequests.find(row=>row.path==='/api/module-data/save')")
            assert request["body"]["edits"][0]["addRequired"] is True
            assert request["body"]["edits"][0]["attribute"] == "id"

            page.evaluate('navigate("gauntlet")')
            page.wait_for_function("state.gauntlet && state.gauntlet.elementCount===3")
            page.locator("button.bl-item").filter(has_text="Widget").click()
            page.locator('.bl-detail input[type="checkbox"]').check()
            page.evaluate("save()")
            page.wait_for_function("!gauntletDirty()")
            gauntlet_request = page.evaluate("window.__bannerlordRequests.find(row=>row.path==='/api/gauntlet/save')")
            assert gauntlet_request["body"]["edits"][0]["attribute"] == "IsEnabled"

            page.evaluate('navigate("build")')
            for label in ("dotnet build", "Build + deploy", "Sync assets"):
                assert page.get_by_role("button", name=label, exact=True).is_enabled()
            page.get_by_role("button", name="Sync assets", exact=True).click()
            page.wait_for_function("state.deployResult && state.deployResult.copied.length===1")

            page.evaluate('navigate("deployment")')
            deployment_text = page.locator("#main").inner_text()
            assert "GUI assets" in deployment_text
            assert "ModuleData assets" in deployment_text
            assert "Project/deployed sync" in deployment_text

            page.evaluate('navigate("datamap")')
            page.wait_for_selector(".lex-data-map-table")
            assert page.locator(".lex-paged-list-detail").count() == 1
            filenames = page.evaluate("state.datamap.rows.map(row=>row.filename)")
            assert "ModuleData/items.xml" in filenames
            assert "GUI/Prefabs/Test.xml" in filenames

            page.screenshot(path=str(ARTIFACTS / "bannerlord-editor.png"), full_page=True)

            page.evaluate("""
                window.__bannerlordRequests=[];
                state.source={path:"SubModule.xml",absolutePath:"C:/fixture/SubModule.xml",encoding:"utf-8",text:"raw changed"};
                state.savedSourceText="raw before";
                state.module.name="Structured changed";
            """)
            page.evaluate("save()")
            page.wait_for_timeout(100)
            conflicting_requests = page.evaluate("window.__bannerlordRequests.filter(row=>row.path==='/api/module/save'||row.path==='/api/source/save')")
            assert conflicting_requests == [], conflicting_requests

            results.append({"viewport": [1280, 820], "status": "passed"})
            page.close()
        finally:
            browser.close()
    (ARTIFACTS / "results.json").write_text(
        json.dumps({"fixtureOnly": True, "results": results, "errors": errors}, indent=2), encoding="utf-8")
    assert not errors, errors
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
