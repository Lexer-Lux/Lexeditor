"""Hidden rendered acceptance check for the FF9 plugin (GitHub #70)."""

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

from games.ff9.plugin import FF9Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-70-ff9-plugin.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff9-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff9-project-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    try:
        game = Path(project.name) / "game"
        for relative in (
            "FF9_Launcher.exe", "x64/FF9.exe",
            "x64/FF9_Data/Managed/Assembly-CSharp.dll", "StreamingAssets/p0data2.bin",
        ):
            target = game / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fixture")
        items = game / "StreamingAssets" / "Data" / "Items" / "Items.csv"
        items.parent.mkdir(parents=True, exist_ok=True)
        items.write_text(
            "# Id;Price;Usable;Name\n# Int32;UInt32;Bit;String\n"
            "0;250;1;Hammer;# 000 - Hammer\n1;320;0;Dagger;# 001 - Dagger\n",
            encoding="utf-8",
        )
        with FF9Session({
            "LEXEDITOR_FF9_ROOT": str(game),
            "LEXEDITOR_FF9_DATA_ROOT": str(Path(project.name) / "data"),
            "LEXEDITOR_FF9_PROJECT": str(Path(project.name) / "project"),
        }) as session:
            port = free_port()
            hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
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
                "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "document.title==='Lexeditor - Final Fantasy 9'", 20)
            try:
                wait_eval(cdp, "!!(typeof state!=='undefined'&&state.dashboard&&document.querySelector('.ff9-table')&&document.querySelector('.ff9-detail'))", 30)
            except AssertionError as error:
                diagnostic = cdp.eval("""(()=>({url:location.href,title:document.title,
                  state:typeof state,errors:window.__testErrors,body:document.body.innerText.slice(0,800)}))()""")
                raise AssertionError(f"FF9 scaffold did not finish rendering: {diagnostic}") from error
            result = cdp.eval("""(()=>({
              title:document.title,
              tabs:[...document.querySelectorAll('.lex-nav-frame button')].map((node=>[...node.childNodes].filter(part=>!(part.nodeType===1&&part.classList.contains('lex-tab-shortcut'))).map(part=>part.textContent).join('').trim())),
              heading:document.querySelector('.lex-detail-panel-title').textContent.trim(),
              rows:document.querySelectorAll('.ff9-table .lex-column-list-row:not(.lex-filler-row)').length,
              inputs:[...document.querySelectorAll('.ff9-detail input')].map(node=>({type:node.type,value:node.value,checked:node.checked})),
              saveDisabled:document.querySelector('#global-save').disabled,
              errors:window.__testErrors,
            }))()""")
            assert result["title"] == "Lexeditor - Final Fantasy 9", result
            assert result["tabs"][-1] == "Tweaks" and len(result["tabs"]) > 1, result
            assert {"Accessories", "Abilities", "Armor", "Items", "Magic", "Synthesis", "Weapons"}.issubset(result["tabs"]), result
            assert result["heading"] == "Dagger" or result["heading"] == "Hammer", result
            assert result["rows"] == 2, result
            assert any(value["type"] == "number" and value["value"] in {"250", "320"} for value in result["inputs"]), result
            assert any(value["type"] == "checkbox" for value in result["inputs"]), result
            assert result["saveDisabled"] and not result["errors"], result
            cdp.eval("""(()=>{const input=document.querySelector('.ff9-detail input[type=number]');input.value='333';input.dispatchEvent(new Event('input',{bubbles:true}));return dirtyCount()})()""")
            wait_eval(cdp, "dirtyCount()===1&&!document.querySelector('#global-save').disabled", 10)
            cdp.eval("save()")
            wait_eval(cdp, "dirtyCount()===0&&document.querySelector('#global-save').disabled", 10)
            saved = Path(project.name) / "project" / "StreamingAssets" / "Data" / "Items" / "Items.csv"
            assert saved.is_file() and ";333;" in saved.read_text(encoding="utf-8"), saved
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(shot["data"]))
            cdp.eval("navigate('datamap')")
            wait_eval(cdp, "document.querySelectorAll('.lex-column-list-row').length>=4", 10)
            statuses = cdp.eval("state.dataMap.rows.map(row=>row.status)")
            assert "integrated" in statuses and "not-integrated" in statuses, statuses
            print({**result, "dataMapRows": len(statuses), "screenshot": str(output)})
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
