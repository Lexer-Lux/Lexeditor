"""The three user-selected King's Field covers work in the offline home menu."""
import functools
import json
from pathlib import Path
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

from core.cover_art import CoverArtCache
from core.plugin_api import validate_plugin
from plugins.kf1.plugin import PLUGIN as KF1
from plugins.kings_field2.plugin import PLUGIN as KF2
from plugins.kings_field3.plugin import PLUGIN as KF3

ROOT = Path(__file__).resolve().parents[2]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def test_kings_field_selected_covers_render_offline(tmp_path):
    plugins = {plugin.plugin_id: plugin for plugin in (KF1, KF2, KF3)}

    def unexpected_fetch(_url):
        raise AssertionError("Packaged King's Field covers must work without networking")

    cache = CoverArtCache(plugins, root=tmp_path / "cache", fetcher=unexpected_fetch, steam_roots=())
    assert not cache._threads
    for plugin in plugins.values():
        validate_plugin(plugin)
        state = cache.snapshot(plugin.plugin_id)
        assert state["state"] == "ready", state
        assert (state["width"], state["height"]) == (600, 900), state

    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    settings = json.loads((ROOT / "ui/default_settings.json").read_text(encoding="utf-8"))
    settings.update(defaultValues=dict(settings), loadingTransitionMinimumSeconds=0,
                    updateCheckChoices=[], viewPreferences={})
    cards = [{"id": plugin.plugin_id, "name": plugin.name, "status": "added", "canOpen": True,
              "coverArt": {**cache.snapshot(plugin.plugin_id),
                           "uri": base + "/" + plugin.cover_art.relative_to(ROOT).as_posix()}}
             for plugin in plugins.values()]
    stub = (f"window.pywebview={{api:new Proxy({{lexeditor_settings:async()=>({json.dumps(settings)}),"
            f"plugins:async()=>({json.dumps(cards)}),"
            "loading_quote:async()=>({quote:''}),app_update_status:async()=>({available:false}),"
            "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
            "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
            "project_info:async()=>({canCreate:false,projects:[]})},{get:(t,k)=>t[k]||(async()=>false)})};")
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1920, "height": 1080})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.add_init_script(stub)
                page.goto(base + "/ui/chooser.html")
                page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                page.wait_for_selector("#loading-screen", state="hidden")
                for plugin in plugins.values():
                    selector = f'.game[data-plugin="{plugin.plugin_id}"] .game-cover'
                    page.wait_for_function("s => document.querySelector(s)?.naturalWidth === 600", arg=selector)
                    assert page.locator(selector).is_visible()
                assert not errors, errors
                page.screenshot(path=str(tmp_path / "kings-field-home-covers.png"), full_page=True)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
