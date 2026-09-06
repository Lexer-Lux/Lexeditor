"""Rendered check for the DEV helper-versions panel (GOAL.md item 35).

Lexeditor helpers are pinned forks with self-updating disabled, so this panel
is the only update path there is: it reports what upstream published and never
installs anything. It belongs to Lexer Mode alone, and slides in from the right
of the main menu.
"""

from __future__ import annotations

import json
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

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

HELPERS = [
    {"pluginId": "ff8", "plugin": "Final Fantasy VIII", "helper": "FFNx",
     "pinned": "1.24.3", "latest": "1.25.0", "behind": True,
     "source": "https://github.com/julianxhokaxhiu/FFNx"},
    {"pluginId": "ff9", "plugin": "Final Fantasy IX", "helper": "Memoria",
     "pinned": "v2025.07.04", "latest": "v2025.07.04", "behind": False,
     "source": "https://github.com/Albeoris/Memoria"},
]

PLUGINS = [{
    "id": "ff8", "name": "Final Fantasy VIII", "status": "added", "canOpen": True,
    "scanInProgress": False, "root": "C:\Games\FF8", "problems": [], "statusText": "Ready",
    "resident": False, "dirtyCount": 0, "coverArt": {"state": "missing"},
    "fonts": {"total": 0, "installed": 0, "items": []},
}]

STUB = """
  window.__testSettings=SETTINGS;
  window.__helperCalls=[];
  window.pywebview={api:{
    plugins:async()=>PLUGINS,
    window_state:async()=>({maximized:false}),
    lexeditor_settings:async()=>structuredClone(window.__testSettings),
    save_lexeditor_settings:async values=>{Object.assign(window.__testSettings,values);return structuredClone(window.__testSettings)},
    helper_versions:async refresh=>{window.__helperCalls.push(!!refresh);return{helpers:HELPERS,cached:!refresh}},
    cover_art_data_uri:async id=>({uri:''})
  }};
  window.dispatchEvent(new Event('pywebviewready'));
"""

SETTINGS = {
    "developerMode": False, "developerMode": True, "developerAuthorized": True, "developerLogin": "Lexer-Lux",
    "hoverableAltClick": False, "selectionHoldMs": 650, "tableRowsPerPage": 15,
    "panelGapPercent": 1, "residentHandleWidthPercent": 5, "mainMenuHeightPercent": 9,
    "soundEnabled": False, "soundVolumePercent": 50, "absentGameDesaturationPercent": 75,
    "globalMessageRarity": 3, "loadingTransitionMinimumSeconds": 0, "viewPreferences": {},
    "updateCheckFrequency": "daily", "updateCheckChoices": [{"value": "daily", "label": "Daily"}],
    "defaultValues": {"updateCheckFrequency": "daily"},
}


def main() -> int:
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-helpers-", ignore_cleanup_errors=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    port = free_port()
    try:
        browser = subprocess.Popen([
            str(EDGE), "--headless=new", "--no-first-run", "--no-default-browser-check",
            "--remote-allow-origins=*", "--use-angle=swiftshader",
            f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
        page = next(row for row in wait_json(f"http://127.0.0.1:{port}/json/list")
                    if row.get("type") == "page")
        cdp = Cdp(page["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Emulation.setDeviceMetricsOverride",
                 {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        cdp.call("Page.navigate", {"url": (ROOT / "ui" / "chooser.html").as_uri()})
        wait_eval(cdp, "!!window.__lexChooser", 20)
        cdp.eval(STUB.replace("SETTINGS", json.dumps(SETTINGS))
                 .replace("PLUGINS", json.dumps(PLUGINS))
                 .replace("HELPERS", json.dumps(HELPERS)))
        wait_eval(cdp, "!document.querySelector('#chooser-lexer').hidden", 20)
        import base64
        closed_shot = cdp.call("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        closed_target = ROOT / "worklog" / "issues" / "rendered" / "helper-versions-button.png"
        closed_target.parent.mkdir(parents=True, exist_ok=True)
        closed_target.write_bytes(base64.b64decode(closed_shot["data"]))
        button = json.loads(cdp.eval("""JSON.stringify((()=>{const node=document.querySelector('#chooser-lexer'),
          box=node.getBoundingClientRect(),header=document.querySelector('#chooser-window-header').getBoundingClientRect();
          return {text:node.textContent,width:Math.round(box.width),height:Math.round(box.height),
            insideHeader:box.top>=header.top-1&&box.bottom<=header.bottom+1,
            clipped:node.scrollWidth>Math.ceil(box.width)+1};})())"""))
        assert button["insideHeader"], f"the button escaped the menu bar: {button}"
        assert not button["clipped"], f"the button label is cut off: {button}"
        cdp.eval("document.querySelector('#chooser-lexer').click()")
        wait_eval(cdp, "document.querySelectorAll('#lexer-panel-list .lexer-helper').length===2", 20)
        time.sleep(.4)
        opened = json.loads(cdp.eval("""JSON.stringify((()=>{const panel=document.querySelector('#lexer-panel'),
          box=panel.getBoundingClientRect(),rows=[...panel.querySelectorAll('.lexer-helper')];
          return {hidden:panel.hidden,right:Math.round(box.right),width:Math.round(box.width),
            onScreen:box.left<window.innerWidth-40,
            states:rows.map(row=>row.querySelector('.lexer-helper-state').textContent),
            behind:rows.filter(row=>row.classList.contains('behind')).length,
            text:rows.map(row=>row.textContent),
            note:panel.querySelector('.lexer-panel-note').textContent,
            calls:window.__helperCalls};})())"""))
        assert not opened["hidden"], "the panel did not open"
        assert abs(opened["right"] - 1440) <= 1, f"the panel is not on the right edge: {opened}"
        assert opened["onScreen"], f"the panel did not slide in: {opened}"
        assert opened["states"] == ["NEWER RELEASE", "UP TO DATE"], opened["states"]
        assert opened["behind"] == 1, opened
        assert "1.24.3" in opened["text"][0] and "1.25.0" in opened["text"][0], opened["text"]
        assert opened["calls"] == [False], f"opening must not force a refresh: {opened['calls']}"
        assert "self-updating disabled" in opened["note"], opened["note"]
        # Capture it open, which is the state worth looking at.
        shot = cdp.call("Page.captureScreenshot", {"format": "png", "fromSurface": True})
        target = ROOT / "worklog" / "issues" / "rendered" / "helper-versions-panel.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(shot["data"]))
        cdp.eval("document.querySelector('#lexer-panel-refresh').click()")
        wait_eval(cdp, "JSON.stringify(window.__helperCalls)==='[false,true]'", 10)
        # Nothing in this panel may install: it is a report, not an updater.
        actions = cdp.eval("""JSON.stringify([...document.querySelectorAll('#lexer-panel button')]
          .map(node=>node.textContent.trim()))""")
        assert "Install" not in actions and "Update" not in actions, actions
        cdp.eval("document.querySelector('#lexer-panel-close').click()")
        time.sleep(.4)
        assert cdp.eval("document.querySelector('#lexer-panel').hidden") is True, "close left the panel open"
        # Without Lexer Mode the button does not exist for anyone else.
        cdp.eval("""window.__testSettings.developerMode=false;
          window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:structuredClone(window.__testSettings)}))""")
        assert cdp.eval("document.querySelector('#chooser-lexer').hidden") is True, \
            "the helper panel button must belong to Lexer Mode alone"
        print(json.dumps(opened))
        print("Helper versions panel: Lexer Mode only, right-hand slide-out, report-only.")
    finally:
        if browser:
            browser.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
