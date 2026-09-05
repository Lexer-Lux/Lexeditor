"""Hidden Edge proof for Warband hoverable troop relationships."""

from __future__ import annotations

import base64
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.warband.plugin import WarbandSession  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-warband-hover-edge-", ignore_cleanup_errors=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    try:
        with WarbandSession() as session:
            port = free_port()
            browser = subprocess.Popen([
                str(edge), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--remote-allow-origins=*", "--use-angle=swiftshader",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
            page = next(value for value in wait_json(f"http://127.0.0.1:{port}/json/list")
                        if value.get("type") == "page")
            cdp = Cdp(page["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('upgrades')")
            wait_eval(cdp, "state.tab==='upgrades'", 30)
            diagnosis = cdp.eval("({errors:window.__testErrors,html:document.querySelector('#main').textContent.slice(0,300),upgrade:state.upgrades.rows[0],troops:state.troops.rows.length,matched:state.upgrades.rows.filter(u=>state.troops.rows.some(t=>t.id===u.fromId)&&state.troops.rows.some(t=>t.id===u.toId)).length,hoverableType:typeof hoverable,cell:document.querySelector('.lex-column-list-cell')?.outerHTML})")
            if diagnosis["errors"] or not diagnosis.get("upgrade"):
                raise AssertionError(diagnosis)
            wait_eval(cdp, "!!document.querySelector('.lex-hoverable')", 30)
            cdp.eval("window.__lexLastTop=null;window.__lexStable=0")
            wait_eval(cdp, "(()=>{const node=document.querySelector('.lex-hoverable');"
                            "if(!node)return false;const top=Math.round(node.getBoundingClientRect().top);"
                            "window.__lexStable=top===window.__lexLastTop?window.__lexStable+1:0;"
                            "window.__lexLastTop=top;return window.__lexStable>=3})()", 30)
            before = cdp.eval("""(()=>{const n=document.querySelector('.lex-hoverable'),r=n.getBoundingClientRect();return{id:n.dataset.hoverTargetId,type:n.dataset.hoverTargetType,x:r.x+r.width/2,y:r.y+r.height/2,color:getComputedStyle(n).color,errors:window.__testErrors}})()""")
            if before["type"] != "warband-troop":
                raise AssertionError(before)
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": before["x"], "y": before["y"]})
            hovered = cdp.eval("(()=>{const style=getComputedStyle(document.querySelector('.lex-hoverable'));return{color:style.color,decoration:style.textDecorationLine}})()")
            if before["errors"] or hovered["decoration"] != "underline":
                raise AssertionError({"before": before, "hovered": hovered})
            output = ROOT / "worklog" / "issues" / "rendered" / "github-45-warband-upgrade-hoverable.png"
            output.parent.mkdir(parents=True, exist_ok=True)
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(shot["data"]))
            cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": before["x"], "y": before["y"], "button": "left", "clickCount": 1})
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": before["x"], "y": before["y"], "button": "left", "clickCount": 1})
            wait_eval(cdp, f"state.tab==='troops'&&state.selectedTroop==={before['id']!r}", 30)
            result = cdp.eval("""(()=>{const selected=document.querySelector('.lex-column-list-row.selected');return{tab:state.tab,selected:state.selectedTroop,row:selected?.textContent||'',visible:!!selected,errors:window.__testErrors}})()""")
            if not result["visible"] or before["id"] not in result["row"] or result["errors"]:
                raise AssertionError(result)
            print({"target": before["id"], "hoverBorder": hovered, "destination": result, "screenshot": str(output)})
        return 0
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        profile.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
