"""Hidden Edge proof for the shared numeric reference display in RDR2."""

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

from games.rdr2.plugin import Rdr2Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-26-rdr2-numeric-references.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-rdr2-ref-edge-", ignore_cleanup_errors=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    try:
        with Rdr2Session() as session:
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
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting&&state.catalog?.items?.length", 90)
            cdp.eval("navigate('items')")
            wait_eval(cdp, "state.tab==='items'", 10)
            probe = cdp.eval("""(()=>{
              let applied=null;
              const matching=refStack([['V','vtag',50],['K','ktag',50]],50,value=>applied=value,String);
              const input=el('input',{value:'50'});
              const differing=refField(input,[['V','vtag',60],['K','ktag',50]],50,value=>applied=value,String);
              differing.style.cssText='position:fixed;left:20px;bottom:20px;width:260px;z-index:9999;background:var(--panel);padding:10px';
              document.body.append(differing);
              const button=differing.querySelector('.lex-reference-value'),br=button.getBoundingClientRect(),ir=input.getBoundingClientRect();
              button.click();
              return{matchingAbsent:matching==='',labels:[...differing.querySelectorAll('.lex-reference-value')].map(node=>node.textContent.trim()),applied,centerDelta:Math.abs((br.top+br.height/2)-(ir.top+ir.height/2)),fontSize:parseFloat(getComputedStyle(button).fontSize),errors:window.__testErrors};
            })()""")
            assert probe["matchingAbsent"], probe
            assert probe["labels"] == ["V60"] and probe["applied"] == 60, probe
            assert probe["centerDelta"] <= 3 and probe["fontSize"] >= 11, probe
            assert not probe["errors"], probe
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print({"probe": probe, "screenshot": str(output)})
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
