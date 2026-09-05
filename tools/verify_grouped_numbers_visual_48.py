"""Hidden Edge visual proof for shared comma-grouped numeric displays."""

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
    output = ROOT / "worklog" / "issues" / "rendered" / "github-48-ff8-grouped-numbers.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-grouped-numbers-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-grouped-numbers-project-", ignore_cleanup_errors=True)
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
            cdp.eval("navigate('items')")
            wait_eval(cdp, "document.querySelectorAll('.ff8-record-list .lex-number').length>=2", 30)
            result = cdp.eval("""(()=>{
              const values=[...document.querySelectorAll('.ff8-record-list .lex-number')].map(node=>node.textContent.trim());
              const grouped=values.filter(value=>value.includes(','));
              const sample=[...document.querySelectorAll('.ff8-record-list .lex-number')].find(node=>node.textContent.includes(','));
              const detail=document.querySelector('.item-price-section .lex-readonly-field');
              const input=document.querySelector('.item-price-section input[inputmode="numeric"]');
              const table=LexeditorUI.columnList({rows:[{name:'Probe',amount:20000}],columns:[{key:'name',label:'Name'},{key:'amount',label:'Amount'}]});
              const reference=LexeditorUI.referenceDisplay({current:1,sources:[{name:'Vanilla',shortName:'V',value:20000}],apply:()=>{}});
              return{values:values.slice(0,12),grouped:grouped.slice(0,8),formatProbe:[1000,20000,-1234.5].map(LexeditorUI.formatNumber),sharedTable:table.querySelector('.lex-number')?.textContent,sharedReference:reference?.textContent.trim(),
                style:sample?{kerning:getComputedStyle(sample).fontKerning,numeric:getComputedStyle(sample).fontVariantNumeric,font:getComputedStyle(sample).fontFamily}:null,
                detail:detail?.value,input:input?.value,
                detailFont:detail?getComputedStyle(detail).fontFamily:null,
                inputFont:input?getComputedStyle(input).fontFamily:null,
                overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,errors:window.__testErrors};
            })()""")
            assert result["formatProbe"] == ["1,000", "20,000", "-1,234.5"], result
            assert result["sharedTable"] == "20,000" and result["sharedReference"] == "V20,000", result
            assert result["grouped"] and all("," in value for value in result["grouped"]), result
            assert result["style"] and result["style"]["kerning"] == "none", result
            assert "FF8 Menu" in result["style"]["font"], result
            assert result["detail"] and "," in result["detail"], result
            assert result["input"] and "," in result["input"], result
            assert "FF8 Menu" in result["detailFont"] and "FF8 Menu" in result["inputFont"], result
            assert result["overflow"] == 0 and not result["errors"], result
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print(json.dumps({"result": result, "screenshot": str(output)}, ensure_ascii=True))
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
