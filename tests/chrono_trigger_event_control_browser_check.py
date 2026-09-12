"""Fixture-only browser regression for Chrono Trigger facing/control event editors."""
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

ARTIFACTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "chrono-trigger-event-control-browser"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ORIGIN = "http://chrono-event-control-fixture.local"

EVENT_LIST = {
    "kind": "field-events", "matchCount": 1, "offset": 0, "limit": 100,
    "rows": [{
        "id": 22, "name": "Atel 0022", "path": "Game/field/atel/Atel_0022.dat",
        "source": "archive", "sha256": "b" * 64, "objectCount": 1, "decodedCommandCount": 4,
    }],
}
EVENT_DETAIL = {
    "kind": "field-event", "id": 22, "name": "Atel 0022", "path": "Game/field/atel/Atel_0022.dat",
    "source": "archive", "sha256": "b" * 64, "objectCount": 1, "uniqueFunctionBounds": 1,
    "decodedCommandCount": 4, "completeFunctionBounds": 1, "problemFunctionBounds": 0,
    "objects": [{
        "id": 0, "start": 32, "end": 41,
        "functions": [{
            "id": 0, "name": "Startup", "start": 32, "end": 41, "length": 9, "complete": True,
            "commands": [
                {
                    "offset": 32, "opcode": 0x23, "name": "Get Object Facing", "size": 3,
                    "argumentsHex": "06 10", "argumentBytes": 2,
                    "semantic": {
                        "summary": "Get object 3 facing → 0x7F0220", "targetId": 3,
                        "targetType": "object", "storeAddress": 0x7F0220, "operation": "get-facing",
                    },
                    "editor": {
                        "editor": "fixed-fields", "opcode": 0x23, "opcodeHex": "0x23", "fixedWidth": True,
                        "fields": [
                            {"key": "targetId", "label": "Object ID", "kind": "integer", "min": 0, "max": 127},
                            {"key": "storeAddress", "label": "Store facing at", "kind": "integer", "min": 0x7F0200, "max": 0x7F03FE},
                        ],
                        "values": {"targetId": 3, "storeAddress": 0x7F0220},
                    },
                },
                {
                    "offset": 35, "opcode": 0x0B, "name": "Disable Processing", "size": 2,
                    "argumentsHex": "08", "argumentBytes": 1,
                    "semantic": {
                        "summary": "Disable script processing for object 4", "objectId": 4,
                        "operation": "processing-off",
                    },
                    "editor": {
                        "editor": "fixed-fields", "opcode": 0x0B, "opcodeHex": "0x0B", "fixedWidth": True,
                        "fields": [
                            {"key": "objectId", "label": "Object ID", "kind": "integer", "min": 0, "max": 127},
                        ],
                        "values": {"objectId": 4},
                    },
                },
                {
                    "offset": 37, "opcode": 0x9D, "name": "Vector Move from Memory", "size": 3,
                    "argumentsHex": "14 15", "argumentBytes": 2,
                    "semantic": {
                        "summary": "Vector move from direction 0x7F0228 · magnitude 0x7F022A",
                        "directionAddress": 0x7F0228, "magnitudeAddress": 0x7F022A,
                        "operation": "vector-move-from-memory",
                    },
                    "editor": {
                        "editor": "fixed-fields", "opcode": 0x9D, "opcodeHex": "0x9D", "fixedWidth": True,
                        "fields": [
                            {"key": "directionAddress", "label": "Direction source", "kind": "integer", "min": 0x7F0200, "max": 0x7F03FE},
                            {"key": "magnitudeAddress", "label": "Magnitude source", "kind": "integer", "min": 0x7F0200, "max": 0x7F03FE},
                        ],
                        "values": {"directionAddress": 0x7F0228, "magnitudeAddress": 0x7F022A},
                    },
                },
                {"offset": 40, "opcode": 0x00, "name": "Return", "size": 1, "argumentsHex": ""},
            ],
        }],
    }],
}


