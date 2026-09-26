"""A draw point's panel and its list row show the same number.

Lexer: "also how does it say 'Draw point X' then an ID that is nowhere near X.
Where are these names coming from?"

The list names each draw point by the draw ID the game's data carries. The
panel named the record by its position in the file instead, so the heading said
"DRAW POINT 129" beside "#000". This loads the world page with a small
draw-point fixture and compares the panel's identity with the row it selected.
"""
from __future__ import annotations

import json
import re
import sys
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
        result = page.evaluate("""() => ({
          heading: document.querySelector(".lex-detail-panel-title").innerText.trim(),
          identity: document.querySelector(".lex-detail .lex-pinnable-property").innerText.replace(/\\s+/g, ""),
          row: document.querySelector(".lex-column-list-row.selected [data-column-key='drawId']").innerText.trim(),
          rowCount: document.querySelectorAll(".lex-column-list-row").length,
        })""")
        assert result["rowCount"] == 2, result
        assert result["heading"] == "DRAW POINT 129", result
        assert result["row"] == "129", result
        assert result["identity"] == "#129", result
        browser.close()
    print("Draw point panel: the heading says DRAW POINT 129, the list row says 129, "
          "and the panel's own identity says #129.")


if __name__ == "__main__":
    sys.exit(main())
