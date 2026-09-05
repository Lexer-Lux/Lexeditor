"""Hidden Edge render check for the FF8 Info page (GitHub #58)."""

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
    output = ROOT / "worklog/issues/rendered/github-58-ff8-info.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-info-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-info-project-", ignore_cleanup_errors=True)
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
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('dashboard')")
            wait_eval(cdp, "state.tab==='dashboard'&&!!document.querySelector('.ff8-information')", 30)
            result = cdp.eval("""(()=>{const panel=document.querySelector('.ff8-information');return{
              toolbarHidden:document.querySelector('#toolbar').hidden,
              panel:!!panel,
              title:panel?.querySelector('.lex-detail-title,h1,h2')?.textContent.trim(),
              infoIcon:!!panel?.querySelector('svg'),
              sections:[...panel.querySelectorAll('.lex-detail-section-title,h3')].map(n=>n.textContent.trim()),
              folderButton:!!panel.querySelector('.ff8-folder-button'),
              text:panel.textContent,
              oldCaption:document.body.textContent.includes('FF8 plugin and runtime status'),
              oldPaths:document.body.textContent.includes('FFNx Hext patches')||document.body.textContent.includes('Private extracted baseline'),
              errors:window.__testErrors};})()""")
            assert result["toolbarHidden"] and result["panel"], result
            assert result["title"] == "Information" and result["infoIcon"], result
            # PLUGIN SFX only appears in developer mode, so check the fixed three.
            assert result["sections"][:3] == ["GAME", "GAME DATA", "FFNX"], result
            assert result["folderButton"], result
            assert not result["oldCaption"] and not result["oldPaths"] and not result["errors"], result
            shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(shot["data"]))
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
