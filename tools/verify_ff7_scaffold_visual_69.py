"""Hidden rendered acceptance check for the real FF7 kernel editor (GitHub #69)."""

from __future__ import annotations

import base64
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff7.kernel import Kernel, resolve_kernel  # noqa: E402
from games.ff7.paths import GAME_ROOT  # noqa: E402
from games.ff7.plugin import FF7Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-69-ff7-kernel-editor.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff7-edge-", ignore_cleanup_errors=True)
    workspace = tempfile.TemporaryDirectory(prefix="lexeditor-ff7-project-", ignore_cleanup_errors=True)
    browser = None
    cdp = None
    root = Path(workspace.name)
    source, relative = resolve_kernel(GAME_ROOT)
    game = root / "game"
    target = game / relative
    target.parent.mkdir(parents=True)
    shutil.copy2(source, target)
    (game / "FFVII_LAUNCHER.exe").write_bytes(b"test")
    project = root / "project"
    try:
        with FF7Session({
            "LEXEDITOR_FF7_ROOT": str(game),
            "LEXEDITOR_FF7_DATA_ROOT": str(root / "data"),
            "LEXEDITOR_FF7_PROJECT": str(project),
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
            wait_eval(cdp, "document.title==='Lexeditor - Final Fantasy 7 (Original)'", 20)
            wait_eval(cdp, "!!(state.data&&document.querySelector('.ff7-table')&&document.querySelector('.ff7-detail'))", 30)
            result = cdp.eval("""(()=>({
              title:document.title,
              tabs:[...document.querySelectorAll('.lex-nav-frame button')].map((node=>[...node.childNodes].filter(part=>!(part.nodeType===1&&part.classList.contains('lex-tab-shortcut'))).map(part=>part.textContent).join('').trim())),
              heading:document.querySelector('.lex-detail-panel-title')?.textContent.trim(),
              rows:document.querySelectorAll('.ff7-table .lex-column-list-row').length,
              recordCounts:Object.fromEntries(Object.entries(state.records).map(([key,value])=>[key,value.length])),
              source:state.data.sourceRelativePath,
              saveDisabled:document.querySelector('#global-save').disabled,
              errors:window.__testErrors,
            }))()""")
            assert result["title"] == "Lexeditor - Final Fantasy 7 (Original)", result
            assert {"Accessories", "Armor", "Items", "Materia", "Weapons"}.issubset(result["tabs"]), result
            assert result["heading"] == "Potion" and result["rows"] == 16, result
            assert result["recordCounts"] == {
                "items": 128, "weapons": 128, "armor": 32, "accessories": 32, "materia": 96,
            }, result
            assert result["source"].lower().endswith("kernel/kernel.bin"), result
            assert result["saveDisabled"] and not result["errors"], result

            original = cdp.eval("state.records.items[0].values.attackPower")
            changed = original + 1 if original < 255 else original - 1
            cdp.eval(f"""(()=>{{const input=document.querySelector('[aria-label="Attack power for Potion"]');
              input.value={changed};input.dispatchEvent(new Event('input',{{bubbles:true}}));return true}})()""")
            wait_eval(cdp, f"state.records.items[0].values.attackPower==={changed}&&!document.querySelector('#global-save').disabled", 10)
            reference = cdp.eval("""(()=>({
              dirty:dirtyCount(),
              reference:[...document.querySelectorAll('.lex-reference-values')]
                .some(node=>node.textContent.includes(String(state.data.vanilla.items[0].values.attackPower))),
              count:document.querySelectorAll('.lex-reference-values').length,
              control:document.querySelector('[aria-label="Attack power for Potion"]')?.parentElement?.parentElement?.outerHTML,
            }))()""")
            assert reference["dirty"] == 1 and reference["reference"], reference
            cdp.eval("document.querySelector('#global-save').click()")
            wait_eval(cdp, "dirtyCount()===0&&document.querySelector('#global-save').disabled", 20)
            saved_path = project / relative
            assert saved_path.is_file(), saved_path
            assert Kernel(saved_path).records("items")[0]["values"]["attackPower"] == changed

            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(shot["data"]))
            cdp.eval("navigate('datamap')")
            wait_eval(cdp, "document.querySelectorAll('.lex-column-list-row').length===10", 10)
            statuses = cdp.eval("state.dataMap.rows.map(row=>row.status)")
            assert statuses.count("integrated") == 5, statuses
            assert statuses.count("not-integrated") + statuses.count("partial") == 5, statuses
            assert not cdp.eval("window.__testErrors"), cdp.eval("window.__testErrors")
            print({**result, "reference": reference, "dataMapStatuses": statuses, "screenshot": str(output)})
        return 0
    finally:
        if cdp:
            cdp.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        workspace.cleanup()
        profile.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
