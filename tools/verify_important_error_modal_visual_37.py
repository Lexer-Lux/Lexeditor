"""Hidden Edge acceptance for the shared important-error modal (GitHub #37)."""

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
    output = ROOT / "worklog" / "issues" / "rendered" / "github-37-important-save-error-modal.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-important-error-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-important-error-project-", ignore_cleanup_errors=True)
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
                "width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False,
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
            cdp.eval("state.data.weapons.rows[0].upgradePrice=3000;saveAll().catch(()=>true)", True)
            wait_eval(cdp, "!!document.querySelector('.lex-important-dialog')", 30)
            result = cdp.eval("""(()=>{const dialog=document.querySelector('.lex-important-dialog'),backdrop=dialog.closest('.lex-dialog-backdrop'),rect=dialog.getBoundingClientRect(),link=dialog.querySelector('.lex-important-item-link');return{role:dialog.getAttribute('role'),modal:dialog.getAttribute('aria-modal'),title:dialog.querySelector('h2').textContent,item:link?.textContent,row:dialog.querySelector('.lex-important-list li')?.textContent,close:dialog.querySelector('.lex-dialog-action').textContent,status:document.querySelector('#plugin-status')?.textContent,active:document.activeElement?.textContent,width:rect.width,height:rect.height,dirty:dirtyCount(),errors:window.__testErrors,backdropClass:backdrop.className}})()""")
            assert result["role"] == "alertdialog" and result["modal"] == "true", result
            assert result["title"] == "Save failed" and result["close"] == "Confirm and Close", result
            assert result["item"] and result["row"] == f'{result["item"]}: Upgrade price must be 0 to 2550 in steps of 10', result
            assert result["active"] == "Confirm and Close", result
            assert result["width"] >= 600 and result["dirty"] > 0 and not result["errors"], result
            retained = cdp.eval("""(()=>{const backdrop=document.querySelector('.lex-important-backdrop');backdrop.dispatchEvent(new MouseEvent('click',{bubbles:true}));backdrop.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return!!document.querySelector('.lex-important-dialog')})()""")
            assert retained, "backdrop click or Escape dismissed the important modal"
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            navigated = cdp.eval("state.tab='items';document.querySelector('.lex-important-item-link').click();state.tab==='weapons'&&!document.querySelector('.lex-important-dialog')")
            assert navigated, "the item link did not close the modal and return to its record"
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
