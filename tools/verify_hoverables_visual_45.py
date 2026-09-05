"""Hidden Edge acceptance check for FF8 global hoverables (GitHub #45)."""

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


def point(cdp: Cdp, selector: str) -> tuple[float, float]:
    bounds = cdp.eval(f"""(()=>{{const rect=document.querySelector({selector!r}).getBoundingClientRect();return {{x:rect.left+rect.width/2,y:rect.top+rect.height/2}}}})()""")
    return bounds["x"], bounds["y"]


def mouse(cdp: Cdp, selector: str, modifiers: int = 0, click: bool = True) -> None:
    x, y = point(cdp, selector)
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "modifiers": modifiers})
    if click:
        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y,
                                                "button": "left", "clickCount": 1, "modifiers": modifiers})
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y,
                                                "button": "left", "clickCount": 1, "modifiers": modifiers})


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output_dir = ROOT / "worklog" / "issues" / "rendered"
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-hoverables-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-hoverables-project-", ignore_cleanup_errors=True)
    port = free_port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    gf_selector = '.gf-entity-label.lex-hoverable[data-hover-target-type="gf"][data-hover-target-id="1"]'
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
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("state.selected.gfs=state.data.gfs.rows.find(row=>row.name==='Alexander').id;navigate('gfs')")
            wait_eval(cdp, f"!!document.querySelector({gf_selector!r})", 30)
            cdp.eval(f"document.querySelector({gf_selector!r}).scrollIntoView({{block:'center'}})")
            before = cdp.eval(f"getComputedStyle(document.querySelector({gf_selector!r})).color")
            mouse(cdp, gf_selector, click=False)
            # 5s was too tight under parallel load: the synthetic mouse move lands but
            # :hover has not applied yet, so the run fails on hover LATENCY rather
            # than on whether hovering works, which is what this checks.
            wait_eval(cdp, f"document.querySelector({gf_selector!r}).matches(':hover')", 30)
            after = cdp.eval(f"(()=>{{const style=getComputedStyle(document.querySelector({gf_selector!r}));return{{color:style.color,decoration:style.textDecorationLine}}}})()")
            assert after["decoration"] == "underline", {"before": before, "after": after}
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            (output_dir / "github-45-ff8-gf-hoverable.png").write_bytes(base64.b64decode(screenshot["data"]))

            mouse(cdp, gf_selector)
            wait_eval(cdp, "state.tab==='gfs'&&state.data.gfs.rows.find(row=>row.id===state.selected.gfs)?.name==='Shiva'", 30)

            cdp.eval("window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{hoverableAltClick:true,developerMode:false,viewPreferences:{}}}));state.selected.gfs=state.data.gfs.rows.find(row=>row.name==='Alexander').id;renderGFs()")
            wait_eval(cdp, f"!!document.querySelector({gf_selector!r})", 30)
            mouse(cdp, gf_selector)
            assert cdp.eval("state.data.gfs.rows.find(row=>row.id===state.selected.gfs)?.name") == "Alexander"
            mouse(cdp, gf_selector, modifiers=1)
            wait_eval(cdp, "state.data.gfs.rows.find(row=>row.id===state.selected.gfs)?.name==='Shiva'", 30)

            cdp.eval("state.selected.gfs=state.data.gfs.rows.find(row=>row.name==='Alexander').id;renderGFs();document.querySelector('.gf-entity-label.lex-hoverable[data-hover-target-id=\"1\"]').click()")
            wait_eval(cdp, "state.data.gfs.rows.find(row=>row.id===state.selected.gfs)?.name==='Shiva'", 30)

            item_selector = '.ff8-item-label.lex-hoverable[data-hover-target-type="item"]'
            cdp.eval("window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{hoverableAltClick:false,developerMode:false,viewPreferences:{}}}));state.selected.items=94;navigate('items')")
            wait_eval(cdp, f"!!document.querySelector({item_selector!r})", 30)
            item_id = cdp.eval(f"Number(document.querySelector({item_selector!r}).dataset.hoverTargetId)")
            mouse(cdp, item_selector)
            wait_eval(cdp, f"state.tab==='items'&&Number(state.selected.items)==={item_id}", 30)
            result = cdp.eval("""(()=>({
              selectedItem:state.selected.items,
              selectedRow:document.querySelector('.lex-list-row.selected')?.dataset.key,
              typed:document.querySelectorAll('.lex-hoverable[data-hover-target-type][data-hover-target-id]').length,
              errors:window.__testErrors,
            }))()""")
            assert int(result["selectedRow"]) == item_id and result["typed"] > 5 and not result["errors"], result

            cdp.eval("""(()=>{window.__savedSettingsArgs=null;window.pywebview={api:{
              lexeditor_settings:()=>Promise.resolve({updateCheckFrequency:'daily',updateCheckChoices:[{value:'daily',label:'Daily'}],developerMode:false,hoverableAltClick:false,selectionHoldMs:650,tableRowsPerPage:15,viewPreferences:{},helpers:[]}),
              save_lexeditor_settings:(...args)=>{window.__savedSettingsArgs=args;return Promise.resolve({updateCheckFrequency:args[0],updateCheckChoices:[{value:'daily',label:'Daily'}],developerMode:args[1],hoverableAltClick:args[2],viewPreferences:{},helpers:[]})}
            }};LexeditorUI.openSettings()})()""")
            wait_eval(cdp, "!!document.querySelector('#lex-hoverableAltClick')", 30)
            assert cdp.eval("document.querySelector('label[for=\"lex-hoverableAltClick\"]')?.textContent") == "Alt + Click hoverable linking"
            layout = cdp.eval("""(()=>{const dialog=document.querySelector('.lex-global-settings');const cards=[...dialog.querySelectorAll('.lex-global-setting')];return{
              columns:new Set(cards.map(card=>Math.round(card.getBoundingClientRect().left))).size,
              scrollHeight:dialog.scrollHeight,clientHeight:dialog.clientHeight,mustScroll:dialog.classList.contains('lex-settings-must-scroll'),overflowY:getComputedStyle(dialog).overflowY,
            }})()""")
            assert layout["columns"] >= 2, layout
            if layout["scrollHeight"] > layout["clientHeight"] + 1:
                assert layout["mustScroll"] and layout["overflowY"] in {"auto", "scroll"}, layout
            cdp.eval("document.querySelector('#lex-hoverableAltClick').click();document.querySelector('.lex-global-settings .lex-settings-save-control').click()")
            wait_eval(cdp, "Array.isArray(window.__savedSettingsArgs)", 30)
            saved = cdp.eval("JSON.stringify(window.__savedSettingsArgs)")
            import json as _json
            saved = _json.loads(saved)
            assert len(saved) == 1 and isinstance(saved[0], dict), saved
            assert saved[0]["updateCheckFrequency"] == "daily", saved
            assert saved[0]["hoverableAltClick"] is True, saved
            print({"hover": [before, after], "item": result})
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
