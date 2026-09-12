"""Fixture-only browser check for Chrono Trigger desktop map and event surfaces."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.chrono_trigger.scene_render import png_rgba

ARTIFACTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "chrono-trigger-browser"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
ORIGIN = "http://chrono-fixture.local"

PNG = png_rgba(32, 32, bytes((255, 0, 0, 255)) * 32 * 32)
SCENE_MAP = {
    "sceneId": 0,
    "mapId": 0,
    "path": "Game/field/MapTable/MapTable_0000.dat",
    "sceneWidth": 16,
    "sceneHeight": 16,
    "header": {"scrollLayer2": {"xPixelsPerSecond": 0, "yPixelsPerSecond": 0}},
    "layerPriorities": [3, 1, 2, 2],
    "priorityPath": "Game/field/PrioMap/PrioMap0.dat",
    "prioritySemanticsKnown": False,
    "compositionBits": {
        "screen": {
            "raw": 0x4B,
            "main": {"layer1": True, "layer2": True, "layer3": False, "sprites": True},
            "sub": {"layer1": False, "layer2": False, "layer3": True, "sprites": False},
        },
        "effects": {
            "raw": 0x53,
            "targets": {"layer1": True, "layer2": True, "layer3": False, "sprites": True},
            "unknown08": False, "defaultColor": False, "halfIntensity": True, "subtract": False,
        },
        "semantics": "CTViewer PC MapTable bit labels only; Lexeditor does not emulate render order or blending from these flags.",
    },
    "chipAnimations": {
        "present": True,
        "valid": True,
        "path": "Game/field/BGAnime/bganimeinfo_4.dat",
        "declaredAnimationCount": 1,
        "decodedAnimationCount": 1,
        "playbackEmulated": False,
        "animations": [{
            "index": 0, "destinationChipRange": [12, 15],
            "frames": [
                {"sourceChipRange": [0, 3], "durationTicks": 16, "durationRaw": 0x10},
                {"sourceChipRange": [4, 7], "durationTicks": 4, "durationRaw": 0x80},
            ],
        }],
    },
    "layers": {
        "layer1": {"width": 16, "height": 16, "tiles": [1] * 256},
        "layer2": {"width": 16, "height": 16, "tiles": [2] * 256},
        "layer3": {"enabled": True, "width": 16, "height": 16, "tiles": [3] * 256},
    },
    "properties": [{"collisionIndex": 1}] * 256,
    "collisionCounts": {"Full": 256},
    "propertyStats": {"encodedRecords": 1, "expected": 256, "padded": 0, "trimmed": 0},
}
SCENES = {
    "kind": "scene-headers", "matchCount": 1, "offset": 0, "limit": 100, "labelLanguage": "en",
    "fields": [],
    "rows": [{
        "id": 0, "name": "Millennial Fair", "path": "Game/field/Mapinfo/mapinfo_0.dat",
        "source": "archive", "sha256": "a" * 64,
        "values": {"musicIndex": 10, "tilesetL12": 1, "tilesetL12Assembly": 2, "tilesetL3": 9,
                   "palette": 3, "mapIndex": 0},
    }],
}
WORLDS = {
    "kind": "world-headers", "path": "Game/common/bankc6.bin", "headerOffset": 0, "recordSize": 23,
    "labelLanguage": "en", "fields": [],
    "rows": [{
        "id": 0, "name": "Present", "source": "archive",
        "values": {"map": 4, "palette": 3, "assemblyL12": 2},
        "derived": {"effectivePaletteAnimations": 0},
    }],
}
EVENT_LIST = {
    "kind": "field-events", "matchCount": 1, "offset": 0, "limit": 100,
    "rows": [{
        "id": 20, "name": "Atel 0020", "path": "Game/field/atel/Atel_0020.dat",
        "source": "archive", "sha256": "b" * 64, "objectCount": 1, "decodedCommandCount": 3,
    }],
}
EVENT_DETAIL = {
    "kind": "field-event", "id": 20, "name": "Atel 0020", "path": "Game/field/atel/Atel_0020.dat",
    "source": "archive", "sha256": "b" * 64, "objectCount": 1, "uniqueFunctionBounds": 1,
    "decodedCommandCount": 3, "completeFunctionBounds": 1, "problemFunctionBounds": 0,
    "objects": [{
        "id": 0, "start": 32, "end": 41,
        "functions": [{
            "id": 0, "name": "Startup", "start": 32, "end": 41, "length": 9, "complete": True,
            "commands": [
                {
                    "offset": 32, "opcode": 0xA6, "name": "NPC Facing", "size": 2,
                    "argumentsHex": "01", "argumentBytes": 1,
                    "semantic": {"summary": "NPC facing down", "facing": 1, "facingName": "down"},
                    "editor": {
                        "editor": "fixed-fields", "opcode": 0xA6, "opcodeHex": "0xA6", "fixedWidth": True,
                        "fields": [{
                            "key": "facing", "label": "Facing (0 up, 1 down, 2 left, 3 right)",
                            "kind": "integer", "min": 0, "max": 3,
                        }],
                        "values": {"facing": 1},
                    },
                },
                {
                    "offset": 34, "opcode": 0x13, "name": "If 16-bit", "size": 6,
                    "argumentsHex": "10 34 12 03 01", "argumentBytes": 5,
                    "semantic": {
                        "summary": "16-bit 0x7F0220 less than 4660 · false → jump +1",
                        "widthBytes": 2, "memoryAddress": 0x7F0220, "value": 0x1234,
                        "operation": 3, "operationName": "less than", "jumpOffset": 1, "jumpOnFalse": True,
                    },
                    "editor": {
                        "editor": "fixed-fields", "opcode": 0x13, "opcodeHex": "0x13", "fixedWidth": True,
                        "fields": [
                            {"key": "memoryAddress", "label": "Script-memory address", "kind": "integer", "min": 0x7F0200, "max": 0x7F03FE},
                            {"key": "value", "label": "Comparison value", "kind": "integer", "min": 0, "max": 0xFFFF},
                            {"key": "operation", "label": "Comparison operation (0–7)", "kind": "integer", "min": 0, "max": 7},
                            {"key": "jumpOffset", "label": "Jump bytes if false", "kind": "integer", "min": 0, "max": 0xFF},
                        ],
                        "values": {"memoryAddress": 0x7F0220, "value": 0x1234, "operation": 3, "jumpOffset": 1},
                    },
                },
                {"offset": 40, "opcode": 0x00, "name": "Return", "size": 1, "argumentsHex": ""},
            ],
        }],
    }],
}
DASHBOARD = {
    "game": {"archive": "resources.bin", "ready": True},
    "project": {"writable": True, "root": "FixtureMod", "overlayResources": 0},
    "datasets": {"sceneHeaders": 1, "worldHeaders": 8},
    "deployment": {},
}


def _editor_html() -> str:
    html = (ROOT / "games/chrono_trigger/editor.html").read_text(encoding="utf-8")
    html = html.replace(
        '<link rel="stylesheet" href="/shared/framework.css">',
        "<style>" + (ROOT / "ui/framework.css").read_text(encoding="utf-8") + "</style>",
    )
    html = html.replace(
        '<script src="/shared/framework.js"></script>',
        "<script>" + (ROOT / "ui/framework.js").read_text(encoding="utf-8") + "</script>",
    )
    modules = (
        "<script>" + (ROOT / "games/chrono_trigger/event_editor.js").read_text(encoding="utf-8") + "</script>"
        "<script>" + (ROOT / "games/chrono_trigger/map_previews.js").read_text(encoding="utf-8") + "</script>"
    )
    return html.replace("</body>", modules + "</body>", 1)


def main() -> None:
    errors: list[str] = []
    results = []
    saved_event_requests: list[dict] = []
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
                elif path == "/api/scene-map":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(SCENE_MAP))
                elif path == "/api/worlds":
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(WORLDS))
                elif path == "/api/events":
                    if "id=" in route.request.url:
                        route.fulfill(status=200, content_type="application/json", body=json.dumps(event_detail))
                    else:
                        route.fulfill(status=200, content_type="application/json", body=json.dumps(EVENT_LIST))
                elif path == "/api/save/event-fields":
                    request = json.loads(route.request.post_data or "{}")
                    saved_event_requests.append(request)
                    command_index = int(request.get("commandIndex", -1))
                    values = request.get("values", {})
                    if command_index == 0:
                        facing = int(values.get("facing", 1))
                        command = event_detail["objects"][0]["functions"][0]["commands"][0]
                        command["argumentsHex"] = f"{facing:02X}"
                        command["semantic"] = {
                            "summary": ("NPC facing up", "NPC facing down", "NPC facing left", "NPC facing right")[facing],
                            "facing": facing,
                            "facingName": ("up", "down", "left", "right")[facing],
                        }
                        command["editor"]["values"]["facing"] = facing
                        event_detail["sha256"] = "c" * 64
                    elif command_index == 1:
                        address = int(values["memoryAddress"])
                        value = int(values["value"])
                        operation = int(values["operation"])
                        jump = int(values["jumpOffset"])
                        command = event_detail["objects"][0]["functions"][0]["commands"][1]
                        slot = (address - 0x7F0200) // 2
                        command["argumentsHex"] = f"{slot:02X} {value & 0xFF:02X} {(value >> 8) & 0xFF:02X} {operation:02X} {jump:02X}"
                        operation_names = (
                            "equals", "not equals", "greater than", "less than",
                            "greater or equal", "less or equal", "bitwise AND nonzero", "bitwise OR nonzero",
                        )
                        command["semantic"] = {
                            "summary": f"16-bit 0x{address:06X} {operation_names[operation]} {value} · false → jump +{jump}",
                            "widthBytes": 2, "memoryAddress": address, "value": value,
                            "operation": operation, "operationName": operation_names[operation],
                            "jumpOffset": jump, "jumpOnFalse": True,
                        }
                        command["editor"]["values"] = {
                            "memoryAddress": address, "value": value, "operation": operation, "jumpOffset": jump,
                        }
                        event_detail["sha256"] = "d" * 64
                    else:
                        route.fulfill(status=400, content_type="application/json", body=json.dumps({"error": "unexpected command"}))
                        return
                    event_detail["source"] = "project"
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(event_detail))
                elif path in {"/api/scene-raster", "/api/world-raster"}:
                    route.fulfill(status=200, content_type="image/png", body=PNG)
                else:
                    route.fulfill(status=404, content_type="application/json", body=json.dumps({"error": path}))

            page.route(f"{ORIGIN}/**", handle)
            page.goto(ORIGIN + "/", wait_until="domcontentloaded")
            page.wait_for_function('state.scenes.data?.rows?.length === 1')

            page.locator(".ct-section-tabs").get_by_role("button", name="Map", exact=True).click()
            page.wait_for_function('state.scenes.map?.sceneWidth === 16')
            diagnostics = page.locator(".ct-render-diagnostics")
            assert "1/1 BGAnime records" in diagnostics.locator("summary").inner_text()
            diagnostics.locator("summary").click()
            diagnostic_text = diagnostics.inner_text()
            assert "main: L1, L2, sprites" in diagnostic_text
            assert "sub: L3" in diagnostic_text
            assert "3 / 1 / 2 / 2" in diagnostic_text
            assert "semantics unknown" in diagnostic_text
            assert "chips 12–15" in diagnostic_text
            assert "16 ticks" in diagnostic_text
            assert "does not emulate animation playback" in diagnostic_text

            scene_select = page.locator(".ct-map-panel select")
            scene_select.select_option("raster1")
            page.wait_for_function('document.querySelector(".ct-raster-image")?.naturalWidth > 0')
            assert "/api/scene-raster" in page.locator(".ct-raster-image").get_attribute("src")
            assert "isolated layer only" in page.locator(".ct-raster-policy").inner_text()
            assert page.locator(".ct-warning").count() == 0
            page.screenshot(path=str(ARTIFACTS / "scene-raster.png"), full_page=True)

            scene_select.select_option("raster3")
            page.wait_for_function('document.querySelector(".ct-raster-image")?.src.includes("layer=3")')
            page.wait_for_function('document.querySelector(".ct-raster-image")?.naturalWidth > 0')
            assert "Actual PC L3 raster" in page.locator(".ct-raster-policy").inner_text()
            assert "main/sub-screen" in page.locator(".ct-raster-policy").inner_text()
            assert page.locator(".ct-warning").count() == 0
            page.screenshot(path=str(ARTIFACTS / "scene-raster-l3.png"), full_page=True)

            page.evaluate('navigate("worlds")')
            page.wait_for_function('state.worlds.data?.rows?.length === 1')
            page.locator(".ct-section-tabs").get_by_role("button", name="Map", exact=True).click()
            page.wait_for_function('document.querySelector(".ct-raster-image")?.naturalWidth > 0')
            world_image = page.locator(".ct-raster-image")
            assert "/api/world-raster" in world_image.get_attribute("src")
            assert "1536×1024px" in page.locator(".ct-raster-policy").inner_text()
            world_select = page.locator(".ct-map-panel select")
            world_select.select_option("2")
            page.wait_for_function('document.querySelector(".ct-raster-image")?.src.includes("layer=2")')
            page.wait_for_function('document.querySelector(".ct-raster-image")?.naturalWidth > 0')
            assert "main/sub-screen" in page.locator(".ct-raster-policy").inner_text()
            assert page.locator(".ct-warning").count() == 0
            page.screenshot(path=str(ARTIFACTS / "world-raster.png"), full_page=True)

            page.evaluate('navigate("events")')
            page.wait_for_function('state.events.detail?.id === 20')
            editors = page.locator(".ct-command-editor")
            assert editors.count() == 2

            facing_editor = editors.nth(0)
            assert "Facing (0 up, 1 down, 2 left, 3 right)" in facing_editor.inner_text()
            facing_input = facing_editor.locator('input:is([type="number"],[inputmode="decimal"])')
            assert facing_input.input_value().replace(",", "") == "1"
            facing_input.focus()
            facing_input.fill("3")
            facing_editor.get_by_role("button", name="Apply command", exact=True).click()
            page.wait_for_function('state.events.detail?.objects?.[0]?.functions?.[0]?.commands?.[0]?.editor?.values?.facing === 3')
            page.wait_for_function('document.querySelectorAll(".ct-command-summary")[0]?.textContent === "NPC facing right"')
            page.wait_for_function('document.querySelectorAll(".ct-hex")[0]?.textContent === "03"')
            assert saved_event_requests
            facing_request = saved_event_requests[-1]
            assert facing_request["eventId"] == 20
            assert facing_request["objectId"] == 0
            assert facing_request["functionId"] == 0
            assert facing_request["commandIndex"] == 0
            assert facing_request["sha256"] == "b" * 64
            assert facing_request["values"] == {"facing": 3}

            comparison_editor = page.locator(".ct-command-editor").nth(1)
            comparison_text = comparison_editor.inner_text()
            assert "Script-memory address" in comparison_text
            assert "Comparison value" in comparison_text
            assert "Comparison operation (0–7)" in comparison_text
            assert "Jump bytes if false" in comparison_text
            comparison_inputs = comparison_editor.locator('input:is([type="number"],[inputmode="decimal"])')
            assert comparison_inputs.count() == 4
            assert comparison_inputs.nth(0).input_value().replace(",", "") == str(0x7F0220)
            assert comparison_inputs.nth(1).input_value().replace(",", "") == str(0x1234)
            assert comparison_inputs.nth(2).input_value().replace(",", "") == "3"
            assert comparison_inputs.nth(3).input_value().replace(",", "") == "1"
            comparison_inputs.nth(1).focus()
            comparison_inputs.nth(1).fill(str(0xBEEF))
            comparison_editor.get_by_role("button", name="Apply command", exact=True).click()
            page.wait_for_function('state.events.detail?.objects?.[0]?.functions?.[0]?.commands?.[1]?.editor?.values?.value === 48879')
            page.wait_for_function('document.querySelectorAll(".ct-command-summary")[1]?.textContent.includes("48879")')
            page.wait_for_function('document.querySelectorAll(".ct-hex")[1]?.textContent === "10 EF BE 03 01"')
            comparison_request = saved_event_requests[-1]
            assert comparison_request["commandIndex"] == 1
            assert comparison_request["sha256"] == "c" * 64
            assert comparison_request["values"]["memoryAddress"] == 0x7F0220
            assert comparison_request["values"]["value"] == 0xBEEF
            assert comparison_request["values"]["operation"] == 3
            assert comparison_request["values"]["jumpOffset"] == 1
            assert page.locator(".ct-command-summary").nth(1).inner_text() == \
                "16-bit 0x7F0220 less than 48879 · false → jump +1"
            assert page.locator(".ct-hex").nth(1).inner_text() == "10 EF BE 03 01"
            assert page.locator(".ct-warning").count() == 0
            page.screenshot(path=str(ARTIFACTS / "event-editor.png"), full_page=True)

            results.append({"sceneRaster": True, "sceneL3Raster": True, "sceneRenderDiagnostics": True,
                            "worldRaster": True, "eventEditor": True, "comparisonEditor": True,
                            "errors": len(errors)})
            page.close()
        finally:
            browser.close()

    (ARTIFACTS / "results.json").write_text(
        json.dumps({"fixtureOnly": True, "results": results, "errors": errors}, indent=2), encoding="utf-8")
    assert not errors, errors
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
