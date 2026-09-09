"""Fixture-only browser check for Chrono Trigger desktop raster map surfaces."""
from __future__ import annotations

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
    "layerPriorities": [0, 1, 2],
    "layers": {
        "layer1": {"width": 16, "height": 16, "tiles": [1] * 256},
        "layer2": {"width": 16, "height": 16, "tiles": [2] * 256},
        "layer3": {"enabled": False, "width": 0, "height": 0, "tiles": []},
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
        "values": {"musicIndex": 10, "tilesetL12": 1, "tilesetL12Assembly": 2, "palette": 3, "mapIndex": 0},
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
                elif path in {"/api/scene-raster", "/api/world-raster"}:
                    route.fulfill(status=200, content_type="image/png", body=PNG)
                else:
                    route.fulfill(status=404, content_type="application/json", body=json.dumps({"error": path}))

            page.route(f"{ORIGIN}/**", handle)
            page.goto(ORIGIN + "/", wait_until="domcontentloaded")
            page.wait_for_function('state.scenes.data?.rows?.length === 1')

            page.locator(".ct-section-tabs").get_by_role("button", name="Map", exact=True).click()
            page.wait_for_function('state.scenes.map?.sceneWidth === 16')
            scene_select = page.locator(".ct-map-panel select")
            scene_select.select_option("raster1")
            page.wait_for_function('document.querySelector(".ct-raster-image")?.naturalWidth > 0')
            assert "/api/scene-raster" in page.locator(".ct-raster-image").get_attribute("src")
            assert "isolated layer only" in page.locator(".ct-raster-policy").inner_text()
            assert page.locator(".ct-warning").count() == 0
            page.screenshot(path=str(ARTIFACTS / "scene-raster.png"), full_page=True)

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

            results.append({"sceneRaster": True, "worldRaster": True, "errors": len(errors)})
            page.close()
        finally:
            browser.close()

    (ARTIFACTS / "results.json").write_text(
        json.dumps({"fixtureOnly": True, "results": results, "errors": errors}, indent=2), encoding="utf-8")
    assert not errors, errors
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
