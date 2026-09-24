"""Headless proof for Warband troop relationship navigation."""

from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugins.warband import paths  # noqa: E402
from plugins.warband.plugin import WarbandSession  # noqa: E402


TROOPS = [
    {
        "recordIndex": 0, "id": "recruit", "name": "Recruit", "plural": "Recruits",
        "faction": "fac_test", "level": 1, "line": 1, "status": "active",
        "fields": {
            "name": "Recruit", "plural": "Recruits", "faction": "fac_test",
            "attributes": "0", "flags": "0", "inventory": "[]",
        },
        "stats": {}, "flagValue": None, "items": [],
    },
    {
        "recordIndex": 1, "id": "veteran", "name": "Veteran", "plural": "Veterans",
        "faction": "fac_test", "level": 10, "line": 2, "status": "active",
        "fields": {
            "name": "Veteran", "plural": "Veterans", "faction": "fac_test",
            "attributes": "0", "flags": "0", "inventory": "[]",
        },
        "stats": {}, "flagValue": None, "items": [],
    },
]


def main() -> int:
    errors: list[str] = []
    with WarbandSession() as session, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(session.url, wait_until="domcontentloaded")
            page.wait_for_function("typeof state!=='undefined'&&!state.booting")
            page.evaluate(
                """troops => {
                    state.troops = {
                        rows: troops, items: [], factions: ["fac_test"],
                        types: {}, flags: {},
                    };
                    state.items = {rows: []};
                    state.upgrades = {rows: [{
                        fromId: "recruit", toId: "veteran",
                        from: "Recruit [recruit]", to: "Veteran [veteran]",
                        branch: "1/1", line: 1,
                    }]};
                    navigate("upgrades");
                }""",
                TROOPS,
            )
            veteran = page.locator('.lex-tree-graph-node[data-node="veteran"]')
            veteran.wait_for(state="visible")
            assert page.locator(".lex-tree-graph-stage svg path").count() == 1
            veteran.click()
            page.wait_for_function("state.selectedUpgrade==='veteran'")
            assert "Veteran" in page.locator(".warband-tree-detail").inner_text()

            page.evaluate(
                """() => {
                    const holder=document.createElement("div");
                    holder.id="verify-warband-link";
                    holder.append(troopLink("recruit","Recruit linked record"));
                    document.querySelector("#toolbar").append(holder);
                }"""
            )
            link = page.locator("#verify-warband-link .lex-hoverable")
            link.wait_for(state="visible")
            assert link.get_attribute("data-hover-target-type") == "warband-troop"
            assert link.get_attribute("data-hover-target-id") == "recruit"
            link.hover()
            assert "underline" in link.evaluate("node => getComputedStyle(node).textDecorationLine")
            link.click(modifiers=["Alt"])
            page.wait_for_function("state.tab==='troops'&&state.troops.rows.find(row=>troopRowKey(row)===state.selectedTroop)?.id==='recruit'")
            selected = page.locator(".lex-column-list-row.selected")
            selected.wait_for(state="visible")
            assert "recruit" in selected.inner_text().lower()
            assert not errors, errors

            output = DEV_CACHE / "rendered" / "github-45-warband-relationship.png"
            page.screenshot(path=str(output), full_page=True)
            print({
                "treeTarget": "veteran",
                "linkedTarget": "recruit",
                "destination": page.evaluate("() => ({tab:state.tab, selectedRecord:state.selectedTroop, selectedId:state.troops.rows.find(row=>troopRowKey(row)===state.selectedTroop)?.id})"),
                "screenshot": str(output),
            })
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
