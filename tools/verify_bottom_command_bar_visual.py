"""Rendered acceptance for the shared bottom search and pagination bar."""

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
    output = ROOT / "worklog" / "issues" / "rendered" / "shared-bottom-command-bar-ff8.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-bottom-bar-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-bottom-bar-project-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            port = free_port()
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
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('items')")
            try:
                wait_eval(cdp, "state.tab==='items'&&!!document.querySelector('.lex-pager-search input')", 5)
            except AssertionError:
                print(json.dumps(cdp.eval("({tab:state.tab,errors:window.__testErrors,toolbar:document.querySelector('#toolbar')?.innerText,main:document.querySelector('#main')?.innerText?.slice(0,300),pager:document.querySelector('.lex-pager')?.outerHTML,sharedSearch:typeof LexeditorUI.bottomSearch,source:showPaged.toString().slice(0,500)})"), ensure_ascii=True))
                raise
            geometry = cdp.eval("""(()=>{
              const bar=document.querySelector('.lex-pager'),search=bar.querySelector('.lex-pager-search'),
                icon=search.querySelector('svg'),controls=bar.querySelector('.lex-pager-controls'),
                right=bar.querySelector('.lex-pager-right'),toolbar=document.querySelector('#toolbar'),
                cell=document.querySelector('.lex-column-list-row .lex-column-list-cell');
              const box=node=>node.getBoundingClientRect(),barBox=box(bar),searchBox=box(search),
                controlsBox=box(controls),rightBox=box(right),cellBox=box(cell);
              const text=cell.firstChild,range=document.createRange();range.selectNodeContents(text);
              const textBox=range.getBoundingClientRect();
              return{toolbar:getComputedStyle(toolbar).display,icon:!!icon,
                order:searchBox.right<controlsBox.left&&controlsBox.right<rightBox.left,
                centerDelta:Math.abs((controlsBox.left+controlsBox.width/2)-innerWidth/2),
                textCenterDelta:(textBox.top+textBox.height/2)-(cellBox.top+cellBox.height/2),
                barBottom:Math.abs(barBox.bottom-innerHeight),errors:window.__testErrors||[]};
            })()""")
            assert geometry["toolbar"] == "none" and geometry["icon"], geometry
            assert geometry["order"] and geometry["centerDelta"] <= 1.5, geometry
            assert abs(geometry["textCenterDelta"]) <= 2.0 and geometry["barBottom"] <= 1, geometry
            cdp.eval("""(()=>{const input=document.querySelector('.lex-pager-search input');input.focus();input.value='Potion';input.setSelectionRange(6,6);input.dispatchEvent(new Event('input',{bubbles:true}))})()""")
            wait_eval(cdp, "state.filters.items==='Potion'&&document.activeElement?.dataset.lexBottomSearch==='ff8-items'&&document.activeElement.selectionStart===6", 10)
            cdp.eval("navigate('weapons')")
            wait_eval(cdp, "state.tab==='weapons'&&!!document.querySelector('.lex-pager-search input')", 20)
            one_page = cdp.eval("""(()=>{const bar=document.querySelector('.lex-pager');return{
              present:!!bar,page:bar.querySelector('.lex-page-position')?.innerText,
              search:bar.querySelector('.lex-pager-search input')?.getAttribute('aria-label'),
              errors:window.__testErrors||[]}})()""")
            assert one_page["present"] and one_page["search"] == "Search weapons", one_page
            assert not one_page["errors"], one_page
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print({"geometry": geometry, "onePage": one_page, "screenshot": str(output)})
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
