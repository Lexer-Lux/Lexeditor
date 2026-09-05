"""Hidden Edge acceptance check for shared N-barrelled tables (GitHub #44)."""

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
    profile = tempfile.TemporaryDirectory(
        prefix="lexeditor-barrels-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-barrels-project-", ignore_cleanup_errors=True)
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
            for width, height in ((1280, 720), (1600, 900)):
                cdp.call("Emulation.setDeviceMetricsOverride", {
                    "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
                })
                cdp.call("Page.navigate", {"url": session.url})
                cdp.call("Page.bringToFront")
                wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
                cdp.eval("localStorage.removeItem('lexeditor:barrels:ff8-magic');localStorage.removeItem('lexeditor:barrels:ff8-items');localStorage.removeItem('lexeditor:list-detail:ff8-magic');state.pages.magic=0;navigate('magic')")
                wait_eval(cdp, "state.tab==='magic'&&document.querySelector('.lex-barrel-count')?.textContent==='1'", 30)
                cdp.eval("new Promise(resolve=>setTimeout(resolve,750))", True)
                cdp.eval("window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{tableRowsPerPage:19,viewPreferences:{}}}))")
                wait_eval(cdp, "state.pageSizes.magic===19&&document.querySelectorAll('.lex-barrel-grid>.lex-list .lex-list-row').length===19", 30)
                cdp.eval("new Promise(resolve=>setTimeout(resolve,750))", True)
                configured_rows = cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),master=root.querySelector('.lex-barrel-grid>.lex-list'),detail=(root.querySelector(':scope>.lex-detail')||root.querySelector(':scope>.lex-panel-layout,:scope>.lex-list-detail-pane,.lex-detail')),rows=[...master.querySelectorAll('.lex-list-row')],last=rows[rows.length-1],mr=master.getBoundingClientRect(),lr=last?last.getBoundingClientRect():mr,dr=detail.getBoundingClientRect();return{rows:rows.length,fillers:master.querySelectorAll('.lex-filler-row').length,insideMaster:lr.bottom<=mr.bottom+1,heightGap:Math.abs(mr.height-dr.height),overflow:master.scrollHeight-master.clientHeight};})()""")
                # Magic is a slot table, so it shows one row per real slot and is
                # never padded out to the page height; the rows it does show must
                # still sit inside the master and never scroll it.
                assert configured_rows["rows"] == 19 and configured_rows["fillers"] == 0, configured_rows
                assert configured_rows["insideMaster"], configured_rows
                assert configured_rows["heightGap"] <= 2 and configured_rows["overflow"] <= 1, configured_rows
                cdp.eval("window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{tableRowsPerPage:15,viewPreferences:{}}}))")
                wait_eval(cdp, "state.pageSizes.magic===15&&document.querySelectorAll('.lex-barrel-grid>.lex-list .lex-list-row').length===15", 30)
                one = cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),master=root.querySelector('.lex-barrelled-master'),detail=(root.querySelector(':scope>.lex-detail')||root.querySelector(':scope>.lex-panel-layout,:scope>.lex-list-detail-pane,.lex-detail')),divider=root.querySelector('.lex-list-detail-divider'),box=divider.getBoundingClientRect(),table=root.querySelector('.lex-barrel-grid>.lex-list'),last=table.querySelector('.lex-column-list-head-cell:last-child')?.getBoundingClientRect(),tableBox=table.getBoundingClientRect(),pair=master.getBoundingClientRect().width+detail.getBoundingClientRect().width,scale=Math.min(1,pair/(340+420));return{x:box.left+box.width/2,y:box.top+box.height/2,minimum:340*scale,before:master.getBoundingClientRect().width,tableFit:table.scrollWidth<=table.clientWidth+1&&last.right<=tableBox.right+1};})()""")
                cdp.eval(f"""(()=>{{const divider=document.querySelector('.lex-list-detail-divider');divider.dispatchEvent(new PointerEvent('pointerdown',{{bubbles:true,cancelable:true,button:0,buttons:1,pointerId:7,clientX:{one['x']},clientY:{one['y']}}}));divider.dispatchEvent(new PointerEvent('pointermove',{{bubbles:true,buttons:1,pointerId:7,clientX:{one['x'] + 120},clientY:{one['y']}}}));divider.dispatchEvent(new PointerEvent('pointerup',{{bubbles:true,button:0,buttons:0,pointerId:7,clientX:{one['x'] + 120},clientY:{one['y']}}}));}})()""")
                one["after"] = cdp.eval("document.querySelector('.lex-barrelled-master').getBoundingClientRect().width")
                assert one["tableFit"] and one["after"] > one["before"] + 20, one
                cdp.eval("document.querySelector('.lex-list-detail-divider').dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true}))")
                double_click_width = cdp.eval("document.querySelector('.lex-barrelled-master').getBoundingClientRect().width")
                assert abs(double_click_width - one["after"]) < 2, {"one": one, "doubleClick": double_click_width}
                cdp.eval("document.querySelector('.lex-list-detail-divider').dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,button:2}))")
                reset_width = cdp.eval("document.querySelector('.lex-barrelled-master').getBoundingClientRect().width")
                assert abs(reset_width - one["before"]) < 2, {"one": one, "rightClick": reset_width}
                for expected in (2, 3):
                    cdp.eval("document.querySelector('[aria-label=\"Increase table barrels\"]').click()")
                    wait_eval(cdp, f"document.querySelector('.lex-barrel-count')?.textContent==='{expected}'", 30)
                wait_eval(cdp, "document.querySelectorAll('.lex-barrel-grid>.lex-list').length===3", 30)
                cdp.eval("new Promise(resolve=>setTimeout(resolve,750))", True)
                barrel_style = cdp.eval("""(()=>{const control=document.querySelector('.lex-barrel-control'),divider=control.parentElement,box=control.getBoundingClientRect(),rail=divider.getBoundingClientRect(),buttons=[...control.querySelectorAll('button')];return{parent:divider.className,opacity:getComputedStyle(control).opacity,transform:getComputedStyle(control).transform,railX:rail.left+rail.width/2,railY:rail.top+rail.height/2,centerDelta:Math.abs((box.top+box.bottom-rail.top-rail.bottom)/2),text:buttons.map(button=>button.textContent),shadows:buttons.map(button=>getComputedStyle(button).textShadow)}})()""")
                assert barrel_style["opacity"] == "1", barrel_style
                assert cdp.eval("document.querySelector('.lex-barrel-control').classList.contains('open')"), barrel_style
                assert "lex-panel-layout-divider" in barrel_style["parent"] and barrel_style["centerDelta"] < 2, barrel_style
                assert barrel_style["transform"] != "none", barrel_style
                assert barrel_style["text"] == ["", ""] and all(value == "none" for value in barrel_style["shadows"]), barrel_style
                cdp.eval("document.querySelector('.lex-barrel-control').dispatchEvent(new MouseEvent('mouseleave',{bubbles:false}))")
                wait_eval(cdp, "getComputedStyle(document.querySelector('.lex-barrel-control')).opacity==='0'", 10)
                cdp.eval("document.body.classList.add('lex-panel-layout-dragging')")
                wait_eval(cdp, "getComputedStyle(document.querySelector('.lex-barrel-control')).opacity==='1'", 10)
                cdp.eval("document.body.classList.remove('lex-panel-layout-dragging')")
                cdp.eval("new Promise(resolve=>setTimeout(resolve,500))", True)
                result = cdp.eval("""(()=>{
                  const root=document.querySelector('.lex-paged-list-detail');
                  const masters=[...root.querySelectorAll('.lex-barrel-grid>.lex-list')];
                  const allRows=filtered('magic',['name','id']);
                  const size=state.pageSizes.magic;
                  const visibleIds=masters.map(master=>[...master.querySelectorAll('.lex-list-row')].map(row=>Number(row.dataset.key)));
                  const expectedIds=Array.from({length:3},(_,barrel)=>allRows.slice(barrel*size,(barrel+1)*size).map(row=>Number(row.id)));
                  const second=masters[1].querySelector('.lex-list-row');
                  const masterPane=root.querySelector(':scope>.lex-barrelled-master');
                  const detailPane=(root.querySelector(':scope>.lex-detail')||root.querySelector(':scope>.lex-panel-layout,:scope>.lex-list-detail-pane,.lex-detail'));
                  const panelWidth=masterPane.getBoundingClientRect().width;
                  const pairWidth=panelWidth+detailPane.getBoundingClientRect().width;
                  const barrelMinimum=340*3+7*2,detailMinimum=420;
                  const minimumScale=Math.min(1,pairWidth/(barrelMinimum+detailMinimum));
                  const expectedPanelMinimum=Math.max(barrelMinimum*minimumScale,pairWidth*.66);
                  return {
                    barrels:masters.length,
                    headers:masters.map(master=>master.querySelectorAll('.lex-column-list-header').length),
                    visibleIds,expectedIds,
                    clicked:Number(second?.dataset.key),
                    pageSize:size,pages:Math.ceil(allRows.length/(size*3)),
                    pager:!!root.querySelector('.lex-pager'),
                    split:Number(root.querySelector('.lex-list-detail-divider')?.getAttribute('aria-valuenow')),
                    overflow:masters.map(master=>({scroll:master.scrollHeight,client:master.clientHeight,style:getComputedStyle(master).overflowY})),
                    horizontalFit:masters.map(master=>{const box=master.getBoundingClientRect(),last=master.querySelector('.lex-column-list-head-cell:last-child')?.getBoundingClientRect();return{scroll:master.scrollWidth,client:master.clientWidth,lastRight:last?.right,panelRight:box.right};}),
                    panelWidth,pairWidth,expectedPanelMinimum,
                    horizontal:document.documentElement.scrollWidth<=innerWidth+1,
                    errors:window.__testErrors,
                  };
                })()""")
                assert result["barrels"] == 3 and result["headers"] == [1, 1, 1], result
                assert result["visibleIds"] == result["expectedIds"], result
                assert result["pager"] == (result["pages"] > 1), result
                assert result["split"] >= 60, result
                assert result["panelWidth"] >= result["expectedPanelMinimum"] - 2, result
                assert all(value["style"] in {"hidden", "visible"} and value["scroll"] <= value["client"] + 1
                           for value in result["overflow"]), result
                assert all(value["scroll"] <= value["client"] + 1
                           and value["lastRight"] <= value["panelRight"] + 1
                           for value in result["horizontalFit"]), result
                assert result["horizontal"] and not result["errors"], result

                divider = cdp.eval("""(()=>{const box=document.querySelector('.lex-list-detail-divider').getBoundingClientRect();return{x:box.left+box.width/2,y:box.top+box.height/2};})()""")
                cdp.eval(f"""(()=>{{const divider=document.querySelector('.lex-list-detail-divider');divider.dispatchEvent(new PointerEvent('pointerdown',{{bubbles:true,cancelable:true,button:0,buttons:1,pointerId:8,clientX:{divider['x']},clientY:{divider['y']}}}));divider.dispatchEvent(new PointerEvent('pointermove',{{bubbles:true,buttons:1,pointerId:8,clientX:1,clientY:{divider['y']}}}));divider.dispatchEvent(new PointerEvent('pointerup',{{bubbles:true,button:0,buttons:0,pointerId:8,clientX:1,clientY:{divider['y']}}}));}})()""")
                clamped = cdp.eval("document.querySelector('.lex-barrelled-master').getBoundingClientRect().width")
                assert clamped >= result["expectedPanelMinimum"] - 2, {"before": result, "afterDrag": clamped}

                clicked_after_resize = cdp.eval("(()=>{const row=document.querySelectorAll('.lex-barrel-grid>.lex-list')[1].querySelector('.lex-list-row'),key=Number(row.dataset.key);row.click();return key})()")
                wait_eval(cdp, f"state.selected.magic==={clicked_after_resize}&&document.querySelector('.lex-list-row.selected')?.dataset.key==='{clicked_after_resize}'", 30)

                cdp.eval("navigate('items')")
                wait_eval(cdp, "state.tab==='items'&&document.querySelector('.lex-barrel-count')?.textContent==='1'", 30)
                cdp.eval("navigate('magic')")
                wait_eval(cdp, "state.tab==='magic'&&document.querySelector('.lex-barrel-count')?.textContent==='3'", 30)
                cdp.eval("document.body.classList.add('lex-panel-layout-dragging')")
                screenshot = cdp.call("Page.captureScreenshot", {
                    "format": "png", "captureBeyondViewport": False, "fromSurface": True,
                })
                (output_dir / f"github-44-n-barrelled-magic-{width}x{height}.png").write_bytes(
                    base64.b64decode(screenshot["data"]))
                cdp.eval("document.body.classList.remove('lex-panel-layout-dragging')")
                for _unused in range(6):
                    disabled = cdp.eval("document.querySelector('[aria-label=\"Increase table barrels\"]')?.disabled")
                    if disabled:
                        break
                    cdp.eval("document.querySelector('[aria-label=\"Increase table barrels\"]').click()")
                    wait_eval(cdp, "!!document.querySelector('.lex-barrel-count')", 30)
                # Search lives in the bottom command bar. With one page, the
                # unused center controls disappear and search gets that space.
                one_page_bar = cdp.eval("""(()=>{const pager=document.querySelector('.lex-pager'),search=pager?.querySelector('.lex-pager-search'),box=pager?.getBoundingClientRect(),searchBox=search?.getBoundingClientRect();return{pager:!!pager,single:pager?.classList.contains('single-page'),search:!!search,controls:pager?.querySelectorAll('.lex-pager-controls').length||0,searchRatio:box&&searchBox?searchBox.width/box.width:0}})()""")
                assert one_page_bar["pager"] and one_page_bar["single"] and one_page_bar["search"], one_page_bar
                assert one_page_bar["controls"] == 0 and one_page_bar["searchRatio"] > .5, one_page_bar
                print(width, height, result)
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
