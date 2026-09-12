"""Fixture-only browser regression for raw PC segment-memory event editing."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chrono_trigger_browser_check import DASHBOARD, SCENES, _editor_html

ARTIFACTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "chrono-trigger-segment-memory-browser"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ORIGIN = "http://chrono-segment-memory-fixture.local"

EVENT_LIST = {
    "kind": "field-events", "matchCount": 1, "offset": 0, "limit": 100,
    "rows": [{
        "id": 24, "name": "Atel 0024", "path": "Game/field/atel/Atel_0024.dat",
        "source": "archive", "sha256": "j" * 64, "objectCount": 1, "decodedCommandCount": 2,
    }],
}
EVENT_DETAIL = {
    "kind": "field-event", "id": 24, "name": "Atel 0024", "path": "Game/field/atel/Atel_0024.dat",
    "source": "archive", "sha256": "j" * 64, "objectCount": 1, "uniqueFunctionBounds": 1,
    "decodedCommandCount": 2, "completeFunctionBounds": 1, "problemFunctionBounds": 0,
    "objects": [{
        "id": 0, "start": 32, "end": 38,
        "functions": [{
            "id": 0, "name": "Startup", "start": 32, "end": 38, "length": 6, "complete": True,
            "commands": [
                {
                    "offset": 32, "opcode": 0x4B, "name": "Value to Any 16", "size": 5,
                    "argumentsHex": "34 12 78 56", "argumentBytes": 4,
                    "semantic": {
                        "summary": "PC Store16 value 22136 → raw segment 0x1234",
                        "widthBytes": 2, "pcSegmentRaw": True, "fullAddressKnown": False,
                        "segment": 0x1234, "value": 0x5678,
                    },
                    "editor": {
                        "editor": "fixed-fields", "opcode": 0x4B, "opcodeHex": "0x4B", "fixedWidth": True,
                        "fields": [
                            {"key": "segment", "label": "PC segment destination (raw)", "kind": "integer", "min": 0, "max": 0xFFFF},
                            {"key": "value", "label": "16-bit value", "kind": "integer", "min": 0, "max": 0xFFFF},
                        ],
                        "values": {"segment": 0x1234, "value": 0x5678},
                    },
                },
                {"offset": 37, "opcode": 0x00, "name": "Return", "size": 1, "argumentsHex": ""},
            ],
        }],
    }],
}


def main() -> None:
    errors: list[str] = []
    saved_requests: list[dict] = []
    event_detail = copy.deepcopy(EVENT_DETAIL)
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
                path = urlparse(route.request.url).path
                if path in {"/", "/blank"}:
                    route.fulfill(status=200, content_type="text/html", body=html)
                elif path == "/api/dashboard":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(DASHBOARD))
                elif path == "/api/scenes":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(SCENES))
                elif path == "/api/events":
                    body = event_detail if "id=" in route.request.url else EVENT_LIST
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
                elif path == "/api/save/event-fields":
                    request = json.loads(route.request.post_data or "{}")
                    saved_requests.append(request)
                    values = request.get("values", {})
                    segment = int(values["segment"])
                    value = int(values["value"])
                    command = event_detail["objects"][0]["functions"][0]["commands"][0]
                    command["argumentsHex"] = (segment.to_bytes(2, "little") + value.to_bytes(2, "little")).hex(" ").upper()
                    command["semantic"] = {
                        "summary": f"PC Store16 value {value} → raw segment 0x{segment:04X}",
                        "widthBytes": 2, "pcSegmentRaw": True, "fullAddressKnown": False,
                        "segment": segment, "value": value,
                    }
                    command["editor"]["values"] = {"segment": segment, "value": value}
                    event_detail["source"] = "project"
                    event_detail["sha256"] = "k" * 64
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(event_detail))
                else:
                    route.fulfill(status=404, content_type="application/json", body=json.dumps({"error": path}))

            page.route(f"{ORIGIN}/**", handle)
            page.goto(ORIGIN + "/", wait_until="domcontentloaded")
            page.wait_for_function('state.scenes.data?.rows?.length === 1')
            page.evaluate('navigate("events")')
            page.wait_for_function('state.events.detail?.id === 24')

            editor = page.locator(".ct-command-editor")
            assert editor.count() == 1
            text = editor.inner_text()
            assert "PC segment destination (raw)" in text
            assert "16-bit value" in text
            assert "0x7F" not in text
            inputs = editor.locator('input[type="number"]')
            assert inputs.count() == 2
            assert inputs.nth(0).input_value() == str(0x1234)
            assert inputs.nth(1).input_value() == str(0x5678)
            inputs.nth(0).fill(str(0xBEEF))
            inputs.nth(1).fill(str(0xCAFE))
            editor.get_by_role("button", name="Apply command", exact=True).click()

            page.wait_for_function('state.events.detail?.objects?.[0]?.functions?.[0]?.commands?.[0]?.editor?.values?.segment === 48879')
            page.wait_for_function('document.querySelector(".ct-command-summary")?.textContent === "PC Store16 value 51966 → raw segment 0xBEEF"')
            page.wait_for_function('document.querySelector(".ct-hex")?.textContent === "EF BE FE CA"')
            request = saved_requests[-1]
            assert request["eventId"] == 24
            assert request["objectId"] == 0
            assert request["functionId"] == 0
            assert request["commandIndex"] == 0
            assert request["sha256"] == "j" * 64
            assert request["values"] == {"segment": 0xBEEF, "value": 0xCAFE}
            assert page.locator(".ct-warning").count() == 0
            page.screenshot(path=str(ARTIFACTS / "segment-memory-editor.png"), full_page=True)
            page.close()
        finally:
            browser.close()

    result = {"fixtureOnly": True, "segmentMemoryEditor": True, "fullAddressKnown": False, "errors": errors}
    (ARTIFACTS / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert not errors, errors
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
