from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


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
    '''            assert "Fixture Module" in page.locator("#main").inner_text()\n\n            page.evaluate('navigate("dependencies")')\n            legacy_row = page.locator("button.bl-item").filter(has_text="LegacyBrowserDep")\n            assert legacy_row.count() == 1\n            legacy_row.click()\n            detail_text = page.locator(".bl-detail").inner_text()\n            assert "Legacy shape" in detail_text\n            assert "LoadAfterModules" in detail_text\n            assert "historical LoadAfterModules relation is required" in detail_text\n            assert page.get_by_role("button", name="+ Legacy", exact=True).count() == 0\n            legacy_id = page.locator('.bl-detail .bl-grid input[type="text"]').first\n            legacy_id.fill("LegacyBrowserRenamed")\n            assert page.evaluate("moduleDirty()") is True\n            assert page.evaluate("state.module.legacyDependencies[0].id") == "LegacyBrowserRenamed"\n            legacy_id.fill("LegacyBrowserDep")\n            assert page.evaluate("moduleDirty()") is False\n\n            page.evaluate('navigate("moduledata")')\n''',
    "rendered legacy dependency editor coverage",
)
