"""Hidden Edge display and save proof for FF8 GF Compatibility (GitHub #32)."""

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
from service_session import request_json  # noqa: E402


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-32-ff8-gf-signed-compatibility.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-gf-compat-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-gf-compat-project-", ignore_cleanup_errors=True)
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
            cdp.eval("navigate('gfs')")
            wait_eval(cdp, "state.tab==='gfs'&&document.querySelectorAll('.gf-panel.compatibility .gf-compat-input').length===16", 30)
            before = cdp.eval(r"""(()=>{const inputs=[...document.querySelectorAll('.gf-panel.compatibility .gf-compat-input')];return{types:[...new Set(inputs.map(input=>input.type))],signed:inputs.every(input=>/^[-+]?\d+(?:\.\d+)?$/.test(input.value)),editableTable:document.querySelector('.gf-panel.compatibility .lex-editable-table')!==null,sortable:document.querySelectorAll('.gf-panel.compatibility .lex-column-sort').length,detachedSigns:document.querySelectorAll('.gf-compat-sign').length,vanilla:[...document.querySelectorAll('.gf-panel.compatibility .lex-source-strip button')].slice(0,2).map(button=>button.textContent.trim()),errors:window.__testErrors}})()""")
            assert before["types"] == ["text"] and before["signed"] and before["editableTable"], before
            assert before["sortable"] == 2 and before["detachedSigns"] == 0, before
            assert before["vanilla"] == [], before
            changed = cdp.eval("""(()=>{const inputs=[...document.querySelectorAll('.gf-panel.compatibility .gf-compat-input')],fields=state.data.gfs.rows.find(row=>row.id===state.selected.gfs).fields.filter(field=>field.formula==='gf_compat').sort((a,b)=>a.label.localeCompare(b.label,undefined,{sensitivity:'base'}));inputs[0].value='+0.5';inputs[0].dispatchEvent(new Event('input',{bubbles:true}));inputs[1].value='-1';inputs[1].dispatchEvent(new Event('input',{bubbles:true}));return{id:state.selected.gfs,labels:fields.slice(0,2).map(field=>field.label),values:inputs.slice(0,2).map(input=>input.value),stored:fields.slice(0,2).map(field=>field.value)}})()""")
            assert changed["values"] == ["+0.5", "-1"] and changed["stored"] == [105, 90], changed
            cdp.eval("saveAll()", True)
            reread = request_json(session.url + "api/kernel?section=3")["rows"][changed["id"]]
            stored_by_label = {field["label"]: field["value"] for field in reread["fields"] if field.get("formula") == "gf_compat"}
            stored = [stored_by_label[label] for label in changed["labels"]]
            assert stored == [105, 90], stored
            after = cdp.eval("""(()=>{const buttons=[...document.querySelectorAll('.gf-panel.compatibility .lex-source-strip button')].slice(0,2),button=buttons[0],strip=button?.closest('.lex-source-strip'),control=button?.closest('.lex-source-control'),br=strip?.getBoundingClientRect(),cr=control?.getBoundingClientRect();return{values:[...document.querySelectorAll('.gf-panel.compatibility .gf-compat-input')].slice(0,2).map(input=>input.value),detachedSigns:document.querySelectorAll('.gf-compat-sign').length,sources:buttons.map(value=>value.textContent.trim()),geometry:button&&control?{attached:br.bottom>=cr.top-2&&br.top<=cr.bottom+2,fontSize:parseFloat(getComputedStyle(button).fontSize)}:null,errors:window.__testErrors}})()""")
            assert after["values"] == ["+0.5", "-1"] and after["detachedSigns"] == 0, after
            assert after["sources"] and all(source.startswith("V") and "VANILLA" not in source for source in after["sources"]), after
            assert after["geometry"] and after["geometry"]["attached"] and after["geometry"]["fontSize"] >= 12, after
            assert not after["errors"], after
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print({"before": before, "changed": changed, "savedBytes": stored, "after": after})
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
