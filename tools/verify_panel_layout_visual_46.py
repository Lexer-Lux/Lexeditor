"""Rendered interaction proof for the shared multi-panel composer (GitHub #46)."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RDR2_ROOT = Path(r"C:\RDR2Mod")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(RDR2_ROOT / "tools" / "reverse-engineering"))

from games.ff8.plugin import FF8Session  # noqa: E402
from games.rdr2.plugin import Rdr2Session  # noqa: E402
from games.blank.plugin import BlankSession  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
OUTPUT = ROOT / "worklog" / "issues" / "rendered"


def browser_session():
    port = free_port()
    profile = tempfile.TemporaryDirectory(prefix="lexeditor-panel-layout-edge-", ignore_cleanup_errors=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = subprocess.Popen([
        str(EDGE), "--headless=new", "--no-first-run", "--no-default-browser-check",
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
    return profile, browser, cdp


def close_browser(profile, browser, cdp):
    if cdp:
        cdp.close()
    if browser:
        browser.terminate()
        browser.wait(timeout=10)
    profile.cleanup()


def screenshot(cdp: Cdp, name: str) -> Path:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = cdp.call("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": False, "fromSurface": True,
    })
    path = OUTPUT / name
    path.write_bytes(base64.b64decode(result["data"]))
    return path


def check_layout(cdp: Cdp, selector: str, panel_selector: str, key: str) -> dict:
    return cdp.eval(f"""(()=>{{
      const root=document.querySelector({selector!r});
      const panels=[...root.querySelectorAll(':scope > {panel_selector}')];
      const dividers=[...root.querySelectorAll(':scope > .lex-panel-layout-divider')];
      const before=panels.map(panel=>panel.getBoundingClientRect().width);
      dividers[0].dispatchEvent(new KeyboardEvent('keydown',{{key:'ArrowRight',bubbles:true}}));
      const after=panels.map(panel=>panel.getBoundingClientRect().width);
      return {{panels:panels.length,dividers:dividers.length,before,after,
        stored:JSON.parse(localStorage.getItem({key!r})||'null'),
        errors:window.__testErrors}};
    }})()""")


def drag_second_divider(cdp: Cdp, selector: str, panel_selector: str) -> dict:
    geometry = cdp.eval(f"""(()=>{{const root=document.querySelector({selector!r}),
      divider=root.querySelectorAll(':scope>.lex-panel-layout-divider')[1],
      box=divider.getBoundingClientRect();return{{x:box.left+box.width/2,y:box.top+box.height/2,
      before:[...root.querySelectorAll(':scope>{panel_selector}')].map(node=>node.getBoundingClientRect().width)}};}})()""")
    cdp.call("Input.dispatchMouseEvent", {
        "type": "mousePressed", "x": geometry["x"], "y": geometry["y"],
        "button": "left", "buttons": 1, "clickCount": 1,
    })
    cdp.call("Input.dispatchMouseEvent", {
        "type": "mouseMoved", "x": geometry["x"] + 24, "y": geometry["y"],
        "button": "left", "buttons": 1,
    })
    cdp.call("Input.dispatchMouseEvent", {
        "type": "mouseReleased", "x": geometry["x"] + 24, "y": geometry["y"],
        "button": "left", "buttons": 0, "clickCount": 1,
    })
    geometry["after"] = cdp.eval(f"""(()=>{{const root=document.querySelector({selector!r});return [...root.querySelectorAll(':scope>{panel_selector}')].map(node=>node.getBoundingClientRect().width);}})()""")
    return geometry


def verify_ff8() -> dict:
    project = tempfile.TemporaryDirectory(prefix="lexeditor-panel-layout-ff8-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            cdp.eval("navigate('gfs')")
            wait_eval(cdp, "document.querySelectorAll('.gf-three-panel>.gf-panel').length===3", 30)
            result = check_layout(cdp, ".gf-three-panel", ".gf-panel",
                                  "lexeditor:panel-layout:ff8-gfs")
            assert result["panels"] == 3 and result["dividers"] == 2, result
            assert result["after"][0] > result["before"][0], result
            assert result["after"][1] < result["before"][1], result
            assert abs(result["after"][2] - result["before"][2]) < 2, result
            assert isinstance(result["stored"], list) and len(result["stored"]) == 3, result
            pointer = drag_second_divider(cdp, ".gf-three-panel", ".gf-panel")
            assert abs(pointer["after"][0] - pointer["before"][0]) < 2, pointer
            assert pointer["after"][1] > pointer["before"][1], pointer
            assert pointer["after"][2] < pointer["before"][2], pointer
            result["pointer"] = pointer
            result["screenshot"] = str(screenshot(cdp, "github-46-ff8-resizable-panels.png"))
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 900, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            narrow = cdp.eval("""(()=>{const root=document.querySelector('.gf-three-panel'),
              panels=[...root.querySelectorAll(':scope>.gf-panel')],
              dividers=[...root.querySelectorAll(':scope>.lex-panel-layout-divider')];return{
                dividerDisplays:dividers.map(node=>getComputedStyle(node).display),
                tops:panels.map(node=>node.getBoundingClientRect().top)};})()""")
            assert narrow["dividerDisplays"] == ["none", "none"], narrow
            assert narrow["tops"] == sorted(narrow["tops"]), narrow
            result["narrow"] = narrow
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.eval("navigate('items')")
            wait_eval(cdp, "document.querySelector('.lex-list-detail')", 30)
            legacy = cdp.eval("""(()=>{const root=document.querySelector('.lex-list-detail');return{
              panels:root.querySelectorAll(':scope>.lex-panel-layout-pane').length,
              dividers:root.querySelectorAll(':scope>.lex-panel-layout-divider').length};})()""")
            assert legacy == {"panels": 2, "dividers": 1}, legacy
            stable_selection = cdp.eval("""(()=>new Promise(resolve=>{const table=document.querySelector('.lex-barrel-grid .lex-column-list'),rows=[...table.querySelectorAll('.lex-column-list-row')];window.__stableTable=table;rows[1].click();requestAnimationFrame(()=>requestAnimationFrame(()=>resolve({
              same:window.__stableTable===document.querySelector('.lex-barrel-grid .lex-column-list'),
              selected:[...document.querySelectorAll('.lex-barrel-grid .lex-column-list-row.selected')].length,
              key:document.querySelector('.lex-barrel-grid .lex-column-list-row.selected')?.dataset.key,
              errors:window.__testErrors})));}))()""", True)
            assert stable_selection["same"] and stable_selection["selected"] == 1, stable_selection
            assert not stable_selection["errors"], stable_selection
            result["stableSelection"] = stable_selection
            result["legacy"] = legacy
            assert not result["errors"], result
            return result
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        project.cleanup()


def verify_blank() -> dict:
    profile = browser = cdp = None
    try:
        profile, browser, cdp = browser_session()
        with BlankSession() as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "document.body.dataset.lexPlugin==='blank'&&!!document.querySelector('.blank-layout')", 30)
            gallery = cdp.eval("""(()=>({panels:document.querySelectorAll('.blank-layout>.lex-panel-layout-pane').length,dividers:document.querySelectorAll('.blank-layout>.lex-panel-layout-divider').length,fields:document.querySelectorAll('.lex-detail-field').length,errors:window.__lexErrors||[]}))()""")
            assert gallery["panels"] == 1 and gallery["dividers"] == 0 and gallery["fields"] >= 11, gallery
            special_tab = cdp.eval("""(()=>{const normal=document.querySelector('nav button[data-tab="editable"]'),tweaks=document.querySelector('nav button[data-tab="tweaks"]');return{special:tweaks.classList.contains('lex-settings-tab'),gap:tweaks.getBoundingClientRect().left-normal.getBoundingClientRect().right,normal:getComputedStyle(normal).backgroundColor,tweaks:getComputedStyle(tweaks).backgroundColor}})()""")
            assert special_tab["special"] and special_tab["gap"] >= 9 and special_tab["normal"] != special_tab["tweaks"], special_tab
            stacks = cdp.eval("""(()=>[...document.querySelectorAll('.lex-detail-field')].filter(row=>/^\\d-REF VALUE$/.test(row.querySelector('.lex-detail-field-label')?.textContent.trim()||'')).map(row=>{const rowBox=row.getBoundingClientRect(),strip=row.querySelector('.lex-reference-values'),buttons=[...strip.querySelectorAll('.lex-reference-value')],boxes=buttons.map(button=>button.getBoundingClientRect());return{label:row.querySelector('.lex-detail-field-label').textContent.trim(),height:rowBox.height,count:Number(strip.dataset.referenceCount),indexes:buttons.map(button=>Number(button.dataset.referenceIndex)),tags:buttons.map(button=>button.querySelector('.lex-reference-tag').textContent.trim()),colors:buttons.map(button=>getComputedStyle(button.querySelector('.lex-reference-tag')).color),contained:boxes.every(box=>box.top>=rowBox.top-1&&box.bottom<=rowBox.bottom+1),vertical:boxes.every((box,index)=>index===0||(box.top>boxes[index-1].top&&Math.abs(box.left-boxes[0].left)<2))}}))()""")
            assert [entry["label"] for entry in stacks] == ["1-REF VALUE", "2-REF VALUE", "3-REF VALUE"], stacks
            expected_colors = ["rgb(98, 183, 79)", "rgb(214, 75, 75)", "rgb(79, 143, 232)", "rgb(214, 184, 63)"]
            for expected_count, entry in enumerate(stacks, 1):
                assert entry["count"] == expected_count and entry["vertical"], entry
                assert entry["indexes"] == list(range(expected_count)), entry
                assert entry["tags"] == ["V", "R1", "R2"][:expected_count], entry
                assert entry["colors"] == expected_colors[:expected_count], entry
                assert entry["contained"], entry
            assert max(entry["height"] for entry in stacks) - min(entry["height"] for entry in stacks) <= 1, stacks
            overflow = cdp.eval("""(()=>{try{LexeditorUI.referenceDisplay({current:99,sources:[0,1,2,3,4].map((value,index)=>({name:`Source ${index}`,value}))});return null}catch(error){return{name:error.name,message:error.message}}})()""")
            assert overflow and overflow["name"] == "RangeError" and "at most two reference mods" in overflow["message"], overflow
            acceptance = cdp.eval("""(()=>new Promise(resolve=>{
              const panel=document.querySelector('.blank-detail'),head=panel.querySelector('.lex-detail-panel-heading'),body=panel.querySelector('.lex-detail-panel-body');
              const pb=panel.getBoundingClientRect(),hb=head.getBoundingClientRect(),bb=body.getBoundingClientRect();
              const number=[...document.querySelectorAll('.lex-detail-field')].find(row=>row.querySelector('.lex-detail-field-label')?.textContent.includes('NUMBER'));
              const readonly=[...document.querySelectorAll('.lex-detail-field')].find(row=>row.querySelector('.lex-detail-field-label')?.textContent.trim()==='READ ONLY');
              const input=number.querySelector('input[type=number]'),range=number.querySelector('.lex-field-type-range');
              input.focus();
              const help=document.querySelector('.lex-info-help');help.dispatchEvent(new PointerEvent('pointerenter',{bubbles:true}));
              const popup=document.querySelector('.lex-help-popover');
              const command=getComputedStyle(document.querySelector('.lex-shell-command-row')).backgroundColor;
              const tabs=getComputedStyle(document.querySelector('.lex-nav-frame')).backgroundColor;
              const save=document.querySelector('#global-save').getBoundingClientRect(),game=document.querySelector('#global-game-process').getBoundingClientRect(),commandBox=document.querySelector('.lex-shell-command-row').getBoundingClientRect(),closeBox=document.querySelector('[data-window-action="close"]').getBoundingClientRect();
              document.querySelector('.lex-project-select').click();
              const projectNames=[...document.querySelectorAll('.lex-project-menu-name')].map(node=>node.textContent.trim());
              const projectModes=[...document.querySelectorAll('.lex-project-source-mode')].map(node=>node.textContent.trim());
              const projectStatuses=[...document.querySelectorAll('.lex-project-source-status')].map(node=>node.textContent.trim());
              const rail=number.querySelector('.lex-field-type-rail'),lock=readonly.querySelector('.lex-field-readonly-lock'),typeName=readonly.querySelector('.lex-field-type-name'),panelIcon=head.querySelector('.lex-detail-panel-icon'),panelId=head.querySelector('.lex-detail-panel-id'),railBox=rail.getBoundingClientRect(),fieldBox=number.getBoundingClientRect(),sectionBox=number.closest('.lex-detail-section').getBoundingClientRect(),rangeBox=range.getBoundingClientRect(),headIconBox=panelIcon.getBoundingClientRect(),headIdBox=panelId.getBoundingClientRect(),lockBox=lock.getBoundingClientRect(),typeBox=typeName.getBoundingClientRect();
              setTimeout(()=>resolve({headRatio:hb.height/pb.height,bodyRatio:bb.height/pb.height,type:number.dataset.lexType,
                readonlyType:readonly.dataset.lexType,readonly:readonly.dataset.lexReadonly,readonlyRail:readonly.querySelector('.lex-field-type-name')?.textContent,locks:readonly.querySelectorAll('.lex-field-readonly-lock').length,
                range:range?.textContent,rangeOpacity:getComputedStyle(range).opacity,typeAndRangeVisible:[number.querySelector('.lex-field-type-name'),number.querySelector('.lex-field-type-range')].filter(node=>node&&getComputedStyle(node).display!=='none'&&parseFloat(getComputedStyle(node).opacity)>.9).length===2,typeRotation:getComputedStyle(number.querySelector('.lex-field-type-name')).transform,typeWritingMode:getComputedStyle(number.querySelector('.lex-field-type-name')).writingMode,rail:{left:railBox.left,top:railBox.top,bottom:railBox.bottom,transform:getComputedStyle(rail).transform},field:{left:fieldBox.left,top:fieldBox.top,bottom:fieldBox.bottom},section:{left:sectionBox.left},rangeBox:{left:rangeBox.left,right:rangeBox.right},icon:{height:headIconBox.height,headHeight:hb.height},idCenter:(headIdBox.top+headIdBox.bottom)/2,headCenter:(hb.top+hb.bottom)/2,lockAlignment:{rotated:getComputedStyle(lock).transform.includes('matrix')&&!/^matrix\\(1, 0, 0, 1/.test(getComputedStyle(lock).transform),boxRight:(lock.parentElement.querySelector('input,select,textarea')||lock.parentElement).getBoundingClientRect().right,boxLeft:(lock.parentElement.querySelector('input,select,textarea')||lock.parentElement).getBoundingClientRect().left,lockRight:lockBox.right,lockLeft:lockBox.left},helpTitle:help.hasAttribute('title'),
                popup:popup?.textContent,command,tabs,save:{width:save.width,height:save.height},game:{width:game.width,height:game.height},
                windowInset:commandBox.right-closeBox.right,projectHidden:document.querySelector('.lex-project-control').hidden,projectNames,projectModes,projectStatuses}),260);
            }))()""", True)
            assert acceptance["headRatio"] + acceptance["bodyRatio"] >= .97, acceptance
            assert acceptance["bodyRatio"] >= .6, acceptance
            assert .09 <= acceptance["headRatio"] <= .11, acceptance
            assert acceptance["type"] == "INT" and acceptance["range"] == "(0-255)", acceptance
            assert acceptance["readonlyType"] == "STRING", acceptance
            assert acceptance["readonlyRail"] == "STR", acceptance
            assert acceptance["readonly"] == "true" and acceptance["locks"] == 1, acceptance
            assert float(acceptance["rangeOpacity"]) >= .99 and not acceptance["typeAndRangeVisible"], acceptance
            assert acceptance["typeWritingMode"] == "horizontal-tb", acceptance
            assert acceptance["typeRotation"].startswith("matrix(0, -1, 1, 0"), acceptance
            assert acceptance["rail"]["left"] >= acceptance["section"]["left"] - 1, acceptance
            assert acceptance["rail"]["top"] >= acceptance["field"]["top"] - 1 and acceptance["rail"]["bottom"] <= acceptance["field"]["bottom"] + 1, acceptance
            assert acceptance["rangeBox"]["left"] >= acceptance["section"]["left"] - 1, acceptance
            assert acceptance["icon"]["height"] >= acceptance["icon"]["headHeight"] - 9, acceptance
            assert abs(acceptance["idCenter"] - acceptance["headCenter"]) <= 1, acceptance
            assert not acceptance["lockAlignment"]["rotated"], acceptance
            assert (acceptance["lockAlignment"]["lockLeft"]
                    >= acceptance["lockAlignment"]["boxLeft"]), acceptance
            assert 0 < (acceptance["lockAlignment"]["boxRight"]
                        - acceptance["lockAlignment"]["lockRight"]) <= 12, acceptance
            assert not acceptance["helpTitle"] and acceptance["popup"] == "A normal editable text value.", acceptance
            assert acceptance["command"] != acceptance["tabs"], acceptance
            assert acceptance["save"] == acceptance["game"] == {"width": 38, "height": 38}, acceptance
            assert 5 <= acceptance["windowInset"] <= 12, acceptance
            assert not acceptance["projectHidden"] and acceptance["projectNames"] == ["Vanilla", "My Mod"], acceptance
            assert acceptance["projectModes"] == ["🔒", "🔒"], acceptance
            assert acceptance["projectStatuses"] == ["✓", "✓"], acceptance
            pristine_layout = cdp.eval("""(()=>{const rows=[...document.querySelectorAll('.lex-detail-field')],number=rows.find(row=>row.querySelector('.lex-detail-field-label')?.textContent.includes('NUMBER')),selectRow=rows.find(row=>row.querySelector('.lex-detail-field-label')?.textContent.trim()==='SELECT'),numberRoot=number.querySelector('.lex-source-control-internal'),numberInput=numberRoot.querySelector('input'),unit=numberRoot.querySelector('.lex-unit'),selectRoot=selectRow.querySelector('.lex-source-control-internal'),select=selectRoot.querySelector('select'),reference=selectRoot.querySelector('.lex-reference-value'),box=node=>{const r=node.getBoundingClientRect();return{left:r.left,right:r.right}};return{numberNoReference:numberRoot.classList.contains('no-reference'),numberInput:box(numberInput),unit:box(unit),select:box(select),selectReference:box(reference)}})()""")
            assert pristine_layout["numberNoReference"], pristine_layout
            assert 3 <= pristine_layout["numberInput"]["right"] - pristine_layout["unit"]["right"] <= 12, pristine_layout
            assert pristine_layout["selectReference"]["right"] <= pristine_layout["select"]["right"] - 18, pristine_layout
            integer = cdp.eval("""(()=>{const row=[...document.querySelectorAll('.lex-detail-field')].find(row=>row.querySelector('.lex-detail-field-label')?.textContent.includes('NUMBER')),input=row.querySelector('input[type=number]');input.value='25.5';input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));return{value:input.value,model:demo.value,dirty:dirtyCount()};})()""")
            assert integer == {"value": "25", "model": 25, "dirty": 0}, integer
            edited = cdp.eval("""(()=>{const row=[...document.querySelectorAll('.lex-detail-field')].find(row=>row.querySelector('.lex-detail-field-label')?.textContent.includes('NUMBER')),input=row.querySelector('input[type=number]');input.value='26';input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));return{value:input.value,model:demo.value,dirty:dirtyCount(),reference:row.querySelector('.lex-reference-value')?.textContent.trim(),saveDisabled:document.querySelector('#global-save').disabled};})()""")
            assert edited["value"] == "26" and edited["model"] == 26 and edited["dirty"] == 1, edited
            assert edited["reference"] == "V25" and not edited["saveDisabled"], edited
            unit_layout = cdp.eval("""(()=>{const row=[...document.querySelectorAll('.lex-detail-field')].find(row=>row.querySelector('.lex-detail-field-label')?.textContent.includes('NUMBER')),root=row.querySelector('.lex-source-control-internal'),input=root.querySelector('input[type=number]'),unit=root.querySelector('.lex-unit'),reference=root.querySelector('.lex-reference-value');const box=node=>{const value=node.getBoundingClientRect();return{left:value.left,right:value.right,top:value.top,bottom:value.bottom,width:value.width}};return{root:box(root),input:box(input),unit:box(unit),reference:box(reference),paddingRight:getComputedStyle(input).paddingRight};})()""")
            assert unit_layout["unit"]["right"] <= unit_layout["input"]["right"] - 3, unit_layout
            assert unit_layout["reference"]["left"] >= unit_layout["unit"]["right"] + 3, unit_layout
            assert 3 <= unit_layout["input"]["right"] - unit_layout["reference"]["right"] <= 8, unit_layout
            cdp.eval("document.querySelector('[data-tab=\"two\"]').click()")
            wait_eval(cdp, "document.querySelector('[data-tab=\"two\"]').classList.contains('active')", 10)
            cdp.eval("document.querySelector('[data-tab=\"one\"]').click()")
            wait_eval(cdp, "document.querySelector('[data-tab=\"one\"]').classList.contains('active')", 10)
            persisted_value = cdp.eval("[...document.querySelectorAll('.lex-detail-field')].find(row=>row.querySelector('.lex-detail-field-label')?.textContent.includes('NUMBER'))?.querySelector('input[type=number]')?.value")
            assert persisted_value == "26", persisted_value
            one_screenshot = str(screenshot(cdp, "github-46-blank-game-one-panel.png"))
            cdp.eval("document.querySelector('[data-tab=\"two\"]').click()")
            wait_eval(cdp, "document.querySelector('[data-tab=\"two\"]').classList.contains('active')&&document.querySelectorAll('.blank-layout>.lex-panel-layout-pane').length===2", 10)
            result = check_layout(cdp, ".blank-layout", ".lex-panel-layout-pane",
                                  "lexeditor:panel-layout:blank-two")
            assert result["panels"] == 2 and result["dividers"] == 1, result
            assert result["after"][0] > result["before"][0], result
            table_heading = cdp.eval("""(()=>{const head=document.querySelector('.lex-column-list-header'),cell=head.querySelector('.lex-column-list-head-cell'),row=document.querySelector('.lex-column-list-row'),style=getComputedStyle(cell);return{height:head.getBoundingClientRect().height,rowHeight:row.getBoundingClientRect().height,fontSize:parseFloat(style.fontSize),bodyFontSize:parseFloat(getComputedStyle(row).fontSize),fontWeight:Number(style.fontWeight)}})()""")
            assert table_heading["height"] <= table_heading["rowHeight"], table_heading
            assert 15.5 <= table_heading["fontSize"] <= 17 and table_heading["fontWeight"] >= 700, table_heading
            assert result["after"][1] < result["before"][1], result
            assert not result["errors"], result
            defaults = cdp.eval("""(()=>{const style=getComputedStyle(document.documentElement),title=document.querySelector('.lex-detail-section-title'),initial=document.querySelector('.lex-column-list-head-cell[aria-sort]:not([aria-sort="none"])'),indicator=initial?.querySelector('.lex-sort-indicator'),indicatorBox=indicator?.getBoundingClientRect(),cellBox=initial?.getBoundingClientRect();return{background:style.getPropertyValue('--lex-bg').trim(),panel:style.getPropertyValue('--lex-panel').trim(),titlePosition:getComputedStyle(title).position,titleTransform:getComputedStyle(title).transform,sortKey:initial?.dataset.columnKey,sortText:indicator?.textContent.trim(),sortPosition:getComputedStyle(indicator).position,sortVisible:indicatorBox.width>0&&indicatorBox.left>=cellBox.left&&indicatorBox.right<=cellBox.right,order:[...document.querySelectorAll('.lex-column-list-row')].map(node=>node.textContent)}})()""")
            assert defaults["background"] == "#f7f8f9" and defaults["panel"] == "#ffffff", defaults
            assert defaults["titlePosition"] == "static" and defaults["titleTransform"] == "none", defaults
            assert defaults["sortKey"] == "name" and defaults["sortText"] in {"▲", "▼"}, defaults
            assert defaults["sortPosition"] == "static" and defaults["sortVisible"], defaults
            cdp.eval("document.querySelector('.lex-column-list-head-cell[data-column-key=\"value\"] .lex-column-sort').click()")
            changed = cdp.eval("""(()=>({key:document.querySelector('.lex-column-list-head-cell[aria-sort]:not([aria-sort="none"])')?.dataset.columnKey,order:[...document.querySelectorAll('.lex-column-list-row')].map(node=>node.textContent)}))()""")
            assert changed["key"] == "value", changed
            cdp.eval("document.querySelector('.lex-column-list-row').click()")
            persisted = cdp.eval("document.querySelector('.lex-column-list-head-cell[aria-sort]:not([aria-sort=\"none\"])')?.dataset.columnKey")
            assert persisted == "value", persisted
            two_screenshot = str(screenshot(cdp, "github-46-blank-game-two-panels.png"))
            cdp.eval("document.querySelector('[data-tab=\"editable\"]').click()")
            wait_eval(cdp, "document.querySelector('[data-tab=\"editable\"]').classList.contains('active')&&!!document.querySelector('.blank-editable-table')", 10)
            editable = cdp.eval("""(()=>{const input=document.querySelector('.blank-editable-table input[type=text]'),select=document.querySelector('.blank-editable-table select'),table=input.closest('.lex-column-list'),cell=input.closest('.lex-column-list-cell'),disabledRow=table.querySelector('.lex-row-disabled'),beforeBackground=getComputedStyle(input).backgroundColor,beforeBorder=getComputedStyle(input).borderTopColor;const result={tableClass:table.className,matches:input.matches('.lex-editable-table input:focus'),beforeBackground,beforeBorder,inputWidth:input.getBoundingClientRect().width,cellWidth:cell.getBoundingClientRect().width,selectWidth:select.getBoundingClientRect().width,selectCellWidth:select.closest('.lex-column-list-cell').getBoundingClientRect().width,firstColumn:table.querySelector('.lex-column-list-head-cell')?.dataset.columnKey,disabledOpacity:disabledRow?Math.max(...[...disabledRow.querySelectorAll('.lex-column-list-cell:not([data-column-key="enabled"]) > *')].map(node=>Number(getComputedStyle(node).opacity)),0):1,disabledControlsEditable:disabledRow?[...disabledRow.querySelectorAll('input,select,textarea,button')].every(control=>!control.disabled):false};input.focus();result.matches=input.matches('.lex-editable-table input:focus');result.afterBackground=getComputedStyle(input).backgroundColor;result.focused=document.activeElement===input;return result})()""")
            assert editable["beforeBackground"] == "rgba(0, 0, 0, 0)" and editable["focused"], editable
            assert editable["afterBackground"] != editable["beforeBackground"], editable
            assert editable["inputWidth"] >= editable["cellWidth"] - 75 and editable["selectWidth"] >= editable["selectCellWidth"] - 75, editable
            assert editable["firstColumn"] == "enabled" and editable["disabledOpacity"] < .7 and editable["disabledControlsEditable"], editable
            sort_point = cdp.eval("""(()=>{const head=document.querySelector('.blank-editable-table [data-column-key="value"]'),box=head.querySelector('.lex-column-sort').getBoundingClientRect();return{x:box.left+box.width/2,y:box.top+box.height/2,before:[...document.querySelectorAll('.blank-editable-table .lex-column-list-row')].map(row=>row.dataset.key),beforeAria:head.getAttribute('aria-sort')}})()""")
            cdp.call("Input.dispatchMouseEvent", {"type":"mousePressed","x":sort_point["x"],"y":sort_point["y"],"button":"left","buttons":1,"clickCount":1})
            cdp.call("Input.dispatchMouseEvent", {"type":"mouseReleased","x":sort_point["x"],"y":sort_point["y"],"button":"left","buttons":0,"clickCount":1})
            sorted_rows = cdp.eval("""(()=>({after:[...document.querySelectorAll('.blank-editable-table .lex-column-list-row')].map(row=>row.dataset.key),aria:document.querySelector('.blank-editable-table [data-column-key="value"]')?.getAttribute('aria-sort')}))()""")
            assert sorted_rows["aria"] in {"ascending", "descending"} and sorted_rows["aria"] != sort_point["beforeAria"], sorted_rows
            editable["realMouseSort"] = sorted_rows
            reorder = cdp.eval("""(()=>{const header=document.querySelector('.blank-editable-table .lex-column-list-header'),from=header.querySelector('[data-column-key="name"]'),to=header.querySelector('[data-column-key="value"]'),a=from.getBoundingClientRect(),b=to.getBoundingClientRect();from.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,pointerId:19,clientX:a.left+a.width/2,clientY:a.top+a.height/2}));to.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,button:0,pointerId:19,clientX:b.left+b.width/2,clientY:b.top+b.height/2}));to.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,button:0,pointerId:19,clientX:b.left+b.width/2,clientY:b.top+b.height/2}));return{draggable:[...header.children].every(cell=>cell.draggable),order:[...document.querySelectorAll('.blank-editable-table .lex-column-list-head-cell')].map(cell=>cell.dataset.columnKey)}})()""")
            assert not reorder["draggable"] and reorder["order"].index("name") == reorder["order"].index("value") - 1, reorder
            editable_screenshot = str(screenshot(cdp, "github-46-blank-game-editable-table.png"))
            cdp.eval("document.querySelector('[data-tab=\"three\"]').click()")
            wait_eval(cdp, "document.querySelector('[data-tab=\"three\"]').classList.contains('active')&&document.querySelectorAll('.blank-layout>.lex-panel-layout-pane').length===3", 10)
            three = cdp.eval("""(()=>{const rows=[...document.querySelectorAll('.blank-detail .lex-detail-field')].filter(row=>row.querySelector('.lex-column-pin')),pins=rows.map(row=>{const root=row.querySelector('.lex-source-control'),target=root.querySelector('input,select'),pin=root.querySelector('.lex-column-pin'),a=target.getBoundingClientRect(),p=pin.getBoundingClientRect(),outward=target.type==='checkbox',tip={x:p.left+p.width*3.71/24,y:p.top+p.height*21.71/24},wanted={x:a.right+(outward?a.height*.1:-a.height*.1),y:a.top+(outward?-a.height*.1:a.height*.1)};return{kind:target.type||target.tagName.toLowerCase(),size:p.width,dx:tip.x-wanted.x,dy:tip.y-wanted.y}});return{panels:document.querySelectorAll('.blank-layout>.lex-panel-layout-pane').length,dividers:document.querySelectorAll('.blank-layout>.lex-panel-layout-divider').length,statuses:document.querySelectorAll('.lex-integration-status').length,pins}})()""")
            assert three["panels"] == 3 and three["dividers"] == 2 and three["statuses"] == 3, three
            assert len(three["pins"]) == 4 and all(pin["size"] >= 13 for pin in three["pins"]), three
            assert all(abs(pin["dx"]) <= 1 and abs(pin["dy"]) <= 1 for pin in three["pins"]), three
            three_screenshot = str(screenshot(cdp, "github-46-blank-game-three-panels.png"))
            cdp.eval("document.querySelector('[data-tab=\"subtabs\"]').click()")
            wait_eval(cdp, "document.querySelector('[data-tab=\"subtabs\"]').classList.contains('active')&&!!document.querySelector('.lex-subtab-bar')", 10)
            subtabs = cdp.eval("""(()=>({panels:document.querySelectorAll('.blank-layout>.lex-panel-layout-pane').length,dividers:document.querySelectorAll('.blank-layout>.lex-panel-layout-divider').length,tabs:document.querySelectorAll('.lex-subtab-button').length,active:(node=>node?(node=>[...node.childNodes].filter(part=>!(part.nodeType===1&&part.classList.contains('lex-tab-shortcut'))).map(part=>part.textContent).join('').trim())(node):null)(document.querySelector('.lex-subtab-button.active'))}))()""")
            assert subtabs == {"panels": 1, "dividers": 0, "tabs": 3, "active": "Controls"}, subtabs
            cdp.eval("[...document.querySelectorAll('.lex-subtab-button')].find(node=>(node=>[...node.childNodes].filter(part=>!(part.nodeType===1&&part.classList.contains('lex-tab-shortcut'))).map(part=>part.textContent).join('').trim())(node)==='References').click()")
            wait_eval(cdp, "(node=>[...node.childNodes].filter(part=>!(part.nodeType===1&&part.classList.contains('lex-tab-shortcut'))).map(part=>part.textContent).join('').trim())(document.querySelector('.lex-subtab-button.active'))==='References'", 10)
            subtabs["changed"] = cdp.eval("document.querySelector('.lex-detail-section-title')?.textContent")
            assert subtabs["changed"] == "REFERENCE VALUES", subtabs
            subtab_screenshot = str(screenshot(cdp, "github-46-blank-game-subtabs.png"))
            result["defaults"] = defaults
            result["sort"] = changed
            result["gallery"] = gallery
            result["referenceStacks"] = stacks
            result["referenceOverflow"] = overflow
            result["acceptance"] = acceptance
            result["integer"] = integer
            result["edited"] = edited
            result["unitLayout"] = unit_layout
            result["editable"] = editable
            result["three"] = three
            result["subtabs"] = subtabs
            result["screenshots"] = [one_screenshot, two_screenshot, editable_screenshot, three_screenshot, subtab_screenshot]
            return result
    finally:
        if profile:
            close_browser(profile, browser, cdp)


def verify_rdr2() -> dict:
    isolated = tempfile.TemporaryDirectory(prefix="lexeditor-panel-layout-rdr2-", ignore_cleanup_errors=True)
    profile = browser = cdp = None
    try:
        temp_ini = Path(isolated.name) / "GameplayTweaks.ini"
        shutil.copy2(RDR2_ROOT / "GameplayTweaks" / "GameplayTweaks.ini", temp_ini)
        profile, browser, cdp = browser_session()
        with Rdr2Session({
            "LEXEDITOR_GAMEPLAY_INI": str(temp_ini),
            "RDR2_GAME_ROOT": str(Path(isolated.name) / "empty-game-root"),
        }) as session:
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting&&document.body.dataset.lexPlugin==='rdr2'", 90)
            record_layouts = {}
            for tab in ("items", "crafting", "effects", "weapons"):
                cdp.eval(f"navigate({tab!r})")
                wait_eval(cdp, f"state.tab==={tab!r}&&document.querySelector('.lootsplit.lex-panel-layout')", 60)
                geometry = cdp.eval("""(()=>{const root=document.querySelector('.lootsplit.lex-panel-layout'),master=root.querySelector(':scope>.lex-barrelled-master'),divider=root.querySelector(':scope>.lex-panel-layout-divider'),detail=divider?.nextElementSibling,rb=root.getBoundingClientRect(),mb=master?.getBoundingClientRect(),db=detail?.getBoundingClientRect();return{root:{left:rb.left,right:rb.right,top:rb.top,bottom:rb.bottom},master:{left:mb?.left,right:mb?.right,top:mb?.top,bottom:mb?.bottom},detail:{left:db?.left,right:db?.right,top:db?.top,bottom:db?.bottom},divider:!!divider};})()""")
                assert geometry["divider"], (tab, geometry)
                assert abs(geometry["master"]["top"] - geometry["detail"]["top"]) < 2, (tab, geometry)
                assert geometry["detail"]["left"] > geometry["master"]["right"], (tab, geometry)
                assert geometry["detail"]["right"] >= geometry["root"]["right"] - 2, (tab, geometry)
                record_layouts[tab] = geometry
            cdp.eval("navigate('items')")
            wait_eval(cdp, "state.tab==='items'&&document.querySelector('.lootsplit.lex-panel-layout')", 30)
            record_layouts["screenshot"] = str(screenshot(cdp, "github-46-rdr2-side-by-side-record-panels.png"))
            cdp.eval("navigate('shops',{shopMode:'workspace',shopType:'ST_GENERAL'})")
            wait_eval(cdp, "document.querySelectorAll('.shop-workspace>.shop-panel').length===3", 30)
            result = check_layout(cdp, ".shop-workspace", ".shop-panel",
                                  "lexeditor:panel-layout:rdr2-shops")
            assert result["panels"] == 3 and result["dividers"] == 2, result
            assert result["after"][0] > result["before"][0], result
            assert result["after"][1] < result["before"][1], result
            assert abs(result["after"][2] - result["before"][2]) < 2, result
            assert isinstance(result["stored"], list) and len(result["stored"]) == 3, result
            pointer = drag_second_divider(cdp, ".shop-workspace", ".shop-panel")
            assert abs(pointer["after"][0] - pointer["before"][0]) < 2, pointer
            assert pointer["after"][1] > pointer["before"][1], pointer
            assert pointer["after"][2] < pointer["before"][2], pointer
            result["pointer"] = pointer
            result["recordLayouts"] = record_layouts
            result["screenshot"] = str(screenshot(cdp, "github-46-rdr2-resizable-shops.png"))
            assert not result["errors"], result
            return result
    finally:
        if profile:
            close_browser(profile, browser, cdp)
        isolated.cleanup()


def main() -> int:
    assert EDGE.is_file(), EDGE
    print(json.dumps({"blank": verify_blank(), "ff8": verify_ff8(), "rdr2": verify_rdr2()}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
