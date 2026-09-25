"""Every plugin must open: its own service, the real menu, a page that loads.

Nothing here needs the game installed. A plugin that cannot open is the one
failure a reader notices first, and it is invisible to checks that only read
source: Blank died inside the host with an UnboundLocalError, and FF7 spent two
and a half minutes decompressing files before the page could draw.

The stub host answers only what the menu asks for, so the editor frame is the
plugin's real page from its real service, reached the way the app reaches it.
A plugin whose game is absent is reported as unavailable, which is not a
failure; a plugin that opens and then throws is.
"""
from __future__ import annotations

import functools
import json
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import app  # noqa: E402
from core.desktop_host import HostApi  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

BASE_SETTINGS = json.loads((ROOT / "ui" / "default_settings.json").read_text(encoding="utf-8"))
# A crash looks like this; anything else when opening is the game's absence.
CRASHES = (AttributeError, UnboundLocalError, TypeError, KeyError, IndexError)
OPEN_TIMEOUT_SECONDS = 300


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def stub_host(plugin_id: str, url: str) -> str:
    settings = dict(BASE_SETTINGS, developerMode=False, developerAuthorized=False,
                    viewPreferences={}, defaultValues=dict(BASE_SETTINGS),
                    loadingTransitionMinimumSeconds=0.05, updateCheckChoices=[])
    opened = {"url": url, "name": plugin_id.title(), "id": plugin_id, "fonts": {}}
    games = [{"id": plugin_id, "name": plugin_id.title(), "status": "added",
              "canOpen": True, "coverArt": {"state": "none"}}]
    return ("window.pywebview={api:new Proxy({"
            f"lexeditor_settings:async()=>({json.dumps(settings)}),"
            f"plugins:async()=>({json.dumps(games)}),"
            f"open_plugin:async()=>({json.dumps(opened)}),set_dirty_count:async()=>({{}}),"
            "loading_quote:async()=>({quote:''}),app_update_status:async()=>({available:false}),"
            "window_state:async()=>({maximized:false}),game_process_status:async()=>({running:false}),"
            "theme_sounds:async()=>({rows:[]}),helper_versions:async()=>({helpers:[]}),"
            "restart_plugin:async()=>({}),project_info:async()=>({canCreate:false,projects:[]}),"
            "return_to_main_menu:async()=>({hostNavigates:true})"
            "},{get:(t,k)=>t[k]||(async()=>false)})};")


def main() -> int:
    plugins = app.discover_plugins()
    wanted = [part for part in sys.argv[1:] if not part.startswith("--")]
    if wanted:
        plugins = {key: value for key, value in plugins.items() if key in wanted}
    host = HostApi(plugins, auto_scan=False)
    rows, failures = [], []
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            for plugin_id in sorted(plugins):
                row = {"plugin": plugin_id}
                try:
                    opened = host.open_plugin(plugin_id)
                except CRASHES as error:
                    row.update(status="crashed", detail=f"{type(error).__name__}: {error}")
                    failures.append(row)
                    rows.append(row)
                    continue
                except Exception as error:  # noqa: BLE001 - an absent game, not a crash
                    row.update(status="unavailable", detail=str(error).splitlines()[0][:120])
                    rows.append(row)
                    continue
                page = browser.new_page(viewport={"width": 1500, "height": 950})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.add_init_script(stub_host(plugin_id, opened["url"]))
                started = time.time()
                try:
                    page.goto(base + "/ui/chooser.html")
                    page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                    page.wait_for_selector(".game", timeout=30000)
                    page.wait_for_selector("#loading-screen", state="hidden", timeout=30000)
                    page.evaluate('()=>window.__lexChooser.activate(document.querySelector(".game")._plugin)')
                    page.wait_for_selector("#lexeditor-editor", timeout=30000)
                    state = {}
                    for _ in range(int(OPEN_TIMEOUT_SECONDS * 2)):
                        page.wait_for_timeout(500)
                        frame = next((candidate for candidate in page.frames
                                      if candidate != page.main_frame and "127.0.0.1" in candidate.url), None)
                        if frame is None:
                            continue
                        try:
                            state = frame.evaluate("""()=>({
                              loading:!!document.querySelector('.lex-plugin-loading-screen'),
                              main:(document.querySelector('#main')?.innerText||'').trim()})""")
                        except Exception:  # noqa: BLE001 - the frame is still navigating
                            continue
                        if state.get("loading") is False and state.get("main"):
                            break
                    row["seconds"] = round(time.time() - started, 1)
                    row["main"] = (state.get("main") or "")[:60]
                    if state.get("loading") is not False or not state.get("main"):
                        row["status"] = "never finished loading"
                        row["detail"] = (f"loading={state.get('loading')} "
                                         f"main={state.get('main')!r}")
                        failures.append(row)
                    elif errors:
                        row["status"] = "threw while loading"
                        row["detail"] = errors[0][:160]
                        failures.append(row)
                    else:
                        row["status"] = "opens"
                finally:
                    page.close()
                    try:
                        host.stop()
                    except Exception:  # noqa: BLE001
                        pass
                rows.append(row)
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    for row in rows:
        print(f"{row['plugin']:>16} {row['status']:>22} "
              f"{row.get('seconds', '')!s:>6} {row.get('main', row.get('detail', ''))}")
    print(json.dumps({"plugins": len(rows), "failures": len(failures),
                      "failed": [row["plugin"] for row in failures]}, ensure_ascii=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
