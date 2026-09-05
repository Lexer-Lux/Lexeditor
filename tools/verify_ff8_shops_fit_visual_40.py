"""Hidden Edge geometry check for FF8 Shops (GitHub #40)."""

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
    output_dir = ROOT / "worklog" / "issues" / "rendered"
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-shops-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-shops-project-", ignore_cleanup_errors=True)
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
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            for width, height in ((1280, 720), (1600, 900)):
                cdp.call("Emulation.setDeviceMetricsOverride", {
                    "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
                })
                cdp.call("Page.navigate", {"url": session.url})
                wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
                cdp.eval("navigate('shops')")
                wait_eval(cdp, "state.tab==='shops'&&!!document.querySelector('.shop-detail')", 30)
                result = cdp.eval("""(()=>{
                  const detail=document.querySelector('.shop-detail');
                  const table=detail.querySelector('.ff8-shop-table');
                  const rows=[...table.querySelectorAll('.lex-column-list-row')];
                  const rect=detail.getBoundingClientRect();
                  const before=detail.scrollTop;
                  const help=detail.querySelector('.lex-info-help'),helpBox=help.getBoundingClientRect(),helpStyle=getComputedStyle(help);
                  detail.dispatchEvent(new WheelEvent('wheel',{deltaY:300,bubbles:true,cancelable:true}));
                  return {
                    rows:rows.length,
                    searchers:detail.querySelectorAll('.ff8-item-search').length,
                    obsoleteSelectors:detail.querySelectorAll('select').length,
                    rare:detail.querySelectorAll('input[type="checkbox"]').length,
                    slotClear:detail.querySelectorAll('.shop-slot-clear').length,
                    columns:detail.querySelectorAll('.lex-column-list-head-cell').length,
                    sources:detail.querySelectorAll('.lex-source-strip').length,
                    sortable:detail.querySelectorAll('.lex-column-list-head-cell button').length,
                    overflowY:getComputedStyle(detail).overflowY,
                    scrollHeight:detail.scrollHeight,clientHeight:detail.clientHeight,
                    allVisible:rows.every(row=>row.getBoundingClientRect().bottom<=rect.bottom+1),
                    separators:{before:getComputedStyle(rows.at(-2)).borderBottomWidth,last:getComputedStyle(rows.at(-1)).borderBottomWidth},
                    scrollStable:detail.scrollTop===before,
                    help:{text:help.textContent,title:help.title,aria:help.getAttribute('aria-label'),width:helpBox.width,height:helpBox.height,radius:helpStyle.borderRadius,fill:helpStyle.backgroundColor,border:helpStyle.borderTopWidth},
                    geometry:{detail:[rect.top,rect.bottom],head:detail.querySelector('.lex-detail-panel-heading').getBoundingClientRect().height,table:table.getBoundingClientRect().height,row:rows[0].getBoundingClientRect().height,cells:[...rows[0].children].map(cell=>({height:cell.getBoundingClientRect().height,scroll:cell.scrollHeight,line:getComputedStyle(cell).lineHeight,padding:[getComputedStyle(cell).paddingTop,getComputedStyle(cell).paddingBottom]})),search:detail.querySelector('.ff8-item-search').getBoundingClientRect().height,slot:detail.querySelector('.shop-slot-clear').getBoundingClientRect().height},
                    errors:window.__testErrors,
                  };
                })()""")
                assert result["rows"] == 16, result
                assert result["searchers"] == 16 and result["obsoleteSelectors"] == 0, result
                assert result["rare"] == 16 and result["slotClear"] == 16, result
                assert result["columns"] == 3, result
                assert result["sources"] == 32, result
                assert result["sortable"] >= 3, result
                assert result["geometry"]["row"] >= result["geometry"]["slot"], result
                assert all(cell["scroll"] <= result["geometry"]["row"] + 1 for cell in result["geometry"]["cells"]), result
                assert result["overflowY"] == "hidden", result
                assert result["scrollHeight"] <= result["clientHeight"] + 1, result
                assert result["allVisible"] and result["scrollStable"], result
                assert result["separators"] == {"before": "1px", "last": "0px"}, result
                assert result["help"]["text"] == "?" and not result["help"]["title"] and result["help"]["aria"], result
                assert result["help"]["width"] == result["help"]["height"] == 18, result
                assert result["help"]["radius"] == "50%" and result["help"]["border"] == "0px", result
                assert result["help"]["fill"] not in ("transparent", "rgba(0, 0, 0, 0)"), result
                assert not result["errors"], result
                screenshot = cdp.call("Page.captureScreenshot", {
                    "format": "png", "captureBeyondViewport": False, "fromSurface": True,
                })
                (output_dir / f"github-40-ff8-shops-{width}x{height}.png").write_bytes(
                    base64.b64decode(screenshot["data"]))
                print(width, height, result)
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
