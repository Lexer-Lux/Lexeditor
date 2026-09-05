"""Focused hidden render check for the shared bounded numeric slider."""

from __future__ import annotations

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
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-slider-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-slider-project-", ignore_cleanup_errors=True)
    browser = None
    try:
        Path(project.name, "mod.json").write_text(json.dumps({
            "id": "ff8-slider-test", "name": "FF8 Slider Test",
            "enabled": True, "order": 0,
        }), encoding="utf-8")
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            port = free_port()
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            browser = subprocess.Popen([
                str(edge), "--headless=new", "--no-first-run",
                "--no-default-browser-check", "--remote-allow-origins=*",
                "--use-angle=swiftshader", f"--remote-debugging-port={port}",
                f"--user-data-dir={profile.name}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=flags)
            page = next(item for item in wait_json(
                f"http://127.0.0.1:{port}/json/list") if item.get("type") == "page")
            cdp = Cdp(page["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('characters')")
            wait_eval(cdp, "!!document.querySelector('.character-limit-break-field input')", 30)
            result = cdp.eval("""(()=>{
              const field=document.querySelector('.character-limit-break-field.lex-has-value-fill');
              const handle=field.querySelector('.lex-value-handle');
              const input=field.querySelector('input:not(:disabled)');
              const box=input.getBoundingClientRect(), grip=handle.getBoundingClientRect();
              let inputs=0; input.addEventListener('input',()=>inputs++);
              handle.setPointerCapture=()=>{};
              handle.style.transition='none';
              handle.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,cancelable:true,
                button:0,buttons:1,pointerId:41,clientX:grip.left+grip.width/2,
                clientY:grip.top+grip.height/2}));
              const opacityDuring=Number(getComputedStyle(handle).opacity);
              const activeClass=field.className;
              for(let i=1;i<=120;i++) handle.dispatchEvent(new PointerEvent('pointermove',{
                bubbles:true,buttons:1,pointerId:41,clientX:box.left+box.width*i/121,
                clientY:box.top+box.height/2}));
              handle.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,button:0,
                buttons:0,pointerId:41,clientX:box.right-2,clientY:box.top+box.height/2}));
              return {inputs,opacity:opacityDuring,activeClass,
                value:input.value,connected:input.isConnected,errors:window.__testErrors||[]};
            })()""")
            assert 0 < result["opacity"] < 0.8, result
            assert result["inputs"] == 1 and result["connected"] and not result["errors"], result
            print(json.dumps(result, sort_keys=True))
    finally:
        if browser is not None:
            browser.kill()
            browser.wait(timeout=10)
        project.cleanup()
        profile.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
