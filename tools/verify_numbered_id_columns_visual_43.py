"""Hidden Edge visual and behavior proof for Lexeditor issue 43."""

from __future__ import annotations

import base64
import json
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


VIEWS = {
    "items": "Item",
    "shops": "Shop",
    "weapons": "Weapon",
    "magic": "Magic",
    "enemies": "Enemy",
}


def inspect(cdp: Cdp, width: int, height: int) -> dict:
    cdp.call("Emulation.setDeviceMetricsOverride", {
        "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
    })
    results = {}
    for view, name_label in VIEWS.items():
        cdp.eval(f"navigate('{view}')")
        wait_eval(cdp, "document.querySelectorAll('.lex-column-list-header [role=columnheader]').length>=2", 30)
        result = cdp.eval(r"""(()=>{const heads=[...document.querySelectorAll('.lex-column-list-header [role=columnheader]')],cells=[...document.querySelector('.lex-column-list-row').querySelectorAll('[role=cell]')],rows=[...document.querySelectorAll('.lex-column-list-row')],names=rows.slice(0,8).map(row=>row.querySelectorAll('[role=cell]')[1].textContent.trim()),id=cells[0].querySelector('.lex-record-id'),detail=document.querySelector('.lex-detail .lex-record-id'),title=document.querySelector('.lex-detail .lex-detail-panel-title'),color=node=>getComputedStyle(node).color,brightness=node=>(color(node).match(/[\d.]+/g)||[]).slice(0,3).reduce((sum,value)=>sum+Number(value),0);return{headers:heads.slice(0,2).map(cell=>cell.textContent.trim().replace(/[▼▲]/g,'').trim()),sort:heads.slice(0,2).map(cell=>cell.getAttribute('aria-sort')),first:cells.slice(0,2).map(cell=>cell.textContent.trim()),names,alphabetical:names.every((name,index)=>index===0||names[index-1].localeCompare(name,undefined,{numeric:true})<=0),idClass:!!id,idDarker:brightness(id)<brightness(cells[1]),idColor:color(id),nameColor:color(cells[1]),detailId:detail?.textContent.trim(),detailColor:color(detail),detailTitleColor:color(title),detailDarker:brightness(detail)<brightness(title),overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,errors:window.__testErrors}})()""")
        if result["headers"] != ["ID", name_label] or result["sort"] != ["none", "ascending"]:
            raise AssertionError({view: result})
        if not result["first"][0].startswith("#") or not result["first"][0][1:].isdigit() or not result["alphabetical"]:
            raise AssertionError({view: result})
        if (not result["idClass"] or not result["idDarker"] or
                result["detailId"] != result["first"][0] or not result["detailDarker"]):
            raise AssertionError({view: result})
        if result["overflow"] > 0 or result["errors"]:
            raise AssertionError({view: result})
        results[view] = result
    probe = cdp.eval("""(()=>{const read=node=>[...node.querySelectorAll('.lex-column-list-head-cell')].map(cell=>cell.textContent.trim()),values=node=>[...node.querySelectorAll('.lex-column-list-row [role=cell]')].map(cell=>cell.textContent.trim());const columns=[{key:'name',label:'Name',sortable:true},{key:'id',label:'ID',sortable:true}],numeric=LexeditorUI.columnList({rows:[{id:2,name:'Alpha'}],columns,sortState:{key:'name',dir:1}}),technical=LexeditorUI.columnList({rows:[{id:'itm_alpha',name:'Alpha'}],columns,sortState:{key:'name',dir:1}});return{numeric:read(numeric),numericValues:values(numeric),numericIds:numeric.querySelectorAll('.lex-record-id').length,technical:read(technical),technicalValues:values(technical),technicalIds:technical.querySelectorAll('.lex-record-id').length}})()""")
    if (probe["numeric"] != ["ID", "▲Name"] or probe["numericValues"] != ["#2", "Alpha"] or probe["numericIds"] != 1
            or probe["technical"] != ["▲Name", "ID"] or probe["technicalValues"] != ["Alpha", "itm_alpha"] or probe["technicalIds"] != 0):
        raise AssertionError(probe)
    cdp.eval("navigate('items')")
    output = ROOT / "worklog" / "issues" / "rendered" / f"github-43-numbered-id-{width}x{height}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    screenshot = cdp.call("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": False, "fromSurface": True,
    })
    output.write_bytes(base64.b64decode(screenshot["data"]))
    return {"size": [width, height], "views": results, "sharedProbe": probe}


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-numbered-id-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-numbered-id-project-", ignore_cleanup_errors=True)
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
            print(json.dumps([inspect(cdp, 1280, 720), inspect(cdp, 1600, 900)], ensure_ascii=True))
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
