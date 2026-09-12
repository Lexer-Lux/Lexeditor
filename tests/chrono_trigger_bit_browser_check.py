"""Fixture-only browser regression for Chrono Trigger script-memory bit editing."""
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

ARTIFACTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "chrono-trigger-bit-browser"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ORIGIN = "http://chrono-bit-fixture.local"

EVENT_LIST = {
    "kind": "field-events", "matchCount": 1, "offset": 0, "limit": 100,
    "rows": [{
        "id": 21, "name": "Atel 0021", "path": "Game/field/atel/Atel_0021.dat",
        "source": "archive", "sha256": "b" * 64, "objectCount": 1, "decodedCommandCount": 2,
    }],
}
EVENT_DETAIL = {
    "kind": "field-event", "id": 21, "name": "Atel 0021", "path": "Game/field/atel/Atel_0021.dat",
    "source": "archive", "sha256": "b" * 64, "objectCount": 1, "uniqueFunctionBounds": 1,
    "decodedCommandCount": 2, "completeFunctionBounds": 1, "problemFunctionBounds": 0,
    "objects": [{
        "id": 0, "start": 32, "end": 36,
        "functions": [{
            "id": 0, "name": "Startup", "start": 32, "end": 36, "length": 4, "complete": True,
            "commands": [
                {
                    "offset": 32, "opcode": 0x6B, "name": "Toggle Bits", "size": 3,
                    "argumentsHex": "55 10", "argumentBytes": 2,
                    "semantic": {
                        "summary": "Toggle bits 0x55 in 0x7F0220",
                        "memoryAddress": 0x7F0220, "bitMask": 0x55, "operation": "toggle-mask",
                    },
                    "editor": {
                        "editor": "fixed-fields", "opcode": 0x6B, "opcodeHex": "0x6B", "fixedWidth": True,
                        "fields": [
                            {"key": "memoryAddress", "label": "Script-memory address", "kind": "integer", "min": 0x7F0200, "max": 0x7F03FE},
                            {"key": "bitMask", "label": "Bit mask", "kind": "integer", "min": 0, "max": 0xFF},
                        ],
                        "values": {"memoryAddress": 0x7F0220, "bitMask": 0x55},
                    },
                },
                {"offset": 35, "opcode": 0x00, "name": "Return", "size": 1, "argumentsHex": ""},
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
                    address = int(values["memoryAddress"])
                    mask = int(values["bitMask"])
                    slot = (address - 0x7F0200) // 2
                    command = event_detail["objects"][0]["functions"][0]["commands"][0]
                    command["argumentsHex"] = f"{mask:02X} {slot:02X}"
                    command["semantic"] = {
                        "summary": f"Toggle bits 0x{mask:02X} in 0x{address:06X}",
                        "memoryAddress": address, "bitMask": mask, "operation": "toggle-mask",
                    }
                    command["editor"]["values"] = {"memoryAddress": address, "bitMask": mask}
                    event_detail["source"] = "project"
                    event_detail["sha256"] = "c" * 64
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(event_detail))
                else:
                    route.fulfill(status=404, content_type="application/json", body=json.dumps({"error": path}))

            page.route(f"{ORIGIN}/**", handle)
            page.goto(ORIGIN + "/", wait_until="domcontentloaded")
            page.wait_for_function('state.scenes.data?.rows?.length === 1')
            page.evaluate('navigate("events")')
            page.wait_for_function('state.events.detail?.id === 21')

            editor = page.locator(".ct-command-editor")
            assert editor.count() == 1
            assert "Script-memory address" in editor.inner_text()
            assert "Bit mask" in editor.inner_text()
            inputs = editor.locator('input[type="number"]')
            assert inputs.count() == 2
            assert inputs.nth(0).input_value() == str(0x7F0220)
            assert inputs.nth(1).input_value() == str(0x55)
            inputs.nth(0).fill(str(0x7F0240))
            inputs.nth(1).fill(str(0xAA))
            editor.get_by_role("button", name="Apply command", exact=True).click()

            page.wait_for_function('state.events.detail?.objects?.[0]?.functions?.[0]?.commands?.[0]?.editor?.values?.bitMask === 170')
            page.wait_for_function('document.querySelector(".ct-command-summary")?.textContent === "Toggle bits 0xAA in 0x7F0240"')
            page.wait_for_function('document.querySelector(".ct-hex")?.textContent === "AA 20"')
            assert saved_requests
            request = saved_requests[-1]
            assert request["eventId"] == 21
            assert request["objectId"] == 0
            assert request["functionId"] == 0
            assert request["commandIndex"] == 0
            assert request["sha256"] == "b" * 64
            assert request["values"] == {"memoryAddress": 0x7F0240, "bitMask": 0xAA}
            assert page.locator(".ct-warning").count() == 0
            page.screenshot(path=str(ARTIFACTS / "bit-editor.png"), full_page=True)
            page.close()
        finally:
            browser.close()

    result = {"fixtureOnly": True, "bitEditor": True, "errors": errors}
    (ARTIFACTS / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert not errors, errors
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
