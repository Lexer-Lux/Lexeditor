"""Hidden non-FF8 acceptance for the shared paged Table panel."""

from __future__ import annotations

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

from games.rdr.plugin import RdrSession  # noqa: E402
from games.warband.plugin import WarbandSession  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-46-rdr-global-table.png"
    warband_output = ROOT / "worklog" / "issues" / "rendered" / "github-46-warband-global-table.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(
        prefix="lexeditor-table-edge-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        with RdrSession() as session:
            browser = subprocess.Popen([
                str(edge), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--remote-allow-origins=*", "--use-angle=swiftshader",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile.name}", session.url,
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=hidden)
            page = next(value for value in wait_json(f"http://127.0.0.1:{port}/json/list")
                        if value.get("type") == "page")
            cdp = Cdp(page["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1400, "height": 820, "deviceScaleFactor": 1, "mobile": False,
            })
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting&&document.querySelector('.lex-paged-list-detail')", 90)
            wait_eval(cdp, "document.fonts.status==='loaded'&&document.querySelector('.lex-barrel-grid>.lex-list')", 15)
            time.sleep(.5)
            initial_fit = cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),master=root?.querySelector('.lex-barrelled-master'),list=root?.querySelector('.lex-barrel-grid>.lex-list'),header=list?.querySelector('.lex-column-list-header'),row=list?.querySelector('.lex-list-row');return{root:root?.getBoundingClientRect().height,master:master?.getBoundingClientRect().height,list:list?.getBoundingClientRect().height,scroll:list?.scrollHeight,client:list?.clientHeight,header:header?.getBoundingClientRect().height,row:row?.getBoundingClientRect().height,pageSize:state.itemPageSize,pager:root?.querySelector('.lex-pager')?.getBoundingClientRect().height};})()""")
            print({"plugin": "rdr", "initialFit": initial_fit})
            assert initial_fit["scroll"] <= initial_fit["client"] + 1, initial_fit
            before = cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),list=root.querySelector('.lex-barrel-grid>.lex-list'),rows=[...list.querySelectorAll('.lex-list-row')],last=rows.at(-1)?.getBoundingClientRect(),box=list.getBoundingClientRect(),doc=document.documentElement;return{page:state.itemPage,pageSize:state.itemPageSize,pager:!!root.querySelector('.lex-pager'),overflow:getComputedStyle(list).overflowY,scroll:list.scrollHeight,client:list.clientHeight,lastBottom:last?.bottom,listBottom:box.bottom,documentScroll:doc.scrollHeight,documentClient:doc.clientHeight};})()""")
            assert before["pager"] and before["overflow"] == "hidden", before
            assert before["scroll"] <= before["client"] + 1, before
            assert before["lastBottom"] <= before["listBottom"] + 1, before
            assert before["documentScroll"] <= before["documentClient"] + 1, before
            cdp.eval("document.querySelector('.lex-barrelled-master').dispatchEvent(new WheelEvent('wheel',{deltaY:120,bubbles:true,cancelable:true}))")
            wait_eval(cdp, f"state.itemPage==={before['page'] + 1}", 10)
            rdr_samples = []
            for _ in range(30):
                rdr_samples.append(cdp.eval("""(()=>({page:state.itemPage,pageSize:state.itemPageSize,total:document.querySelector('.lex-pager-right')?.textContent.trim(),detailScroll:document.querySelector('.lex-detail')?.scrollHeight,detailClient:document.querySelector('.lex-detail')?.clientHeight}))()"""))
                time.sleep(.04)
            assert len({(row["page"], row["pageSize"], row["total"], row["detailScroll"], row["detailClient"]) for row in rdr_samples}) == 1, rdr_samples
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(shot["data"]))
            print({"plugin": "rdr", "before": before, "afterPage": before["page"] + 1, "screenshot": str(output)})
        with WarbandSession() as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting&&state.tab==='items'&&document.querySelector('.warband-items')", 90)
            wait_eval(cdp, "document.fonts.status==='loaded'&&document.querySelector('.lex-barrel-grid>.lex-list')", 15)
            time.sleep(.5)
            before = cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),list=root.querySelector('.lex-barrel-grid>.lex-list'),rows=[...list.querySelectorAll('.lex-list-row')],last=rows.at(-1)?.getBoundingClientRect(),box=list.getBoundingClientRect(),doc=document.documentElement;return{page:state.pages.items,pageSize:state.pageSizes.items,pager:!!root.querySelector('.lex-pager'),overflow:getComputedStyle(list).overflowY,scroll:list.scrollHeight,client:list.clientHeight,lastBottom:last?.bottom,listBottom:box.bottom,documentScroll:doc.scrollHeight,documentClient:doc.clientHeight};})()""")
            assert before["pager"] and before["overflow"] == "hidden", before
            assert before["scroll"] <= before["client"] + 1, before
            assert before["lastBottom"] <= before["listBottom"] + 1, before
            assert before["documentScroll"] <= before["documentClient"] + 1, before
            cdp.eval("document.querySelector('.lex-barrelled-master').dispatchEvent(new WheelEvent('wheel',{deltaY:120,bubbles:true,cancelable:true}))")
            wait_eval(cdp, f"state.pages.items==={before['page'] + 1}", 10)
            warband_samples = []
            for _ in range(30):
                warband_samples.append(cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),master=root?.querySelector('.lex-barrelled-master'),list=root?.querySelector('.lex-barrel-grid>.lex-list'),header=list?.querySelector('.lex-column-list-header'),row=list?.querySelector('.lex-list-row');return{page:state.pages.items,pageSize:state.pageSizes.items,total:document.querySelector('.lex-page-total')?.textContent.trim(),right:document.querySelector('.lex-pager-right')?.textContent.trim(),root:root?.clientHeight,master:master?.clientHeight,list:list?.clientHeight,scroll:list?.scrollHeight,header:header?.getBoundingClientRect().height,row:row?.getBoundingClientRect().height,fit:list?.dataset.lexFittedPageSize,font:document.fonts.status};})()"""))
                time.sleep(.04)
            assert len({(row["page"], row["pageSize"], row["total"], row["right"]) for row in warband_samples}) == 1, warband_samples
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            warband_output.write_bytes(base64.b64decode(shot["data"]))
            print({"plugin": "warband", "before": before, "afterPage": before["page"] + 1,
                   "screenshot": str(warband_output)})
            for view in ("troops", "upgrades"):
                cdp.eval(f"navigate('{view}')")
                wait_eval(cdp, f"state.tab==='{view}'&&document.querySelector('.warband-paged-table')", 30)
                wait_eval(cdp, "(()=>{const list=document.querySelector('.lex-barrel-grid>.lex-list');return list&&list.scrollHeight<=list.clientHeight+1})()", 15)
                table = cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),list=root.querySelector('.lex-barrel-grid>.lex-list'),doc=document.documentElement;return{page:Number(root.dataset.lexPage),pager:!!root.querySelector('.lex-pager'),overflow:getComputedStyle(list).overflowY,scroll:list.scrollHeight,client:list.clientHeight,documentScroll:doc.scrollHeight,documentClient:doc.clientHeight};})()""")
                assert table["overflow"] == "hidden" and table["scroll"] <= table["client"] + 1, table
                assert table["documentScroll"] <= table["documentClient"] + 1, table
                if table["pager"]:
                    cdp.eval("document.querySelector('.lex-barrelled-master').dispatchEvent(new WheelEvent('wheel',{deltaY:120,bubbles:true,cancelable:true}))")
                    wait_eval(cdp, f"state.pages.{view}==={table['page'] + 1}", 10)
                print({"plugin": "warband", "view": view, **table})
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
