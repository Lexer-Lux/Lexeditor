"""Fixture-only browser regression for PC-only extended-memory event editing."""
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

ARTIFACTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "chrono-trigger-pc-extended-browser"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ORIGIN = "http://chrono-pc-ext-fixture.local"

EVENT_LIST = {
    "kind": "field-events", "matchCount": 1, "offset": 0, "limit": 100,
    "rows": [{
        "id": 22, "name": "Atel 0022", "path": "Game/field/atel/Atel_0022.dat",
        "source": "archive", "sha256": "d" * 64, "objectCount": 1, "decodedCommandCount": 2,
    }],
}
EVENT_DETAIL = {
    "kind": "field-event", "id": 22, "name": "Atel 0022", "path": "Game/field/atel/Atel_0022.dat",
    "source": "archive", "sha256": "d" * 64, "objectCount": 1, "uniqueFunctionBounds": 1,
    "decodedCommandCount": 2, "completeFunctionBounds": 1, "problemFunctionBounds": 0,
    "objects": [{
        "id": 0, "start": 32, "end": 36,
        "functions": [{
            "id": 0, "name": "Startup", "start": 32, "end": 36, "length": 4, "complete": True,
            "commands": [
                {
                    "offset": 32, "opcode": 0x3D, "name": "Local to Extended Memory", "size": 3,
                    "argumentsHex": "11 12", "argumentBytes": 2,
                    "semantic": {
                        "summary": "PC Copy8 local slot 17 → extended slot 18 (raw slots)",
                        "widthBytes": 1, "pcOnly": True, "rawSlots": True,
                        "localSlot": 0x11, "extendedSlot": 0x12,
                    },
                    "editor": {
                        "editor": "fixed-fields", "opcode": 0x3D, "opcodeHex": "0x3D", "fixedWidth": True,
                        "fields": [
                            {"key": "localSlot", "label": "Local-memory slot (raw)", "kind": "integer", "min": 0, "max": 255},
                            {"key": "extendedSlot", "label": "Extended-memory slot (raw)", "kind": "integer", "min": 0, "max": 255},
                        ],
                        "values": {"localSlot": 0x11, "extendedSlot": 0x12},
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
                    local_slot = int(values["localSlot"])
                    extended_slot = int(values["extendedSlot"])
                    command = event_detail["objects"][0]["functions"][0]["commands"][0]
                    command["argumentsHex"] = f"{local_slot:02X} {extended_slot:02X}"
                    command["semantic"] = {
                        "summary": f"PC Copy8 local slot {local_slot} → extended slot {extended_slot} (raw slots)",
                        "widthBytes": 1, "pcOnly": True, "rawSlots": True,
                        "localSlot": local_slot, "extendedSlot": extended_slot,
                    }
                    command["editor"]["values"] = {"localSlot": local_slot, "extendedSlot": extended_slot}
                    event_detail["source"] = "project"
                    event_detail["sha256"] = "e" * 64
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(event_detail))
                else:
                    route.fulfill(status=404, content_type="application/json", body=json.dumps({"error": path}))

            page.route(f"{ORIGIN}/**", handle)
            page.goto(ORIGIN + "/", wait_until="domcontentloaded")
            page.wait_for_function('state.scenes.data?.rows?.length === 1')
            page.evaluate('navigate("events")')
            page.wait_for_function('state.events.detail?.id === 22')

            editor = page.locator(".ct-command-editor")
            assert editor.count() == 1
            text = editor.inner_text()
            assert "Local-memory slot (raw)" in text
            assert "Extended-memory slot (raw)" in text
            assert "0x7F" not in text
            inputs = editor.locator('input[type="number"]')
            assert inputs.count() == 2
            assert inputs.nth(0).input_value() == str(0x11)
            assert inputs.nth(1).input_value() == str(0x12)
            inputs.nth(0).fill(str(0x22))
            inputs.nth(1).fill(str(0x44))
            editor.get_by_role("button", name="Apply command", exact=True).click()

            page.wait_for_function('state.events.detail?.objects?.[0]?.functions?.[0]?.commands?.[0]?.editor?.values?.extendedSlot === 68')
            page.wait_for_function('document.querySelector(".ct-command-summary")?.textContent === "PC Copy8 local slot 34 → extended slot 68 (raw slots)"')
            page.wait_for_function('document.querySelector(".ct-hex")?.textContent === "22 44"')
            assert saved_requests
            request = saved_requests[-1]
            assert request["eventId"] == 22
            assert request["objectId"] == 0
            assert request["functionId"] == 0
            assert request["commandIndex"] == 0
            assert request["sha256"] == "d" * 64
            assert request["values"] == {"localSlot": 0x22, "extendedSlot": 0x44}
            assert page.locator(".ct-warning").count() == 0
            page.screenshot(path=str(ARTIFACTS / "pc-extended-editor.png"), full_page=True)
            page.close()
        finally:
            browser.close()

    result = {"fixtureOnly": True, "pcExtendedEditor": True, "errors": errors}
    (ARTIFACTS / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert not errors, errors
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
