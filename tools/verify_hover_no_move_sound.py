"""Pointing at something must never play the move sound (GOAL.md item 31).

The move sound belongs to actually MOVING between things. Dragging the cursor
across a tab bar or a list used to machine-gun it, so the tab bar now plays it
only for a real keyboard move. Nothing but a real pointer produces :hover and
:focus-visible, so this drives CDP input events rather than synthetic ones, and
it checks the two modalities separately: a cold pointer, and a pointer moving
after a key press, when Chromium's keyboard modality is live.
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
sys.path.insert(0, str(ROOT / "tools"))

from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402
from shot import EDGE, STUB, session_for  # noqa: E402

PLUGINS = ("blank", "ff8", "rdr2", "warband")

# Every slot is given a distinct URL so a stray sound names itself.
INSTRUMENT = """
(()=>{
  window.__sounds=[];
  const Native=window.Audio;
  window.Audio=function(url){window.__sounds.push(String(url));const audio=new Native();audio.play=()=>Promise.resolve();return audio;};
  window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',
    {detail:Object.assign({},window.__lexSettings,{soundEnabled:true,soundVolumePercent:50})}));
  LexeditorUI.configureThemeSounds(['move','confirm','back','exit','save','launch']
    .map(slot=>({slot,available:true,url:'slot:'+slot})));
  return 'ready';
})()
"""

TARGETS = """
(()=>{
  const pick=(selector,limit)=>[...document.querySelectorAll(selector)].slice(0,limit).map(node=>{
    const box=node.getBoundingClientRect();
    return {x:Math.round(box.x+box.width/2),y:Math.round(box.y+box.height/2),w:box.width,h:box.height};
  }).filter(target=>target.w>2&&target.h>2&&target.y>0&&target.y<960);
  return JSON.stringify([
    ...pick('.lex-tab-bar button, nav button, [data-tab]',12),
    ...pick('.lex-list-row, .lex-column-list-row, tbody tr',8),
    ...pick('.lex-detail-field',6),
    ...pick('header button',6)]);
})()
"""


def hover(cdp, targets):
    for target in targets:
        for step in range(3):
            cdp.call("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": target["x"] + step, "y": target["y"],
                "button": "none", "buttons": 0})
            time.sleep(.04)
        time.sleep(.1)


def check(plugin: str) -> dict:
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-sound-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-sound-project-", ignore_cleanup_errors=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    try:
        with session_for(plugin, project.name) as session:
            port = free_port()
            browser = subprocess.Popen([
                str(EDGE), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--remote-allow-origins=*", "--use-angle=swiftshader",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
            page = next(value for value in wait_json(f"http://127.0.0.1:{port}/json/list")
                        if value.get("type") == "page")
            cdp = Cdp(page["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride",
                     {"width": 1600, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": STUB})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state==='undefined'||!state.booting", 90)
            # finishPluginLoading plays the LAUNCH sound when the plugin has
            # finished opening. Instrumenting before that lands a legitimate
            # launch sound inside the hover measurement and fails this check
            # for something that is not a hover at all. Wait for the loading
            # surface to be gone before recording anything.
            wait_eval(cdp,
                      "!document.documentElement.classList.contains('lex-transition-loading')"
                      " && !document.querySelector('.lex-loading-screen')", 60)
            time.sleep(1.5)
            assert cdp.eval(INSTRUMENT) == "ready", f"{plugin}: could not instrument the sound slots"
            targets = json.loads(cdp.eval(TARGETS))
            assert targets, f"{plugin}: found nothing to hover"
            hover(cdp, targets)
            cold = json.loads(cdp.eval("JSON.stringify(window.__sounds)"))
            # A real keyboard move still plays it, which also proves the slot works.
            # Clicking a tab puts keyboard focus in the tab bar; Tab from there
            # is a real move between tabs, which is what the sound is for.
            first = targets[0]
            for kind, buttons in (("mousePressed", 1), ("mouseReleased", 0)):
                cdp.call("Input.dispatchMouseEvent", {
                    "type": kind, "x": first["x"], "y": first["y"],
                    "button": "left", "buttons": buttons, "clickCount": 1})
            time.sleep(.5)
            cdp.eval("window.__sounds=[]")
            for kind in ("rawKeyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent",
                         {"type": kind, "windowsVirtualKeyCode": 9, "key": "Tab", "code": "Tab"})
            time.sleep(.5)
            keyboard = json.loads(cdp.eval("JSON.stringify(window.__sounds)"))
            cdp.eval("window.__sounds=[]")
            hover(cdp, targets)
            warm = json.loads(cdp.eval("JSON.stringify(window.__sounds)"))
            return {"plugin": plugin, "targets": len(targets), "hoverCold": cold,
                    "keyboard": keyboard, "hoverAfterKey": warm}
    finally:
        if browser:
            browser.terminate()


def main() -> int:
    report = []
    for plugin in PLUGINS:
        result = check(plugin)
        report.append(result)
        for state in ("hoverCold", "hoverAfterKey"):
            assert "slot:move" not in result[state], (
                f"{plugin}: hovering played the move sound ({state}: {result[state]})")
            assert not result[state], f"{plugin}: hovering played {result[state]}"
    played = [row for row in report if "slot:move" in row["keyboard"]]
    assert played, "no plugin played the move sound for a keyboard move, so this check proves nothing"
    print(json.dumps(report))
    print("Hover plays no theme sound in any swept plugin; keyboard moves still do.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
