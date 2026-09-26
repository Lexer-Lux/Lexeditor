"""A draw point panel names the right record and its map only opens the large map.

Lexer, on the Draw Points page:

* "also how does it say 'Draw point X' then an ID that is nowhere near X. Where
  are these names coming from?"
* "no need for a subheader here. no disclaimer text. no zoom in icon. just have
  it so when you click it, it doesn't move the point, it opens the big mode."

The list names a draw point by the draw ID the game's data carries; the panel
used its position in the file, so the heading said DRAW POINT 129 beside "#000".
The panel also drew a subheader, a paragraph, and a magnifier button, and a
click on the small map wrote new bytes into the record.

This loads the world page with a small draw-point fixture, then checks the
identity, the chrome, and both clicks: the small map opens the large one and
leaves the record alone, and a click in the large map is what moves the point.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]

DRAW_POINTS = [
    {"id": 0, "kind": "drawPoint", "drawId": 129, "x": 203, "y": 15, "subId": 20},
    {"id": 1, "kind": "drawPoint", "drawId": 130, "x": 195, "y": 17, "subId": 31},
]

WORLD = {"rows": DRAW_POINTS, "helpers": [], "regions": [], "groups": [], "segments": [],
         "drawPoints": DRAW_POINTS, "fieldReturns": [], "skyColors": [], "tracks": [],
         "textures": [], "width": 32, "height": 24, "sha256": "fixture"}

PAYLOADS = {
    "/api/dashboard": {"runtime": {"installed": False}, "baseline": {"root": "fixture"},
                       "game": {}, "themeSounds": {}},
    "/api/datamap": {"rows": []},
    "/api/editor-settings": {"showNewGame": False},
    "/api/settings": {"sections": []},
    "/api/references": {"rows": []},
    "/api/platform-config": {"sections": []},
    "/api/mods": {"rows": [], "composition": {}},
    "/api/world-map": WORLD,
}


def payload(path: str):
    base = path.split("?", 1)[0]
    if base in PAYLOADS:
        return json.loads(json.dumps(PAYLOADS[base]))
    return {"rows": []}


def serve(route, request):
    path = re.sub(r"^https?://[^/]+", "", request.url)
    base = path.split("?", 1)[0]
    if base.startswith("/api/"):
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload(path)))
        return
    if base.startswith("/shared/"):
        target = ROOT / "ui" / base.rsplit("/", 1)[-1]
    elif base.endswith((".js", ".css", ".html")):
        target = ROOT / "plugins" / "ff8" / base.lstrip("/")
    else:
        route.fulfill(status=200, content_type="image/png", body=b"")
        return
    if not target.is_file():
        route.fulfill(status=404, body="")
        return
    kind = {"js": "text/javascript", "css": "text/css", "html": "text/html"}[target.suffix[1:]]
    route.fulfill(status=200, content_type=f"{kind}; charset=utf-8",
                  body=target.read_text(encoding="utf-8"))


def stored(page) -> tuple:
    return tuple(page.evaluate(
        "() => [state.data.world.rows[0].x, state.data.world.rows[0].y, "
        "state.data.world.rows[0].subId]"))


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 950})
        page.route("**/*", serve)
        page.goto("http://ff8.fixture/editor.html")
        page.wait_for_function("() => typeof state !== 'undefined' && state.booting === false",
                               timeout=20000)
        page.evaluate("() => { state.worldTab = 'drawPoints'; navigate('world'); }")
        page.wait_for_selector(".lex-column-list-row", timeout=10000)
        page.click(".lex-column-list-row >> nth=0")
        page.wait_for_timeout(250)

        # The panel names the record the row names.
        identity = page.evaluate("""() => ({
          heading: document.querySelector(".lex-detail-panel-title").innerText.trim(),
          identity: document.querySelector(".lex-detail .lex-pinnable-property").innerText.replace(/\\s+/g, ""),
          row: document.querySelector(".lex-column-list-row.selected [data-column-key='drawId']").innerText.trim(),
          rows: document.querySelectorAll(".lex-column-list-row").length,
        })""")
        assert identity["rows"] == 2, identity
        assert identity["heading"] == "DRAW POINT 129", identity
        assert identity["row"] == "129" and identity["identity"] == "#129", identity

        # No subheader, no paragraph, no magnifier button on the panel.
        chrome = page.evaluate("""() => ({
          titles: document.querySelectorAll(".world-draw-position .lex-detail-section-title").length,
          notes: document.querySelectorAll(".world-draw-position .world-draw-help").length,
          magnifiers: document.querySelectorAll(".world-draw-point .lex-image-map-magnify").length,
          fields: document.querySelectorAll(".world-draw-position input[type=number]").length,
        })""")
        assert chrome == {"titles": 0, "notes": 0, "magnifiers": 0, "fields": 3}, chrome

        before = stored(page)
        page.click(".world-draw-map .lex-image-map-stage", position={"x": 40, "y": 40})
        page.wait_for_selector(".lex-map-magnifier-dialog", timeout=10000)
        assert stored(page) == before, ("a click on the panel's map moved the record",
                                        before, stored(page))
        note = page.locator(".lex-map-magnifier-note").inner_text()
        assert "place Draw Point 129" in note, note
        assert page.locator(".lex-map-magnifier-dialog .lex-image-map-stage").count() == 1
        shots = Path(tempfile.gettempdir()) / "lexeditor-dev"
        shots.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shots / "ff8-draw-point-map.png"))

        # The large map is where the point moves.
        stage = page.locator(".lex-map-magnifier-dialog .lex-image-map-stage")
        box = stage.bounding_box()
        page.mouse.click(box["x"] + box["width"] * 0.25, box["y"] + box["height"] * 0.25)
        page.wait_for_timeout(250)
        moved = stored(page)
        assert moved != before, ("a click on the large map did not move the record", before, moved)
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        assert page.locator(".lex-map-magnifier-dialog").count() == 0
        browser.close()
    print("Draw point panel: heading DRAW POINT 129 with identity #129 beside row 129; no subheader, "
          "paragraph, or magnifier button; a click on the panel's map opened the large map and left "
          f"the record at {before}; a click in the large map moved it to {moved}.")


if __name__ == "__main__":
    sys.exit(main())
