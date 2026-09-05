"""Hidden rendered check for the FF8 Starting Data page (GitHub #21)."""

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


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-21-ff8-starting-data.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-init-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-init-project-", ignore_cleanup_errors=True)
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
            cdp.eval("navigate('starting')")
            debug = cdp.eval("(()=>({tab:state.tab,view:!!document.querySelector('.starting-view'),errors:window.__testErrors,body:document.body.innerText.slice(-800)}))()")
            if debug["errors"] or not debug["view"]:
                raise AssertionError(debug)
            wait_eval(cdp, "state.tab==='starting'&&!!document.querySelector('.starting-view')", 20)
            general = cdp.eval("""(() => ({
              tabs:[...document.querySelectorAll('#toolbar button')].map((node=>[...node.childNodes].filter(part=>!(part.nodeType===1&&part.classList.contains('lex-tab-shortcut'))).map(part=>part.textContent).join('').trim())),
              sections:[...document.querySelectorAll('.starting-view .lex-detail-section-title')].map(node=>node.textContent.trim()),
              fields:document.querySelectorAll('.starting-field-grid .lex-detail-field').length,
              errors:window.__testErrors,
            }))()""")
            assert general["tabs"] == ["General", "Characters", "GFs", "Inventory"], general
            assert general["sections"] == ["PARTY AND PROGRESS", "CONFIG"], general
            assert general["fields"] == 35 and not general["errors"], general

            edit = cdp.eval("""(() => {
              const field=state.data.init.general.fields.find(value=>value.field==='gil');
              const owner=[...document.querySelectorAll('.starting-field-grid .lex-detail-field')]
                .find(node=>node.textContent.toUpperCase().includes('STARTING GIL'));
              const input=owner.querySelector('input');
              const next=field.value===123456?123455:123456;
              input.value=String(next);input.dispatchEvent(new Event('input',{bubbles:true}));
              return {next,current:field.value};
            })()""")
            assert int(edit["current"]) == int(edit["next"]), edit
            wait_eval(cdp, "dirtyCount()>0", 10)
            cdp.eval("saveAll()", True)
            wait_eval(cdp, "dirtyCount()===0", 20)
            saved = cdp.eval("state.data.init.general.fields.find(value=>value.field==='gil').value")
            assert int(saved) == int(edit["next"]), (saved, edit)

            cdp.eval("state.startingTab='characters';renderStartingData()")
            wait_eval(cdp, "document.querySelectorAll('.starting-magic-table .lex-column-list-row').length===12", 10)
            characters = cdp.eval("""(() => ({
              picker:document.querySelector('.starting-record-picker select').options.length,
              rows:document.querySelectorAll('.starting-magic-table .lex-column-list-row').length,
              pageTotal:document.querySelector('.lex-page-total').textContent,
              fields:document.querySelectorAll('.starting-field-grid .lex-detail-field').length,
              errors:window.__testErrors,
            }))()""")
            assert characters["picker"] == 8 and characters["rows"] == 12
            assert characters["pageTotal"] == "3" and characters["fields"] > 50
            assert not characters["errors"], characters

            cdp.eval("state.startingTab='gfs';renderStartingData()")
            gfs = cdp.eval("""(() => ({
              picker:document.querySelector('.starting-record-picker select').options.length,
              fields:document.querySelectorAll('.starting-field-grid .lex-detail-field').length,
              errors:window.__testErrors,
            }))()""")
            assert gfs == {"picker": 16, "fields": 6, "errors": []}, gfs

            cdp.eval("state.startingTab='inventory';renderStartingData()")
            wait_eval(cdp, "document.querySelectorAll('.starting-inventory-table .lex-column-list-row').length===15", 10)
            inventory = cdp.eval("""(() => ({
              rows:document.querySelectorAll('.starting-inventory-table .lex-column-list-row').length,
              pageTotal:document.querySelector('.lex-page-total').textContent,
              selects:document.querySelectorAll('.starting-inventory-table select').length,
              errors:window.__testErrors,
            }))()""")
            assert inventory == {"rows": 15, "pageTotal": "14", "selects": 15, "errors": []}, inventory
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print(json.dumps({"general": general, "characters": characters,
                              "gfs": gfs, "inventory": inventory}, ensure_ascii=True))
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
