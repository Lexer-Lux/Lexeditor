from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


editor = Path("games/bannerlord/editor.html")
replace_once(
    editor,
    '''  <script src="/shared/framework.js"></script>\n''',
    '''  <script src="/shared/framework.js"></script>\n  <script>\n    function bannerlordModLoaderSection(){\n      return LexeditorUI.modLoaderSection({\n        loader:"Bannerlord's native module loader. Lexeditor deploys the selected project as one module and launches the game with an explicit /singleplayer _MODULES_*...*_MODULES_ loadout.",\n        output:"Build + deploy writes this project's module-owned files under Bannerlord/Modules/<SubModule ID>; binaries remain MSBuild output and XML/GUI/ModuleData assets are synchronized by Lexeditor.",\n        order:"Lexeditor resolves the selected module's required dependency closure and declared load-order relations. Optional dependencies are not auto-enabled merely because they are installed.",\n        safety:"Deployment is additive, backs up overwritten module-owned files, excludes runtime override JSON, and does not edit Bannerlord's base-game files. Custom MSBuild targets still run with your user permissions.",\n        removal:"Stop launching the module and remove its deployed Modules/<SubModule ID> folder to uninstall it; the separate source project remains untouched."\n      });\n    }\n  </script>\n''',
    "shared Bannerlord mod-loader helper",
)

balancing = Path("games/bannerlord/editor_balancing.js")
replace_once(
    balancing,
    '''      el("div",{class:"bl-list-block"},el("h3",{},"Issues"),\n        d.issues?.length?el("ul",{},...d.issues.map(value=>el("li",{},value))):el("div",{class:"bl-note"},"No deployment problems detected by the static checks."))\n    );\n''',
    '''      el("div",{class:"bl-list-block"},el("h3",{},"Issues"),\n        d.issues?.length?el("ul",{},...d.issues.map(value=>el("li",{},value))):el("div",{class:"bl-note"},"No deployment problems detected by the static checks.")),\n      bannerlordModLoaderSection()\n    );\n''',
    "render shared Bannerlord mod-loader section",
)

boot = Path("games/bannerlord/editor_boot.js")
replace_once(
    boot,
    '''    help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the Bannerlord Data Map",\n    dirtyCount,readonly:()=>false,save\n''',
    '''    help:()=>navigate("datamap"),helpActive:()=>state.tab==="datamap",helpTitle:"Open the Bannerlord Data Map",\n    info:()=>navigate("deployment"),infoActive:()=>state.tab==="deployment",infoTitle:"Open Bannerlord deployment information",\n    dirtyCount,readonly:()=>false,save\n''',
    "Bannerlord shared info action",
)

ui_test = Path("tests/test_bannerlord_ui_contract.py")
replace_once(
    ui_test,
    '''    def test_build_ui_exposes_msbuild_execution_trust_boundary(self) -> None:\n''',
    '''    def test_shared_mod_loader_section_is_rendered_from_deployment_information(self) -> None:\n        html = (BANNERLORD_ROOT / "editor.html").read_text(encoding="utf-8")\n        balancing = (BANNERLORD_ROOT / "editor_balancing.js").read_text(encoding="utf-8")\n        boot = (BANNERLORD_ROOT / "editor_boot.js").read_text(encoding="utf-8")\n        self.assertIn("LexeditorUI.modLoaderSection(", html)\n        self.assertIn("bannerlordModLoaderSection()", balancing)\n        self.assertIn('info:()=>navigate("deployment")', boot)\n\n    def test_build_ui_exposes_msbuild_execution_trust_boundary(self) -> None:\n''',
    "Bannerlord shared mod-loader contract regression",
)

browser = Path("tests/bannerlord_browser_check.py")
replace_once(
    browser,
    '''    "dependencies": [], "incompatibleModules": [],\n''',
    '''    "dependencies": [], "communityDependencies": [],\n    "legacyDependencies": [{\n        "index": 0, "id": "LegacyBrowserDep", "order": "LoadAfterThis",\n        "optional": False, "incompatible": False, "version": "",\n        "origin": "LoadAfterModules",\n        "attributes": {"Id": "LegacyBrowserDep", "Future": "keep-browser"},\n    }],\n    "modulesToLoadAfterThis": [], "incompatibleModules": [],\n''',
    "legacy dependency browser fixture",
)
replace_once(
    browser,
    '''            assert "Fixture Module" in page.locator("#main").inner_text()\n\n            page.evaluate('navigate("moduledata")')\n''',
    '''            assert "Fixture Module" in page.locator("#main").inner_text()\n\n            page.evaluate('navigate("dependencies")')\n            legacy_row = page.locator("button.bl-item").filter(has_text="LegacyBrowserDep")\n            assert legacy_row.count() == 1\n            legacy_row.click()\n            detail_text = page.locator(".bl-detail").inner_text()\n            assert "Legacy shape" in detail_text\n            assert "LoadAfterModules" in detail_text\n            assert "historical LoadAfterModules relation is required" in detail_text\n            assert page.get_by_role("button", name="+ Legacy", exact=True).count() == 0\n            legacy_id = page.locator('.bl-detail .bl-grid input[type="text"]').first\n            legacy_id.fill("LegacyBrowserRenamed")\n            assert page.evaluate("moduleDirty()") is True\n            assert page.evaluate("state.module.legacyDependencies[0].id") == "LegacyBrowserRenamed"\n            legacy_id.fill("LegacyBrowserDep")\n            assert page.evaluate("moduleDirty()") is False\n\n            page.evaluate('navigate("deployment")')\n            deployment_text = page.locator("#main").inner_text()\n            assert "MOD LOADER" in deployment_text\n            assert "Bannerlord's native module loader" in deployment_text\n\n            page.evaluate('navigate("moduledata")')\n''',
    "rendered legacy dependency and mod-loader coverage",
)
