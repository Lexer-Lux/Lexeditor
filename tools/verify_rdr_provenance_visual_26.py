"""Hidden rendered check for shared provenance in the RDR plugin (GitHub #26)."""

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

from games.rdr.plugin import RdrSession  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    output = ROOT / "worklog" / "issues" / "rendered" / "github-26-rdr-provenance.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-rdr-provenance-", ignore_cleanup_errors=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    try:
        with RdrSession({"LEXEDITOR_RDR_OPEN_URL_DRY_RUN": "1"}) as session:
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
                "width": 1500, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            wait_eval(cdp, "!!document.querySelector('.item-detail')", 30)
            item = cdp.eval("""(() => {
              const source=[...document.querySelectorAll('.item-detail .lex-source-control')]
                .find(node=>node.querySelector('input:not([type=checkbox])'));
              const input=source?.querySelector('input');
              if(!input)return {missing:true,errors:window.__testErrors};
              const before=input.value;
              input.value=String((Number(before)||0)+1);
              input.dispatchEvent(new Event('input',{bubbles:true}));
              const reference=source.querySelector('.lex-reference-value');
              const changed={before,after:input.value,tag:reference?.querySelector('.lex-reference-tag')?.textContent,
                text:reference?.textContent.trim(),dirty:dirtyCount(),errors:window.__testErrors};
              reference?.click();
              return {...changed,restored:input.value,dirtyAfter:dirtyCount()};
            })()""")
            assert not item.get("missing") and item["tag"] == "V" and item["dirty"] > 0, item
            assert item["restored"] == item["before"] and item["dirtyAfter"] == 0, item
            assert not item["errors"], item

            cdp.eval("navigate('shops')")
            wait_eval(cdp, "!!document.querySelector('.shop-detail')", 30)
            shops = cdp.eval("(()=>({controls:document.querySelectorAll('.shop-detail .lex-source-control').length,errors:window.__testErrors}))()")
            assert shops["controls"] == 3 and not shops["errors"], shops

            cdp.eval("navigate('missions')")
            wait_eval(cdp, "!!document.querySelector('.mission-detail')", 30)
            missions = cdp.eval("(()=>({controls:document.querySelectorAll('.mission-detail .lex-source-control').length,errors:window.__testErrors}))()")
            assert missions["controls"] == 3 and not missions["errors"], missions
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print(json.dumps({"item": item, "shops": shops, "missions": missions}, ensure_ascii=True))
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
