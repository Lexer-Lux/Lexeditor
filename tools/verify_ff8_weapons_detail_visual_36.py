"""Hidden Edge geometry check for the FF8 Weapons detail pane (GitHub #36)."""

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


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-36-ff8-weapons-detail.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-weapons-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-weapons-project-", ignore_cleanup_errors=True)
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            browser = subprocess.Popen([
                str(edge), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--remote-allow-origins=*", "--use-angle=swiftshader",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
            pages = wait_json(f"http://127.0.0.1:{port}/json/list")
            page = next(value for value in pages if value.get("type") == "page")
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
            cdp.eval("navigate('weapons')")
            wait_eval(cdp, "state.tab==='weapons'&&!!document.querySelector('.weapon-detail')", 30)
            wait_eval(cdp, "document.querySelector('.weapon-detail')?.clientHeight>400", 30)
            result = cdp.eval("""(()=>{
              const detail=document.querySelector('.weapon-detail');
              const data=document.querySelector('.weapon-data');
              const ingredients=document.querySelector('.weapon-cost');
              const detailRect=detail.getBoundingClientRect();
              const dataRect=data.getBoundingClientRect();
              const ingredientsRect=ingredients.getBoundingClientRect();
              const before=detail.scrollTop;
              detail.dispatchEvent(new WheelEvent('wheel',{deltaY:240,bubbles:true,cancelable:true}));
              return {
                details:detail.querySelectorAll('details').length,
                order:dataRect.top<ingredientsRect.top,
                overflowY:getComputedStyle(detail).overflowY,
                scrollHeight:detail.scrollHeight,clientHeight:detail.clientHeight,
                contentFits:ingredientsRect.bottom<=detailRect.bottom+1,
                scrollStable:detail.scrollTop===before,
                dataFields:detail.querySelectorAll('.weapon-data-field').length,
                costLabel:ingredients.querySelector(':scope>.lex-detail-section-title')?.textContent,
                priceInputs:ingredients.querySelectorAll('.weapon-cost-price input').length,
                ingredientRows:detail.querySelectorAll('.weapon-ingredient-row').length,
                typedControls:detail.querySelectorAll('input[inputmode="decimal"],input[inputmode="numeric"],input[type="checkbox"],select').length,
                sourceControls:detail.querySelectorAll('.lex-source-control').length,
                overflowing:[...detail.querySelectorAll('*')].map(node=>({tag:node.tagName,cls:node.className||'',text:(node.textContent||'').trim().slice(0,50),bottom:node.getBoundingClientRect().bottom})).filter(value=>value.bottom>detailRect.bottom+1).slice(0,20),
                errors:window.__testErrors,
                bounds:{detail:[detailRect.top,detailRect.bottom],data:[dataRect.top,dataRect.bottom],ingredients:[ingredientsRect.top,ingredientsRect.bottom]},
              };
            })()""")
            assert result["details"] == 0, result
            assert result["order"], result
            assert result["overflowY"] not in {"auto", "scroll"}, result
            assert result["scrollHeight"] <= result["clientHeight"] + 1, result
            assert result["contentFits"] and result["scrollStable"], result
            assert result["dataFields"] == 10 and result["ingredientRows"] == 4, result
            assert result["costLabel"] == "COST" and result["priceInputs"] == 1, result
            assert result["typedControls"] >= 14 and result["sourceControls"] >= 14, result
            assert not result["errors"], result
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print(result)
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
