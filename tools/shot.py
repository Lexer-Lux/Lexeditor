"""Screenshot any Lexeditor plugin screen in headless Edge.

Usage:
    python tools/shot.py <plugin> <name> [--step "<js>"]... [--size WxH]

Each --step runs in the page and is awaited for 400ms before the next one.
The PNG lands in _scratch/shots/<name>.png.
"""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402
import browser_guard  # noqa: E402

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
SHOTS = ROOT / "_scratch" / "shots"

STUB = """
  window.__testErrors=[];
  addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
  addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
  window.pywebview={api:{
    mod_projects:async()=>({canCreate:true,projects:[{name:'Test Mod',path:'Rendered test project',valid:true,current:true}]}),
    set_dirty_count:async()=>null,
    game_process_status:async()=>null,
    lexeditor_settings:async()=>window.__lexSettings,
    save_lexeditor_settings:async v=>Object.assign(window.__lexSettings,v),
    save_developer_setting_defaults:async v=>Object.assign(window.__lexSettings.defaultValues,v),
    save_lexeditor_view_preference:async()=>window.__lexSettings,
    clear_lexeditor_view_preference:async()=>window.__lexSettings
  }};
  window.__lexSettings={updateCheckFrequency:'monthly',developerMode:true,developerMode:true,
    lexerAuthorized:false,lexerLogin:'',hoverableAltClick:false,selectionHoldMs:500,
    tableRowsPerPage:40,panelGapPercent:.5,residentHandleWidthPercent:5,mainMenuHeightPercent:7,
    soundEnabled:false,soundVolumePercent:25,absentGameDesaturationPercent:75,
    globalMessageRarity:3,loadingTransitionMinimumSeconds:0,viewPreferences:{},
    updateCheckChoices:[{value:'monthly',label:'Monthly'}],
    defaultValues:{updateCheckFrequency:'monthly',developerMode:false,hoverableAltClick:false,
      selectionHoldMs:500,tableRowsPerPage:40,panelGapPercent:.5,residentHandleWidthPercent:5,
      mainMenuHeightPercent:7,soundEnabled:false,soundVolumePercent:25,
      absentGameDesaturationPercent:75,globalMessageRarity:3,loadingTransitionMinimumSeconds:0},
    helpers:[]};
"""


def session_for(plugin_id: str, project: str):
    """Return the plugin's own session class, not the shared base class."""
    module = __import__(f"games.{plugin_id}.plugin", fromlist=["PLUGIN"])
    from service_session import LocalPluginSession
    candidates = [getattr(module, name) for name in dir(module)]
    session_class = next(
        (value for value in candidates
         if isinstance(value, type) and issubclass(value, LocalPluginSession)
         and value is not LocalPluginSession),
        None)
    if session_class is None:
        raise SystemExit(f"no session class in games/{plugin_id}/plugin.py")
    variable = {
        "ff8": "LEXEDITOR_FF8_PROJECT", "ff7": "LEXEDITOR_FF7_PROJECT",
        "ff9": "LEXEDITOR_FF9_PROJECT", "rdr2": "LEXEDITOR_RDR2_PROJECT",
        "rdr": "LEXEDITOR_RDR_PROJECT", "warband": "LEXEDITOR_WARBAND_PROJECT",
    }.get(plugin_id)
    try:
        return session_class({variable: project} if variable else {})
    except TypeError:
        return session_class()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin")
    parser.add_argument("name")
    parser.add_argument("--step", action="append", default=[])
    parser.add_argument("--size", default="1600x1000")
    parser.add_argument("--eval", dest="expression")
    parser.add_argument("--live", action="store_true",
                        help="use the real project instead of a temporary one")
    args = parser.parse_args()
    width, height = (int(part) for part in args.size.lower().split("x"))

    profile = tempfile.TemporaryDirectory(prefix="lexeditor-shot-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-shot-project-")
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    try:
        with session_for(args.plugin, project.name) as session:
            port = free_port()
            browser = subprocess.Popen([
                str(EDGE), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--remote-allow-origins=*", "--use-angle=swiftshader",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
            # The kernel kills this browser tree when this process dies, however
            # it dies. terminate() alone orphaned every child renderer, and a
            # `finally` never runs under `timeout`, so both leaked browsers.
            browser_guard.adopt(browser)
            page = next(value for value in wait_json(f"http://127.0.0.1:{port}/json/list")
                        if value.get("type") == "page")
            cdp = Cdp(page["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": STUB})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state==='undefined'||!state.booting", 90)
            time.sleep(1.2)
            for step in args.step:
                cdp.eval(step)
                time.sleep(.45)
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            SHOTS.mkdir(parents=True, exist_ok=True)
            target = SHOTS / f"{args.name}.png"
            target.write_bytes(base64.b64decode(shot["data"]))
            if args.expression:
                value = str(cdp.eval(args.expression))
                # The console is cp1252 here; page text often is not.
                data = value.encode('utf-8', 'backslashreplace')
                sys.stdout.buffer.write(data + bytes([10]))
                sys.stdout.flush()
            errors = cdp.eval("JSON.stringify(window.__testErrors||[])")
            print(target)
            if errors and errors != "[]":
                print(f"page errors: {errors}")
    finally:
        browser_guard.kill_tree(browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
