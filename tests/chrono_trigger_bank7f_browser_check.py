"""Fixture-only browser regression for Chrono Trigger bank-7F event editors."""
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

ARTIFACTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "chrono-trigger-bank7f-browser"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ORIGIN = "http://chrono-bank7f-fixture.local"

EVENT_LIST = {
    "kind": "field-events", "matchCount": 1, "offset": 0, "limit": 100,
    "rows": [{
        "id": 23, "name": "Atel 0023", "path": "Game/field/atel/Atel_0023.dat",
        "source": "archive", "sha256": "g" * 64, "objectCount": 1, "decodedCommandCount": 3,
    }],
}
EVENT_DETAIL = {
    "kind": "field-event", "id": 23, "name": "Atel 0023", "path": "Game/field/atel/Atel_0023.dat",
    "source": "archive", "sha256": "g" * 64, "objectCount": 1, "uniqueFunctionBounds": 1,
    "decodedCommandCount": 3, "completeFunctionBounds": 1, "problemFunctionBounds": 0,
    "objects": [{
        "id": 0, "start": 32, "end": 41,
        "functions": [{
            "id": 0, "name": "Startup", "start": 32, "end": 41, "length": 9, "complete": True,
            "commands": [
                {
                    "offset": 32, "opcode": 0x65, "name": "Set Bank7F Bit", "size": 3,
                    "argumentsHex": "03 44", "argumentBytes": 2,
                    "semantic": {
                        "summary": "Set bit 3 in 0x7F0044",
                        "memoryAddress": 0x7F0044, "bitIndex": 3, "operation": "set-bank7f-bit",
                    },
                    "editor": {
                        "editor": "fixed-fields", "opcode": 0x65, "opcodeHex": "0x65", "fixedWidth": True,
                        "fields": [
                            {"key": "memoryAddress", "label": "Bank-7F address", "kind": "integer", "min": 0x7F0000, "max": 0x7F01FF},
                            {"key": "bitIndex", "label": "Bit index", "kind": "integer", "min": 0, "max": 7},
                        ],
                        "values": {"memoryAddress": 0x7F0044, "bitIndex": 3},
                    },
                },
                {
                    "offset": 35, "opcode": 0x16, "name": "Compare Bank 7F", "size": 5,
                    "argumentsHex": "55 22 85 01", "argumentBytes": 4,
                    "semantic": {
                        "summary": "8-bit 0x7F0155 less or equal 34 · false → jump +1",
                        "widthBytes": 1, "memoryAddress": 0x7F0155, "value": 0x22,
                        "operation": 5, "operationName": "less or equal", "jumpOffset": 1,
                        "jumpOnFalse": True, "bank7F": True,
                    },
                    "editor": {
                        "editor": "fixed-fields", "opcode": 0x16, "opcodeHex": "0x16", "fixedWidth": True,
                        "fields": [
                            {"key": "memoryAddress", "label": "Bank-7F address", "kind": "integer", "min": 0x7F0000, "max": 0x7F01FF},
                            {"key": "value", "label": "Comparison value", "kind": "integer", "min": 0, "max": 255},
                            {"key": "operation", "label": "Comparison operation (0–7)", "kind": "integer", "min": 0, "max": 7},
                            {"key": "jumpOffset", "label": "Jump bytes if false", "kind": "integer", "min": 0, "max": 255},
                        ],
                        "values": {"memoryAddress": 0x7F0155, "value": 0x22, "operation": 5, "jumpOffset": 1},
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
                    command_index = int(request["commandIndex"])
                    command = event_detail["objects"][0]["functions"][0]["commands"][command_index]
                    if command_index == 0:
                        address = int(values["memoryAddress"])
                        bit_index = int(values["bitIndex"])
                        relative = address - 0x7F0000
                        packed = bit_index | (0x80 if relative >= 0x100 else 0)
                        command["argumentsHex"] = f"{packed:02X} {relative & 0xFF:02X}"
                        command["semantic"] = {
                            "summary": f"Set bit {bit_index} in 0x{address:06X}",
                            "memoryAddress": address, "bitIndex": bit_index, "operation": "set-bank7f-bit",
                        }
                        command["editor"]["values"] = {"memoryAddress": address, "bitIndex": bit_index}
                        event_detail["sha256"] = "h" * 64
                    else:
                        address = int(values["memoryAddress"])
                        value = int(values["value"])
                        operation = int(values["operation"])
                        jump_offset = int(values["jumpOffset"])
                        relative = address - 0x7F0000
                        packed = operation | (0x80 if relative >= 0x100 else 0)
                        operation_names = (
                            "equals", "not equals", "greater than", "less than",
                            "greater or equal", "less or equal", "bitwise AND nonzero", "bitwise OR nonzero",
                        )
                        command["argumentsHex"] = f"{relative & 0xFF:02X} {value:02X} {packed:02X} {jump_offset:02X}"
                        command["semantic"] = {
                            "summary": f"8-bit 0x{address:06X} {operation_names[operation]} {value} · false → jump +{jump_offset}",
                            "widthBytes": 1, "memoryAddress": address, "value": value,
                            "operation": operation, "operationName": operation_names[operation],
                            "jumpOffset": jump_offset, "jumpOnFalse": True, "bank7F": True,
                        }
                        command["editor"]["values"] = {
                            "memoryAddress": address, "value": value,
                            "operation": operation, "jumpOffset": jump_offset,
                        }
                        event_detail["sha256"] = "i" * 64
                    event_detail["source"] = "project"
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(event_detail))
                else:
                    route.fulfill(status=404, content_type="application/json", body=json.dumps({"error": path}))

            page.route(f"{ORIGIN}/**", handle)
            page.goto(ORIGIN + "/", wait_until="domcontentloaded")
            page.wait_for_function('state.scenes.data?.rows?.length === 1')
            page.evaluate('navigate("events")')
            page.wait_for_function('state.events.detail?.id === 23')

            editors = page.locator(".ct-command-editor")
            assert editors.count() == 2

            bit_editor = editors.nth(0)
            bit_inputs = bit_editor.locator('input:is([type="number"],[inputmode="decimal"])')
            assert bit_inputs.count() == 2
            assert bit_inputs.nth(0).input_value().replace(",", "") == str(0x7F0044)
            assert bit_inputs.nth(1).input_value().replace(",", "") == "3"
            bit_inputs.nth(0).focus()
            bit_inputs.nth(0).fill(str(0x7F01AA))
            bit_inputs.nth(1).focus()
            bit_inputs.nth(1).fill("7")
            bit_editor.get_by_role("button", name="Apply command", exact=True).click()

            page.wait_for_function('document.querySelectorAll(".ct-hex")[0]?.textContent === "87 AA"')
            page.wait_for_function('document.querySelectorAll(".ct-command-summary")[0]?.textContent === "Set bit 7 in 0x7F01AA"')
            first = saved_requests[-1]
            assert first["sha256"] == "g" * 64
            assert first["commandIndex"] == 0
            assert first["values"] == {"memoryAddress": 0x7F01AA, "bitIndex": 7}

            compare_editor = page.locator(".ct-command-editor").nth(1)
            compare_inputs = compare_editor.locator('input:is([type="number"],[inputmode="decimal"])')
            assert compare_inputs.count() == 4
            assert compare_inputs.nth(0).input_value().replace(",", "") == str(0x7F0155)
            compare_inputs.nth(0).focus()
            compare_inputs.nth(0).fill(str(0x7F0044))
            compare_inputs.nth(1).focus()
            compare_inputs.nth(1).fill(str(0x7F))
            compare_inputs.nth(2).focus()
            compare_inputs.nth(2).fill("2")
            compare_editor.get_by_role("button", name="Apply command", exact=True).click()

            page.wait_for_function('document.querySelectorAll(".ct-hex")[1]?.textContent === "44 7F 02 01"')
            page.wait_for_function('document.querySelectorAll(".ct-command-summary")[1]?.textContent === "8-bit 0x7F0044 greater than 127 · false → jump +1"')
            second = saved_requests[-1]
            assert second["sha256"] == "h" * 64
            assert second["commandIndex"] == 1
            assert second["values"] == {
                "memoryAddress": 0x7F0044, "value": 0x7F, "operation": 2, "jumpOffset": 1,
            }
            assert page.locator(".ct-warning").count() == 0
            page.screenshot(path=str(ARTIFACTS / "bank7f-editors.png"), full_page=True)
            page.close()
        finally:
            browser.close()

    result = {"fixtureOnly": True, "bank7FBitEditor": True, "bank7FComparisonEditor": True, "errors": errors}
    (ARTIFACTS / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert not errors, errors
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
