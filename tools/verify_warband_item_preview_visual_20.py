"""Hidden Edge render for Warband font alpha and Detail icon placement."""

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
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-warband-item-edge-", ignore_cleanup_errors=True)
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
            cdp.eval("state.selectedItem='ankle_boots';renderItems()")
            wait_eval(cdp, "document.querySelectorAll('.warband-item-detail canvas').length===2&&!document.querySelector('.warband-preview-message')", 90)
            result = cdp.eval("""(()=>{
              const heading=document.querySelector('.warband-item-detail>.lex-detail-panel-heading');
              const icon=document.querySelector('.lex-detail-panel-icon');
              const canvases=[...document.querySelectorAll('.warband-item-detail canvas')];
              const labels=[...document.querySelectorAll('nav button')].map(button=>({
                label:button.getAttribute('aria-label'),glyphs:button.querySelectorAll('.warband-glyph').length,
                bitmap:!!button.querySelector('.warband-bitmap-text')
              }));
              const rect=node=>{const r=node.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height}};
              return {heading:rect(heading),icon:rect(icon),canvases:canvases.map(rect),labels,
                title:document.querySelector('.lex-detail-panel-title')?.textContent,
                id:document.querySelector('.lex-detail-panel-id')?.textContent,
                errors:window.__testErrors};
            })()""")
            if (result["errors"] or result["title"] != "Ankle Boots" or result["id"] != "ankle_boots"):
                raise AssertionError(result)
            if result["icon"]["width"] < 24 or result["icon"]["height"] < 24:
                raise AssertionError(result)
            if len(result["canvases"]) != 2 or any(row["width"] < 24 or row["height"] < 24
                                                   for row in result["canvases"]):
                raise AssertionError(result)
            if not all(row["bitmap"] and row["glyphs"] > 0 for row in result["labels"]):
                raise AssertionError(result)
            icon, heading = result["icon"], result["heading"]
            assert icon["y"] >= heading["y"] + 8, result
            assert icon["y"] + icon["height"] <= heading["y"] + heading["height"] - 8, result
            assert cdp.eval("document.querySelector('nav [data-tab=manuals]')===null")
            badges = cdp.eval("[...document.querySelectorAll('nav button[data-tab]')].map(b=>({labels:b.querySelectorAll('.lex-tab-label-text').length,badges:b.querySelectorAll('.lex-tab-shortcut').length}))")
            assert all(b["labels"] == 1 and b["badges"] <= 1 for b in badges), badges
            assert all(b["badges"] == 1 for b in badges), badges
            badge_geometry = cdp.eval("[...document.querySelectorAll('nav .lex-tab-shortcut')].map(n=>{const a=n.getBoundingClientRect(),b=n.closest('button').getBoundingClientRect();return Math.abs((a.top+a.bottom-b.top-b.bottom)/2)})")
            assert all(delta <= 1 for delta in badge_geometry), badge_geometry
            output = ROOT / "worklog" / "issues" / "rendered" / "github-20-warband-detail-icon-font.png"
            output.parent.mkdir(parents=True, exist_ok=True)
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(shot["data"]))
            cdp.eval("navigate('dashboard')")
            assert cdp.eval("[...document.querySelectorAll('#main button')].some(n=>n.textContent==='Read installed mod manuals')")
            cdp.eval("[...document.querySelectorAll('#main button')].find(n=>n.textContent==='Read installed mod manuals').click()")
            assert cdp.eval("state.tab==='manuals'")
            print({"result": result, "screenshot": str(output), "manualsFromInfo": True, "badgeCenterDeltas": badge_geometry})

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
