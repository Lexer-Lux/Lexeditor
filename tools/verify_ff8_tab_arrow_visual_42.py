"""Hidden Edge rendered proof for Lexeditor issue 42."""

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

from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def inspect(cdp: Cdp, width: int, height: int) -> dict:
    cdp.call("Emulation.setDeviceMetricsOverride", {
        "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
    })
    cdp.eval("navigate('shops')")
    wait_eval(cdp, "state.tab==='shops'&&document.querySelector('nav button[data-tab=\"shops\"]')?.classList.contains('active')", 30)
    result = cdp.eval("""(()=>{const button=document.querySelector('nav button[data-tab=shops].active'),label=button.querySelector('.lex-tab-label'),style=getComputedStyle(button),oldArrow=getComputedStyle(button,'::before'),arrow=getComputedStyle(label,'::before'),box=button.getBoundingClientRect(),labelBox=label.getBoundingClientRect();return{display:style.display,align:style.alignItems,justify:style.justifyContent,button:{x:box.x,y:box.y,w:box.width,h:box.height},label:{x:labelBox.x,y:labelBox.y,w:labelBox.width,h:labelBox.height,centerDelta:Math.abs((labelBox.left+labelBox.width/2)-(box.left+box.width/2))},oldContent:oldArrow.content,arrow:{content:arrow.content,position:arrow.position,width:arrow.width,height:arrow.height,right:arrow.right,gap:parseFloat(arrow.right)-labelBox.width,background:arrow.backgroundImage,imageRendering:arrow.imageRendering,pointerEvents:arrow.pointerEvents},overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,errors:window.__testErrors}})()""")
    expected = {"display": "flex", "align": "center", "justify": "center"}
    if any(result[key] != value for key, value in expected.items()):
        raise AssertionError(result)
    arrow = result["arrow"]
    if result["oldContent"] != "none" or arrow["width"] != "32px" or arrow["height"] != "22px":
        raise AssertionError(result)
    if arrow["position"] != "absolute" or arrow["pointerEvents"] != "none":
        raise AssertionError(result)
    if abs(arrow["gap"] - 10) > 0.1 or result["label"]["centerDelta"] > 0.5:
        raise AssertionError(result)
    if "/assets/icons/0.png" not in arrow["background"]:
        raise AssertionError(result)
    if arrow["imageRendering"] != "pixelated":
        raise AssertionError(result)
    if result["overflow"] > 0 or result["errors"]:
        raise AssertionError(result)
    output = ROOT / "worklog" / "issues" / "rendered" / f"github-42-ff8-tab-arrow-{width}x{height}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    screenshot = cdp.call("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": False, "fromSurface": True,
    })
    output.write_bytes(base64.b64decode(screenshot["data"]))
    return result


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-arrow-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-arrow-project-", ignore_cleanup_errors=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
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
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            print([inspect(cdp, 1280, 720), inspect(cdp, 1600, 900)])
        return 0
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        project.cleanup()
        profile.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
