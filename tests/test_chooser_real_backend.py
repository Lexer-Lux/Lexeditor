"""G2-REDO: the main menu renders the real backend's data without errors.

The stubbed two-card check passed while the real menu was reported black,
so this drives the real chooser page with real HostApi payloads: every
discovered plugin row, real settings, and the real loading quote. Ready
in-repo cover art must paint real pixels; anything else must degrade to a
legible fallback; the loading screen must lift; no error dialog may appear.
Network-only calls (update check, helper versions) stay stubbed: they do
not affect the menu render.
"""
import functools
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import discover_plugins
from desktop_host import HostApi


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_): pass


def test_menu_renders_real_backend_data():
    plugins = discover_plugins()
    api = HostApi(plugins, enforce_installations=True, auto_scan=False)
    try:
        settings = api.lexeditor_settings()
        rows = api.plugins()
        quote = api.loading_quote("__home__")
    finally:
        api.dispose()
    assert rows, "the real backend reports no plugins"
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        # Covers that live in the repo are reachable over the fixture server;
        # anything else keeps its URI and must degrade to a fallback.
        for row in rows:
            uri = (row.get("coverArt") or {}).get("uri") or ""
            if uri.startswith("file:///"):
                path = Path(uri[8:])
                try:
                    row["coverArt"]["uri"] = base + "/" + path.relative_to(ROOT).as_posix()
                except ValueError:
                    pass
        stub = (f"window.pywebview={{api:new Proxy({{lexeditor_settings:async()=>({json.dumps(settings)}),"
                f"plugins:async()=>({json.dumps(rows)}),"
                f"loading_quote:async()=>({json.dumps(quote)}),"
                "app_update_status:async()=>({available:false}),"
                "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
                "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
                "project_info:async()=>({canCreate:false,projects:[]})},{get:(t,k)=>t[k]||(async()=>false)})};")
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1920, "height": 1080})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.add_init_script(stub)
                page.goto(base + "/ui/chooser.html")
                page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                page.wait_for_selector(".game", timeout=15000)
                page.wait_for_selector("#loading-screen", state="hidden", timeout=20000)
                assert not errors, errors
                assert page.locator("#modal").is_hidden()
                rendered = page.locator(".game").evaluate_all(
                    "nodes=>nodes.map(n=>n.dataset.plugin)")
                assert rendered == [row["id"] for row in rows]
                for row in rows:
                    card = page.locator(f'.game[data-plugin="{row["id"]}"]')
                    cover = card.locator(".game-cover")
                    if (row.get("coverArt") or {}).get("uri", "").startswith(base):
                        page.wait_for_function(
                            f"document.querySelector('.game[data-plugin=\"{row['id']}\"] .game-cover')"
                            ".naturalWidth > 0",
                            timeout=8000)
                        box = cover.bounding_box()
                        assert box["width"] > 100 and box["height"] > 100, (row["id"], box)
                    else:
                        assert card.locator(".cover-fallback").inner_text().strip(), row["id"]
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