def main() -> None:
    errors: list[str] = []
    saved_requests: list[dict] = []
    event_detail = copy.deepcopy(EVENT_DETAIL)
    html = _editor_html()
    sha_chars = iter(("c", "d", "e"))

    with sync_playwright() as playwright:
        import shutil
        browser = playwright.chromium.launch(
            executable_path=shutil.which("chromium") or None,
            headless=True,
            args=["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
        )
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 900})
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
                    command_index = int(request["commandIndex"])
                    command = event_detail["objects"][0]["functions"][0]["commands"][command_index]

                    if command_index == 0:
                        target = int(values["targetId"])
                        address = int(values["storeAddress"])
                        slot = (address - 0x7F0200) // 2
                        command["argumentsHex"] = f"{target * 2:02X} {slot:02X}"
                        command["semantic"] = {
                            "summary": f"Get object {target} facing → 0x{address:06X}",
                            "targetId": target, "targetType": "object", "storeAddress": address,
                            "operation": "get-facing",
                        }
                        command["editor"]["values"] = {"targetId": target, "storeAddress": address}
                    elif command_index == 1:
                        object_id = int(values["objectId"])
                        command["argumentsHex"] = f"{object_id * 2:02X}"
                        command["semantic"] = {
                            "summary": f"Disable script processing for object {object_id}",
                            "objectId": object_id, "operation": "processing-off",
                        }
                        command["editor"]["values"] = {"objectId": object_id}
                    elif command_index == 2:
                        direction = int(values["directionAddress"])
                        magnitude = int(values["magnitudeAddress"])
                        direction_slot = (direction - 0x7F0200) // 2
                        magnitude_slot = (magnitude - 0x7F0200) // 2
                        command["argumentsHex"] = f"{direction_slot:02X} {magnitude_slot:02X}"
                        command["semantic"] = {
                            "summary": f"Vector move from direction 0x{direction:06X} · magnitude 0x{magnitude:06X}",
                            "directionAddress": direction, "magnitudeAddress": magnitude,
                            "operation": "vector-move-from-memory",
                        }
                        command["editor"]["values"] = {
                            "directionAddress": direction, "magnitudeAddress": magnitude,
                        }
                    else:
                        raise AssertionError(f"Unexpected command index {command_index}")

                    event_detail["source"] = "project"
                    event_detail["sha256"] = next(sha_chars) * 64
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(event_detail))
                else:
                    route.fulfill(status=404, content_type="application/json", body=json.dumps({"error": path}))

            page.route(f"{ORIGIN}/**", handle)
            page.goto(ORIGIN + "/", wait_until="domcontentloaded")
            page.wait_for_function('state.scenes.data?.rows?.length === 1')
            page.evaluate('navigate("events")')
            page.wait_for_function('state.events.detail?.id === 22')

            editors = page.locator(".ct-command-editor")
            assert editors.count() == 3

            facing = editors.nth(0)
            assert "Store facing at" in facing.inner_text()
            facing_inputs = facing.locator('input[type="number"]')
            assert facing_inputs.count() == 2
            facing_inputs.nth(0).fill("7")
            facing_inputs.nth(1).fill(str(0x7F0240))
            facing.get_by_role("button", name="Apply command", exact=True).click()
            page.wait_for_function('document.querySelectorAll(".ct-hex")[0]?.textContent === "0E 20"')
            page.wait_for_function('document.querySelectorAll(".ct-command-summary")[0]?.textContent === "Get object 7 facing → 0x7F0240"')
            assert saved_requests[-1]["sha256"] == "b" * 64
            assert saved_requests[-1]["values"] == {"targetId": 7, "storeAddress": 0x7F0240}

            editors = page.locator(".ct-command-editor")
            processing = editors.nth(1)
            processing.locator('input[type="number"]').fill("9")
            processing.get_by_role("button", name="Apply command", exact=True).click()
            page.wait_for_function('document.querySelectorAll(".ct-hex")[1]?.textContent === "12"')
            page.wait_for_function('document.querySelectorAll(".ct-command-summary")[1]?.textContent === "Disable script processing for object 9"')
            assert saved_requests[-1]["sha256"] == "c" * 64
            assert saved_requests[-1]["values"] == {"objectId": 9}

            editors = page.locator(".ct-command-editor")
            vector = editors.nth(2)
            vector_inputs = vector.locator('input[type="number"]')
            assert vector_inputs.count() == 2
            vector_inputs.nth(0).fill(str(0x7F0244))
            vector_inputs.nth(1).fill(str(0x7F0246))
            vector.get_by_role("button", name="Apply command", exact=True).click()
            page.wait_for_function('document.querySelectorAll(".ct-hex")[2]?.textContent === "22 23"')
            page.wait_for_function('document.querySelectorAll(".ct-command-summary")[2]?.textContent === "Vector move from direction 0x7F0244 · magnitude 0x7F0246"')
            assert saved_requests[-1]["sha256"] == "d" * 64
            assert saved_requests[-1]["values"] == {
                "directionAddress": 0x7F0244,
                "magnitudeAddress": 0x7F0246,
            }

            assert [request["commandIndex"] for request in saved_requests] == [0, 1, 2]
            assert page.locator(".ct-warning").count() == 0
            page.screenshot(path=str(ARTIFACTS / "event-control-editors.png"), full_page=True)
            page.close()
        finally:
            browser.close()

    result = {
        "fixtureOnly": True,
        "facingEditor": True,
        "processingEditor": True,
        "vectorMemoryEditor": True,
        "errors": errors,
    }
    (ARTIFACTS / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert not errors, errors
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
