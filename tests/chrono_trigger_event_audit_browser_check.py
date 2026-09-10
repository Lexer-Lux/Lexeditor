"""Fixture-only browser regression for the on-demand Chrono event audit UI."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chrono_trigger_browser_check import DASHBOARD, EVENT_DETAIL, EVENT_LIST, SCENES, _editor_html

ARTIFACTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "chrono-trigger-event-audit-browser"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ORIGIN = "http://chrono-event-audit-fixture.local"

AUDIT_MINE = {
    "kind": "chrono-trigger-event-audit-summary",
    "events": 1,
    "functions": 8,
    "completeFunctions": 6,
    "problemFunctions": 2,
    "decodedCommands": 14,
    "argumentCommands": 10,
    "zeroArgumentCommands": 4,
    "writableCommands": 5,
    "readOnlyCommands": 5,
    "writablePercent": 50.0,
    "hotspots": [
        {
            "opcode": 0xF1, "opcodeHex": "0xF1", "readOnlyCount": 1,
            "decodedCount": 1, "argumentCount": 1, "stopCount": 2,
            "dynamicOrUnresolvedBoundary": True,
        },
        {
            "opcode": 0x8E, "opcodeHex": "0x8E", "readOnlyCount": 4,
            "decodedCount": 4, "argumentCount": 4, "stopCount": 0,
            "dynamicOrUnresolvedBoundary": False,
        },
    ],
    "stopReasons": [{"reason": "PC command boundary is unresolved", "count": 2}],
    "scanSource": "mine",
    "selectedEventIds": [20, 21],
    "auditedEventIds": [20],
    "scanErrorCount": 1,
    "scanErrors": [{
        "eventId": 21, "path": "Game/field/atel/Atel_0021.dat",
        "error": "Field event object pointer table is truncated",
    }],
}
AUDIT_VANILLA = {
    "kind": "chrono-trigger-event-audit-summary",
    "events": 2,
    "functions": 10,
    "completeFunctions": 10,
    "problemFunctions": 0,
    "decodedCommands": 18,
    "argumentCommands": 12,
    "zeroArgumentCommands": 6,
    "writableCommands": 12,
    "readOnlyCommands": 0,
    "writablePercent": 100.0,
    "hotspots": [],
    "stopReasons": [],
    "scanSource": "vanilla",
    "selectedEventIds": [20, 21],
    "auditedEventIds": [20, 21],
    "scanErrorCount": 0,
    "scanErrors": [],
}


def main() -> None:
    errors: list[str] = []
    audit_queries: list[dict[str, list[str]]] = []
    html = _editor_html()
    with sync_playwright() as playwright:
        import shutil
        browser = playwright.chromium.launch(
            executable_path=shutil.which("chromium") or None,
            headless=True,
            args=["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
        )
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 800})
            page.on("pageerror", lambda error: errors.append(str(error)))

            def handle(route):
                parsed = urlparse(route.request.url)
                path = parsed.path
                if path in {"/", "/blank"}:
                    route.fulfill(status=200, content_type="text/html", body=html)
                elif path == "/api/dashboard":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(DASHBOARD))
                elif path == "/api/scenes":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(SCENES))
                elif path == "/api/events":
                    body = EVENT_DETAIL if "id=" in route.request.url else EVENT_LIST
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
                elif path == "/api/event-audit":
                    query = parse_qs(parsed.query)
                    audit_queries.append(query)
                    payload = AUDIT_VANILLA if query.get("source") == ["vanilla"] else AUDIT_MINE
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
                else:
                    route.fulfill(status=404, content_type="application/json", body=json.dumps({"error": path}))

            page.route(f"{ORIGIN}/**", handle)
            page.goto(ORIGIN + "/", wait_until="domcontentloaded")
            page.wait_for_function('state.scenes.data?.rows?.length === 1')
            page.evaluate('navigate("events")')
            page.wait_for_function('state.events.detail?.id === 20')

            panel = page.locator(".ct-event-audit")
            assert panel.count() == 1
            initial = panel.inner_text()
            assert "Real-install event coverage" in initial
            assert "Run coverage audit" in initial
            assert "runs only on request" in initial
            assert "Aliased function bounds" in initial

            panel.get_by_role("button", name="Run coverage audit", exact=True).click()
            page.wait_for_function('state.events.audit?.scanSource === "mine"')
            mine_text = panel.inner_text()
            assert "1/2 events audited" in mine_text
            assert "10 argument commands" in mine_text
            assert "50.00% named-editor coverage" in mine_text
            assert "2 fail-closed functions" in mine_text
            assert "1 scan error" in mine_text
            assert "0xF1" in mine_text
            assert "2 parser stops" in mine_text
            assert "dynamic/unresolved" in mine_text
            assert "0x8E" in mine_text
            assert "4 argument commands read-only" in mine_text
            assert audit_queries[-1] == {"source": ["mine"]}

            error_details = panel.locator("details")
            assert error_details.count() == 1
            error_details.locator("summary").click()
            assert "0021" in error_details.inner_text()
            assert "pointer table is truncated" in error_details.inner_text()
            page.screenshot(path=str(ARTIFACTS / "event-audit-mine.png"), full_page=True)

            page.evaluate('selectSource("vanilla")')
            page.wait_for_function('state.source === "vanilla" && state.events.detail?.id === 20')
            stale_text = panel.inner_text()
            assert "Run coverage audit" in stale_text
            assert "0xF1" not in stale_text
            assert "50.00%" not in stale_text
            assert "Read-only Vanilla scan" in stale_text

            panel.get_by_role("button", name="Run coverage audit", exact=True).click()
            page.wait_for_function('state.events.audit?.scanSource === "vanilla"')
            vanilla_text = panel.inner_text()
            assert "2/2 events audited" in vanilla_text
            assert "12 argument commands" in vanilla_text
            assert "100.00% named-editor coverage" in vanilla_text
            assert "0 fail-closed functions" in vanilla_text
            assert "No argument-bearing read-only or parser-stop hotspots found." in vanilla_text
            assert audit_queries[-1] == {"source": ["vanilla"]}
            page.screenshot(path=str(ARTIFACTS / "event-audit-vanilla.png"), full_page=True)
            page.close()
        finally:
            browser.close()

    result = {
        "fixtureOnly": True,
        "eventAuditUi": True,
        "mineAndVanilla": True,
        "auditRequests": len(audit_queries),
        "errors": errors,
    }
    (ARTIFACTS / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert not errors, errors
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
