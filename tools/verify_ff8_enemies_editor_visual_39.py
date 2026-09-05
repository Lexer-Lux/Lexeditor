"""Hidden Edge rendering check for the FF8 Enemies editor (GitHub #39)."""

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
    output = ROOT / "worklog" / "issues" / "rendered" / "github-39-ff8-enemies.png"
    curve_output = ROOT / "worklog" / "issues" / "rendered" / "github-39-ff8-enemy-curves.png"
    tables_output = ROOT / "worklog" / "issues" / "rendered" / "github-39-ff8-enemy-tables.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(
        prefix="lexeditor-ff8-enemies-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-enemies-project-", ignore_cleanup_errors=True)
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
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('enemies')")
            wait_eval(cdp, "state.tab==='enemies'&&!!document.querySelector('.lex-detail')", 30)
            result = cdp.eval("""(()=>({
              rows:document.querySelectorAll('.lex-barrelled-master .ff8-record-list .lex-column-list-row').length,
              groups:document.querySelectorAll('.enemy-properties-section,.enemy-table-section').length,
              properties:document.querySelectorAll('.enemy-properties-row>.enemy-property').length,
              controls:document.querySelectorAll('.lex-detail input,.lex-detail select,.lex-detail textarea').length,
              booleans:document.querySelectorAll('.lex-detail input[type="checkbox"]').length,
              sourceControls:document.querySelectorAll('.lex-detail .lex-source-strip').length,
              curves:document.querySelectorAll('.ff8-enemy-curve').length,
              scan:{text:document.querySelector('.enemy-scan-section textarea')?.value||'',
                pin:document.querySelector('.enemy-scan-section .lex-column-pin')?.getAttribute('aria-pressed')},
              curveVariables:[...document.querySelectorAll('.ff8-enemy-curve')].map(card=>
                [...card.querySelectorAll('.lex-curve-variable>span')].map(label=>label.textContent)),
              oldPlaceholder:document.body.textContent.includes('Read-only inventory'),
              filename:document.querySelector('.lex-detail')?.textContent.includes('c0m'),
              sectionGeometry:(()=>{const sections=[...document.querySelectorAll('.enemy-properties-section,.enemy-stat-growth,.enemy-scan-section,.enemy-table-section')],bounds=sections.map(section=>{const box=section.getBoundingClientRect(),contentNode=section.querySelector(':scope>.lex-detail-section-content'),content=contentNode?.getBoundingClientRect(),list=contentNode?.firstElementChild?.getBoundingClientRect(),title=section.querySelector(':scope>.lex-detail-section-title')?.getBoundingClientRect();return{name:section.querySelector(':scope>.lex-detail-section-title')?.textContent.trim(),table:section.classList.contains('enemy-table-section'),top:box.top,bottom:box.bottom,left:box.left,right:box.right,height:box.height,contentBottom:content?.bottom||box.top,listTop:list?.top||box.top,titleBottom:title?.bottom||box.top}});return{bounds,overlaps:bounds.filter((a,i)=>bounds.some((b,j)=>j>i&&a.left<b.right-1&&b.left<a.right-1&&a.top<b.bottom-1&&b.top<a.bottom-1)),escaped:bounds.filter(entry=>entry.contentBottom>entry.bottom+1),titleCollisions:bounds.filter(entry=>entry.table&&entry.listTop<entry.titleBottom-1)}})(),
              statHelp:(()=>{const node=document.querySelector('.enemy-stat-growth>.lex-detail-section-title .lex-info-help'),style=getComputedStyle(node);return{color:style.color,background:style.backgroundColor,opacity:style.opacity,filter:style.filter,textStrokeColor:style.webkitTextStrokeColor,textStrokeWidth:style.webkitTextStrokeWidth,parentColor:getComputedStyle(node.parentElement).color}})(),
              errors:window.__testErrors,
            }))()""")
            assert result["rows"] > 0, result
            assert result["groups"] >= 3 and result["properties"] > 0, result
            # Nine enemy property flags, plus one immunity toggle per element
            # (8) and per status (20) - those replace typing 155 by hand.
            assert result["controls"] >= 44 and result["booleans"] == 37, result
            assert result["sourceControls"] > 0, result
            assert result["curves"] == 7, result
            assert result["scan"]["text"] and result["scan"]["pin"] == "false", result
            assert all(labels == ["A", "B", "C", "D"] for labels in result["curveVariables"]), result
            assert not result["oldPlaceholder"] and not result["filename"], result
            assert result["sectionGeometry"]["bounds"] and not result["sectionGeometry"]["overlaps"] and not result["sectionGeometry"]["escaped"] and not result["sectionGeometry"]["titleCollisions"], result["sectionGeometry"]
            cdp.eval("document.querySelector('.enemy-table-section').scrollIntoView({block:'start'})")
            tables_screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            tables_output.write_bytes(base64.b64decode(tables_screenshot["data"]))
            assert not result["errors"], result
            assert result["statHelp"]["color"] == "rgb(5, 5, 5)" and result["statHelp"]["background"] == "rgb(255, 255, 255)", result
            assert result["statHelp"]["textStrokeWidth"] == "0px" and result["statHelp"]["opacity"] == "1", result
            cdp.eval("""(()=>{const input=document.querySelector('.enemy-scan-section textarea');
              input.value+=' TEST';input.dispatchEvent(new Event('input',{bubbles:true}))})()""")
            wait_eval(cdp, "!!document.querySelector('.enemy-scan-section .lex-reference-values')", 5)
            result["scan"]["liveReference"] = cdp.eval("document.querySelector('.enemy-scan-section .lex-reference-values').textContent.trim()")
            assert result["scan"]["liveReference"].startswith("V"), result
            scroll_restore = cdp.eval("""new Promise(resolve => { const detail=document.querySelector('.lex-detail');
              detail.scrollTop=Math.min(500,detail.scrollHeight-detail.clientHeight);
              const before=detail.scrollTop;
              document.querySelector('.enemy-scan-section .lex-reference-value').click();
              setTimeout(()=>resolve({before,after:document.querySelector('.lex-detail').scrollTop}),1000);
            })""", True)
            assert abs(scroll_restore["after"] - scroll_restore["before"]) <= 1, scroll_restore
            before_path = cdp.eval("document.querySelector('.ff8-enemy-curve .lex-curve-line').getAttribute('d')")
            cdp.eval("""(()=>{const input=document.querySelector('.ff8-enemy-curve input:not(:disabled)');
              input.value=String(Number(input.value)+1);input.dispatchEvent(new Event('input',{bubbles:true}))})()""")
            wait_eval(cdp, f"document.querySelector('.ff8-enemy-curve .lex-curve-line').getAttribute('d')!=={before_path!r}", 5)
            result["liveCurve"] = cdp.eval("""(()=>({
              changed:true,
              reference:document.querySelectorAll('.ff8-enemy-curve .lex-reference-values').length,
              errors:window.__testErrors}))()""")
            assert result["liveCurve"]["reference"] > 0 and not result["liveCurve"]["errors"], result
            cdp.eval("document.querySelector('.enemy-stat-growth').scrollIntoView({block:'start'})")
            curve_geometry = cdp.eval("""(()=>{const grid=document.querySelector('.enemy-stat-growth .character-curve-grid'),cards=[...grid.querySelectorAll('.ff8-enemy-curve')],box=grid.getBoundingClientRect();return{
              grid:{left:box.left,right:box.right},cards:cards.slice(0,4).map(card=>{const value=card.getBoundingClientRect();return{left:value.left,right:value.right}}),
              plot:(()=>{const value=cards[0].querySelector('.lex-curve-plot').getBoundingClientRect();return{x:value.left+value.width*.35,y:value.top+value.height*.45}})()};})()""")
            assert all(card["left"] >= curve_geometry["grid"]["left"] - 1 and
                       card["right"] <= curve_geometry["grid"]["right"] + 1
                       for card in curve_geometry["cards"]), curve_geometry
            cdp.eval("""(()=>{const card=document.querySelector('.ff8-enemy-curve'),svg=card.querySelector('.lex-curve-svg'),box=svg.getBoundingClientRect();card.querySelector('input:not(:disabled)').focus();svg.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:box.left+box.width*.35,clientY:box.top+box.height*.45}))})()""")
            wait_eval(cdp, "getComputedStyle(document.querySelector('.ff8-enemy-curve .lex-curve-variable-overlay')).opacity==='1'", 5)
            result["curveHover"] = cdp.eval("""(()=>({
              overlay:getComputedStyle(document.querySelector('.ff8-enemy-curve .lex-curve-variable-overlay')).opacity,
              tooltip:document.querySelector('.ff8-enemy-curve .lex-curve-tooltip').textContent,
              formula:document.querySelector('.ff8-enemy-curve .lex-curve-formula').textContent.trim()}))()""")
            assert result["curveHover"]["overlay"] == "1", result
            assert result["curveHover"]["tooltip"].startswith("(") and "," in result["curveHover"]["tooltip"], result
            assert result["curveHover"]["formula"], result
            curve_screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            curve_output.write_bytes(base64.b64decode(curve_screenshot["data"]))
            cdp.eval("state.filters.enemies='Rinoa';state.pages.enemies=0;renderEnemies()")
            wait_eval(cdp, "document.querySelectorAll('.lex-barrelled-master .ff8-record-list .lex-column-list-row:not(.lex-filler-row)').length===1", 30)
            special = cdp.eval("""(()=>{const row=document.querySelector('.lex-barrelled-master .ff8-record-list .lex-column-list-row'),title=document.querySelector('.lex-detail h2');return{
              rowText:row?.textContent,titleText:title?.textContent,
              rowFont:getComputedStyle(row.querySelector('.lex-column-list-cell:last-child')).fontFamily,
              titleFont:getComputedStyle(title).fontFamily};})()""")
            assert special["rowText"].endswith("「Rinoa」"), special
            assert special["titleText"] == "「Rinoa」", special
            assert "{" not in special["rowText"] and "}" not in special["rowText"], special
            assert "FF8 Menu" in special["rowFont"] and "FF8 Menu" in special["titleFont"], special
            result["specialName"] = special
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            output.write_bytes(base64.b64decode(screenshot["data"]))
            print(ascii(result))
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
