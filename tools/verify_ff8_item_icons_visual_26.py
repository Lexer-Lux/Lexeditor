"""Hidden Edge acceptance check for FF8 native item-type icons."""

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
    output_dir = ROOT / "worklog" / "issues" / "rendered"
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-item-icons-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-item-icons-project-", ignore_cleanup_errors=True)
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
            wait_eval(cdp, "[...document.images].every(image=>image.complete)", 30)
            items = cdp.eval("""(()=>{
              const labels=[...document.querySelectorAll('.ff8-record-list .ff8-item-label')];
              const detailIcon=document.querySelector('.lex-detail-panel-heading .lex-detail-panel-icon .ff8-item-icon');
              const detailSlot=detailIcon?.closest('.lex-detail-panel-icon');
              const images=[...document.querySelectorAll('.ff8-record-list .ff8-item-icon')];
              const geometry=node=>{const image=node.querySelector('.ff8-item-icon'),style=getComputedStyle(node);return{
                fontSize:parseFloat(style.fontSize),iconWidth:image.getBoundingClientRect().width,
                iconHeight:image.getBoundingClientRect().height};};
              const heading=detailIcon?.closest('.lex-detail-panel-heading');
              return {labels:labels.length,detailIcon:!!detailIcon,images:images.length,
                loaded:images.every(image=>image.complete&&image.naturalWidth>0),
                clipped:labels.some(label=>label.scrollWidth>label.clientWidth+1),
                rowGeometry:geometry(labels[0]),detailGeometry:detailIcon?{
                  iconWidth:detailIcon.getBoundingClientRect().width,
                  iconHeight:detailIcon.getBoundingClientRect().height,
                  slotWidth:detailSlot.getBoundingClientRect().width,
                  slotHeight:detailSlot.getBoundingClientRect().height,
                  headingHeight:heading.getBoundingClientRect().height,
                  headingPadding:getComputedStyle(heading).padding}:null,errors:window.__testErrors};
            })()""")
            assert items["labels"] > 5 and items["detailIcon"] and items["images"] == items["labels"], items
            assert items["loaded"] and not items["clipped"] and not items["errors"], items
            row_ratio = items["rowGeometry"]["iconHeight"] / items["rowGeometry"]["fontSize"]
            assert 1.25 <= row_ratio <= 1.55, items
            assert items["detailGeometry"]["iconHeight"] == items["detailGeometry"]["slotHeight"], items
            assert items["detailGeometry"]["iconWidth"] == items["detailGeometry"]["slotWidth"], items
            # Detail headers now reserve ten percent of their panel. The icon
            # must fill that available row instead of forcing the header taller.
            assert items["detailGeometry"]["iconHeight"] >= items["detailGeometry"]["headingHeight"] * .9, items
            item_screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            (output_dir / "github-57-ff8-item-icon-scaling.png").write_bytes(
                base64.b64decode(item_screenshot["data"]))

            cdp.eval("navigate('shops')")
            wait_eval(cdp, "state.tab==='shops'&&document.querySelectorAll('.ff8-shop-table .ff8-item-search').length===16", 30)
            wait_eval(cdp, "[...document.querySelectorAll('.ff8-shop-table .ff8-item-icon')].every(image=>image.complete)", 30)
            shops = cdp.eval("""(()=>{const controls=[...document.querySelectorAll('.ff8-shop-table .ff8-item-search')];const images=controls.flatMap(control=>[...control.querySelectorAll('.ff8-item-icon')]);return {controls:controls.length,images:images.length,loaded:images.every(image=>image.naturalWidth>0),selects:document.querySelectorAll('.ff8-shop-table select').length,errors:window.__testErrors}})()""")
            assert shops["controls"] > 0 and shops["images"] == shops["controls"] and shops["loaded"], shops
            assert shops["selects"] == 0, shops

            cdp.eval("navigate('weapons')")
            wait_eval(cdp, "state.tab==='weapons'&&document.querySelectorAll('.weapon-ingredient-row .ff8-item-search').length===4", 30)
            wait_eval(cdp, "[...document.querySelectorAll('.weapon-ingredient-row .ff8-item-icon')].every(image=>image.complete)", 30)
            weapons = cdp.eval("""(()=>{const controls=[...document.querySelectorAll('.weapon-ingredient-row .ff8-item-search')];const images=controls.flatMap(control=>[...control.querySelectorAll('.ff8-item-icon')]);return {controls:controls.length,images:images.length,loaded:images.every(image=>image.naturalWidth>0),selects:document.querySelectorAll('.weapon-ingredients select').length,errors:window.__testErrors}})()""")
            assert weapons == {"controls": 4, "images": 4, "loaded": True, "selects": 0, "errors": []}, weapons
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            (output_dir / "github-26-ff8-item-icons.png").write_bytes(base64.b64decode(screenshot["data"]))

            cdp.eval("document.querySelector('.weapon-ingredient-row .ff8-item-icon').src='/assets/icons/999.png'")
            wait_eval(cdp, "!document.querySelector('.weapon-ingredient-row .ff8-item-icon-slot img[src$=\"999.png\"]')", 30)
            assert cdp.eval("!!document.querySelector('.weapon-ingredient-row .ff8-item-icon-slot')"), "text alignment slot must survive a missing image"
            print({"items": items, "shops": shops, "weapons": weapons})
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
