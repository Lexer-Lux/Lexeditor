"""Rendered acceptance for the current FF8 and shared UI repairs."""

from __future__ import annotations

import base64
import json
from urllib.request import Request, urlopen
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(r"C:\RDR2Mod\tools\reverse-engineering")))

from games.ff8.plugin import FF8Session  # noqa: E402
from render_crime_editors_55_62 import Cdp, free_port, wait_eval, wait_json  # noqa: E402


def capture(cdp: Cdp, name: str) -> None:
    shot = cdp.call("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": False, "fromSurface": True,
    })
    target = ROOT / "worklog" / "issues" / "rendered" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(shot["data"]))


def main() -> int:
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    profile = tempfile.TemporaryDirectory(
        prefix="lexeditor-ff8-current-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-current-project-", ignore_cleanup_errors=True)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    browser = None
    cdp = None
    try:
        Path(project.name, "mod.json").write_text(json.dumps({
            "id": "ff8-test-mod", "name": "FF8 Test Mod",
            "enabled": True, "order": 0,
        }), encoding="utf-8")
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
              window.pywebview={api:{
                mod_projects:async()=>({canCreate:true,projects:[{name:'FF8 Test Mod',path:'Rendered test project',valid:true,current:true}]}),
                set_dirty_count:async()=>null,
                game_process_status:async()=>null
              }};
            """})
            cdp.call("Page.navigate", {"url": session.url})
            wait_eval(cdp, "typeof state!=='undefined'&&!state.booting", 90)
            initial_save = cdp.eval("""(()=>{const save=document.querySelector('#global-save'),play=document.querySelector('#global-game-process'),circle=document.querySelector('#lexeditor-settings');return{disabled:save.disabled,badgeHidden:document.querySelector('.lex-save-count').hidden,disabledOpacity:Number(getComputedStyle(save).opacity),playBorder:getComputedStyle(play).borderTopWidth,circleBorder:getComputedStyle(circle).borderTopWidth}})()""")
            assert initial_save["disabled"] and initial_save["badgeHidden"] and initial_save["disabledOpacity"] < .5, initial_save
            assert initial_save["playBorder"] == "2px" and initial_save["circleBorder"] == "2px", initial_save
            top_bar = cdp.eval("""(()=>{const row=document.querySelector('.lex-shell-command-row'),rr=row.getBoundingClientRect(),visible=[...row.children].filter(node=>getComputedStyle(node).display!=='none'),rects=visible.map(node=>{const r=node.getBoundingClientRect();return{className:node.className,left:r.left,right:r.right,top:r.top,bottom:r.bottom,center:r.top+r.height/2}});return{height:rr.height,top:rr.top,bottom:rr.bottom,maxCenterDelta:Math.max(...rects.map(rect=>Math.abs(rect.center-(rr.top+rr.height/2)))),brandRight:rects.find(rect=>String(rect.className).includes('brand-slot'))?.right,leftActionsLeft:rects.find(rect=>String(rect.className).includes('left-actions'))?.left,rects,errors:window.__testErrors}})()""")
            assert abs(top_bar["height"] - 81) <= 1 and top_bar["maxCenterDelta"] <= 1 and top_bar["brandRight"] <= top_bar["leftActionsLeft"] and not top_bar["errors"], top_bar

            wait_eval(cdp, "!document.querySelector('.lex-project-control').hidden", 5)
            cdp.eval("document.querySelector('.lex-project-select').click()")
            selector = cdp.eval("""(()=>{const trigger=document.querySelector('.lex-project-select'),status=trigger.querySelector(':scope>.lex-project-source-status'),arrow=getComputedStyle(trigger,'::after'),box=node=>{const value=node.getBoundingClientRect();return{left:value.left,right:value.right,top:value.top,bottom:value.bottom}};return{names:[...document.querySelectorAll('.lex-project-menu-name')].map(node=>node.textContent.trim()),modes:[...document.querySelectorAll('.lex-project-source-mode')].map(node=>node.textContent.trim()),statuses:[...document.querySelectorAll('.lex-project-source-status')].map(node=>node.textContent.trim()),expanded:trigger.getAttribute('aria-expanded'),collapsedStatus:box(status),trigger:box(trigger),arrowRight:parseFloat(arrow.right),arrowWidth:parseFloat(arrow.width)+parseFloat(arrow.borderRightWidth),errors:window.__testErrors}})()""")
            assert selector["names"] == ["Vanilla", "FF8 Test Mod"] and selector["modes"] == ["📝", "🔒", "📝"] and selector["statuses"] == ["✓", "✓", "✓"] and selector["expanded"] == "true" and not selector["errors"], selector
            arrow_left = selector["trigger"]["right"] - selector["arrowRight"] - selector["arrowWidth"]
            assert selector["collapsedStatus"]["right"] <= arrow_left - 4, selector
            assert selector["trigger"]["right"] - selector["collapsedStatus"]["right"] <= 44, selector
            capture(cdp, "ff8-current-vanilla-selector.png")
            cdp.eval("setTimeout(()=>switchProjectSource('vanilla'),0);true")
            wait_eval(cdp, "state.activeSource==='vanilla'", 5)
            cdp.eval("document.querySelector('.lex-project-select').click();document.querySelector('.lex-project-select').click()")
            vanilla = cdp.eval("""(()=>({name:document.querySelector('.lex-project-name').textContent.trim(),readonly:state.activeSource!=='mine',saveDisabled:document.querySelector('#global-save').disabled,matchesBaseline:JSON.stringify(state.data.items)===JSON.stringify(state.vanilla.items),errors:window.__testErrors}))()""")
            assert vanilla == {"name": "Vanilla", "readonly": True, "saveDisabled": True,
                               "matchesBaseline": True, "errors": []}, vanilla
            cdp.eval("setTimeout(()=>switchProjectSource('mine'),0);true")
            wait_eval(cdp, "state.activeSource==='mine'", 15)
            cdp.eval("document.querySelector('.lex-project-select').click();document.querySelector('.lex-project-select').click()")
            mine = cdp.eval("""(()=>({name:document.querySelector('.lex-project-name').textContent.trim(),readonly:state.activeSource!=='mine',errors:window.__testErrors}))()""")
            assert mine == {"name": "FF8 Test Mod", "readonly": False, "errors": []}, mine

            cdp.eval("navigate('formulae')")
            formulae = cdp.eval("""(()=>{const view=document.querySelector('.formulae-view'),heading=document.querySelector('.formula-card h2'),card=heading.closest('.formula-card'),hr=heading.getBoundingClientRect(),cr=card.getBoundingClientRect(),before=view.scrollTop;view.scrollTop=view.scrollHeight;return{tab:!!document.querySelector('[data-tab="formulae"]'),cards:document.querySelectorAll('.formula-card').length,headings:[...document.querySelectorAll('.formula-card h2')].map(n=>n.textContent),scroll:{before,after:view.scrollTop,client:view.clientHeight,height:view.scrollHeight,overflow:getComputedStyle(view).overflowY},caption:{background:getComputedStyle(heading).backgroundColor,overlap:hr.top<=cr.top},errors:window.__testErrors}})()""")
            assert formulae["tab"] and formulae["cards"] == 6
            assert formulae["headings"] == ["PHYSICAL DAMAGE", "PHYSICAL ACCURACY", "MELEE DAMAGE (REWORK)", "MAGIC DAMAGE (REWORK)", "STATUS INFLICTION (REWORK)", "SPELL HEALING (REWORK)"]
            assert formulae["scroll"]["overflow"] == "auto" and formulae["scroll"]["height"] > formulae["scroll"]["client"] and formulae["scroll"]["after"] > formulae["scroll"]["before"], formulae
            # A surface-matched mask must cover the panel border behind the
            # edge caption. Transparent captions let the border strike through
            # glyphs.
            assert formulae["caption"]["background"] == "rgba(0, 0, 0, 0)" and formulae["caption"]["overlap"], formulae
            assert not formulae["errors"]
            capture(cdp, "ff8-current-formulae.png")

            cdp.eval("navigate('items')")
            wait_eval(cdp, "document.querySelectorAll('.ff8-record-list .lex-column-list-row').length>5", 30)
            items = cdp.eval("""(()=>{const canvas=document.createElement('canvas'),context=canvas.getContext('2d'),sample=document.querySelector('.lex-number'),style=getComputedStyle(sample);context.font=`${style.fontSize} ${style.fontFamily}`;const divider=document.querySelector('.lex-list-detail-divider'),barrel=divider.querySelector('.lex-barrel-control');divider.classList.add('dragging');const label=barrel.querySelector('.lex-barrel-label').getBoundingClientRect(),buttons=barrel.querySelector('.lex-barrel-buttons').getBoundingClientRect(),rail=divider.getBoundingClientRect(),box=barrel.getBoundingClientRect();return{one:context.measureText('1').width,zero:context.measureText('0').width,pins:document.querySelectorAll('.detail .lex-column-pin').length,columns:document.querySelectorAll('.ff8-record-list .lex-column-list-head-cell').length,barrel:{labelLeft:label.left,buttonsLeft:buttons.left,gap:Math.max(0,Math.max(rail.left,box.left)-Math.min(rail.right,box.right))},errors:window.__testErrors}})()""")
            assert items["one"] < items["zero"] * .8, items
            assert items["pins"] >= 3 and items["columns"] == 4, items
            assert items["barrel"]["labelLeft"] < items["barrel"]["buttonsLeft"] and items["barrel"]["gap"] == 0, items
            assert not items["errors"]
            barrel_click = cdp.eval("""(()=>{const button=document.querySelector('.lex-barrel-increase');button.click();return{disabled:button.disabled}})()""")
            assert not barrel_click["disabled"], barrel_click
            wait_eval(cdp, "document.querySelectorAll('.lex-barrel-grid>.lex-list').length===2", 5)
            cdp.eval("document.querySelector('.lex-barrel-decrease').click()")
            wait_eval(cdp, "document.querySelectorAll('.lex-barrel-grid>.lex-list').length===1", 5)
            items["barrelClick"] = {"increased": True, "decreased": True}
            sort_point = cdp.eval("""(()=>{const box=document.querySelector('.lex-column-list-head-cell[data-column-key="buyPrice"]').getBoundingClientRect();return{x:box.right-6,y:box.top+box.height/2}})()""")
            cdp.call("Input.dispatchMouseEvent", {"type":"mousePressed","x":sort_point["x"],"y":sort_point["y"],"button":"left","buttons":1,"clickCount":1})
            cdp.call("Input.dispatchMouseEvent", {"type":"mouseReleased","x":sort_point["x"],"y":sort_point["y"],"button":"left","buttons":0,"clickCount":1})
            items_sort = cdp.eval("""(()=>({key:state.sorts.items[0],direction:state.sorts.items[1],active:document.querySelector('.lex-column-list-head-cell[data-column-key="buyPrice"]')?.getAttribute('aria-sort'),errors:window.__testErrors}))()""")
            assert items_sort["key"] == "buyPrice" and items_sort["active"] in {"ascending", "descending"} and not items_sort["errors"], items_sort
            items["sort"] = items_sort
            item_identity = cdp.eval("""(()=>{const ids=[...document.querySelectorAll('.ff8-record-list .lex-numbered-id-cell .lex-record-id')],prefixes=ids.map(node=>node.querySelector('.lex-record-id-prefix').getBoundingClientRect().left),rights=ids.map(node=>node.getBoundingClientRect().right),identity=document.querySelector('.lex-detail-panel-id'),identityGrid=document.querySelector('.lex-detail-panel-identity'),title=document.querySelector('.lex-detail-panel-title'),pin=identity.querySelector('.lex-column-pin'),record=identity.querySelector('.lex-record-id'),svg=pin.querySelector('svg'),point=svg.createSVGPoint(),ir=identity.getBoundingClientRect(),igr=identityGrid.getBoundingClientRect(),tr=title.getBoundingClientRect(),pr=pin.getBoundingClientRect(),rr=record.getBoundingClientRect(),icon=document.querySelector('.ff8-record-list .lex-column-list-row .ff8-item-icon-slot'),head=document.querySelector('.ff8-record-list [data-column-key="id"]'),hr=head.getBoundingClientRect(),label=head.querySelector('.header-label').getBoundingClientRect(),captions=[...document.querySelectorAll('.detail .lex-detail-section-title')];point.x=3.71;point.y=21.71;const tip=point.matrixTransform(svg.getScreenCTM());return{prefixSpread:Math.max(...prefixes)-Math.min(...prefixes),rightSpread:Math.max(...rights)-Math.min(...rights),headerCenterDelta:Math.abs((label.left+label.width/2)-(hr.left+hr.width/2)),titleStartsIdentity:Math.abs(tr.left-igr.left),titleBeforeId:tr.right<ir.left,pinTouchesTopRight:pr.right<=ir.right+1&&ir.right-pr.right<=4&&pr.top<=ir.top+3,pinTip:{rightInset:rr.right-tip.x,topOffset:tip.y-rr.top},captions:captions.map(node=>({background:getComputedStyle(node).backgroundColor,shadow:getComputedStyle(node).boxShadow})),iconTransform:getComputedStyle(icon).transform,iconParentAlign:getComputedStyle(icon.parentElement).alignItems,errors:window.__testErrors}})()""")
            assert item_identity["prefixSpread"] <= 1, item_identity
            assert item_identity["headerCenterDelta"] <= 1, item_identity
            assert item_identity["titleStartsIdentity"] <= 1 and item_identity["titleBeforeId"], item_identity
            assert item_identity["captions"] and all(row == {"background": "rgba(0, 0, 0, 0)", "shadow": "none"} for row in item_identity["captions"]), item_identity
            assert 0 <= item_identity["pinTip"]["rightInset"] <= 5 and 0 <= item_identity["pinTip"]["topOffset"] <= 5, item_identity
            assert item_identity["iconTransform"].endswith(", 2)"), item_identity
            assert item_identity["iconParentAlign"] == "center", item_identity
            item_detail_geometry = cdp.eval("""(()=>{const flags=[...document.querySelectorAll('.item-menu-section .lex-toggle')].map(label=>{const name=label.querySelector('.lex-toggle-name')?.getBoundingClientRect(),help=label.querySelector('.lex-info-help')?.getBoundingClientRect();return{nameRight:name?.right,helpLeft:help?.left,overlap:!!(name&&help&&help.width>0&&name.right>help.left+.5)}}),price=document.querySelector('.ff8-price-equation-row'),centers=[...price.querySelectorAll('.ff8-price-equation>*')].map(node=>{const r=node.getBoundingClientRect();return r.top+r.height/2});return{flagCount:flags.length,overlaps:flags.filter(value=>value.overlap).length,priceCenterSpread:Math.max(...centers)-Math.min(...centers),priceRows:new Set(centers.map(value=>Math.round(value))).size}})()""")
            assert item_detail_geometry["flagCount"] == 8 and item_detail_geometry["overlaps"] == 0, item_detail_geometry
            assert item_detail_geometry["priceCenterSpread"] <= 3 and item_detail_geometry["priceRows"] == 1, item_detail_geometry
            items["identity"] = item_identity
            final_page = cdp.eval("""(()=>{state.pages.items=Math.max(0,Math.ceil(filtered('items',['name','id']).length/state.pageSizes.items)-1);renderItems();const list=document.querySelector('.ff8-record-list'),last=list?.querySelector('.lex-column-list-row:last-child'),master=document.querySelector('.lex-barrelled-master'),divider=document.querySelector('.lex-panel-layout-divider'),barrel=divider?.querySelector('.lex-barrel-control'),lr=list?.getBoundingClientRect(),rr=last?.getBoundingClientRect(),mr=master?.getBoundingClientRect(),dr=divider?.getBoundingClientRect(),br=barrel?.getBoundingClientRect();return{rows:list?.querySelectorAll('.lex-column-list-row').length||0,listGap:lr&&rr?lr.bottom-rr.bottom:null,masterGap:mr&&lr?mr.bottom-lr.bottom:null,barrelCenter:dr&&br?Math.abs((dr.top+dr.height/2)-(br.top+br.height/2)):null,errors:window.__testErrors}})()""")
            assert final_page["rows"] > 0 and abs(final_page["listGap"]) <= 4 and abs(final_page["masterGap"]) <= 4 and final_page["barrelCenter"] <= 2 and not final_page["errors"], final_page
            items["finalPage"] = final_page
            reorder = cdp.eval("""(()=>{const headers=[...document.querySelectorAll('.ff8-record-list .lex-column-list-head-cell')],source=headers[0],target=headers[2],sr=source.getBoundingClientRect(),tr=target.getBoundingClientRect(),header=source.parentElement;source.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,pointerId:7,clientX:sr.left+sr.width/2,clientY:sr.top+sr.height/2}));header.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,button:0,pointerId:7,clientX:tr.left+tr.width/2,clientY:tr.top+tr.height/2}));const dragTarget=header.querySelector('.drag-target')?.dataset.columnKey||'',dragging=header.querySelector('.dragging')?.dataset.columnKey||'';header.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,button:0,pointerId:7,clientX:tr.left+tr.width/2,clientY:tr.top+tr.height/2}));const selected=document.querySelector('.ff8-record-list .lex-column-list-row.selected'),pointer=selected?.querySelector('.lex-column-pointer-cell'),ordinary=[...document.querySelectorAll('.ff8-record-list .lex-column-list-row:not(.selected) .lex-column-pointer-cell')][0],title=document.querySelector('.lex-detail-panel-title').getBoundingClientRect(),identity=document.querySelector('.lex-detail-panel-id').getBoundingClientRect();return{keys:[...document.querySelectorAll('.ff8-record-list .lex-column-list-head-cell')].map(cell=>cell.dataset.columnKey),dragTarget,dragging,pointerKey:pointer?.dataset.columnKey,padding:pointer&&ordinary?[getComputedStyle(pointer).paddingLeft,getComputedStyle(ordinary).paddingLeft]:[],identityCenterDelta:Math.abs((title.top+title.height/2)-(identity.top+identity.height/2)),errors:window.__testErrors}})()""")
            assert reorder["keys"][:3] == ["name", "id", "buyPrice"], reorder
            assert reorder["pointerKey"] == "name" and len(set(reorder["padding"])) == 1, reorder
            assert reorder["identityCenterDelta"] <= 3, reorder
            capture(cdp, "ff8-current-items.png")
            cdp.eval("document.querySelector('.detail .lex-column-pin[aria-pressed=true]').click()")
            wait_eval(cdp, "document.querySelectorAll('.ff8-record-list .lex-column-list-head-cell').length===3", 5)
            cdp.eval("document.querySelector('.detail .lex-column-pin[aria-pressed=false]').click()")
            wait_eval(cdp, "document.querySelectorAll('.ff8-record-list .lex-column-list-head-cell').length===4", 5)
            cdp.eval("document.querySelector('[data-tab=items]').dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true}))")
            wait_eval(cdp, "document.querySelectorAll('.ff8-record-list .lex-column-list-head-cell').length===4", 5)

            cdp.eval("navigate('characters')")
            wait_eval(cdp, "!!document.querySelector('.character-detail input[inputmode=decimal]')", 30)
            before = cdp.eval("document.querySelectorAll('.character-detail .lex-reference-values').length")
            cdp.eval("""(()=>{const input=document.querySelector('.character-detail input[inputmode=decimal]');input.value=String(Number(input.value.replaceAll(',',''))+1);input.dispatchEvent(new Event('input',{bubbles:true}))})()""")
            wait_eval(cdp, "document.querySelectorAll('.character-detail .lex-reference-values').length>0", 5)
            characters = cdp.eval("""(()=>({before:%d,refs:[...document.querySelectorAll('.character-detail .lex-reference-values')].filter(node=>node.getBoundingClientRect().height>0).map(node=>node.textContent.trim()),save:{disabled:document.querySelector('#global-save').disabled,count:document.querySelector('.lex-save-count').textContent,hidden:document.querySelector('.lex-save-count').hidden},errors:window.__testErrors}))()""" % before)
            assert characters["refs"] and characters["refs"][0].startswith("V"), characters
            assert not characters["save"]["disabled"] and not characters["save"]["hidden"] and int(characters["save"]["count"]) >= 1, characters
            assert not characters["errors"], characters
            # Preserve the restored graph text while redesign remains deferred.
            from tools.verify_ff8_math_visual import check_math
            characters["curveMath"] = check_math(cdp)
            curve_bar = cdp.eval("""(()=>{const card=document.querySelector('.ff8-character-curve'),fill=card.querySelector('.lex-curve-fill'),bar=card.querySelector('.lex-curve-bars rect'),toggle=card.querySelector('.lex-curve-mode-toggle');toggle.click();const result={mode:card.querySelector('.lex-curve-plot').classList.contains('lex-curve-bar-mode'),fill:getComputedStyle(fill).fill,bar:getComputedStyle(bar).fill,errors:window.__testErrors};toggle.click();return result})()""")
            assert curve_bar["mode"] and curve_bar["bar"] == curve_bar["fill"] and not curve_bar["errors"], curve_bar
            characters["curveBar"] = curve_bar
            curve_tooltip = cdp.eval("""(()=>{const card=document.querySelector('.ff8-character-curve'),plot=card.querySelector('.lex-curve-plot'),svg=card.querySelector('.lex-curve-svg'),tooltip=card.querySelector('.lex-curve-tooltip'),svgBox=svg.getBoundingClientRect(),plotBox=plot.getBoundingClientRect(),move=ratio=>{const cursorX=svgBox.left+svgBox.width*ratio;svg.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:cursorX,clientY:svgBox.top+svgBox.height*.35}));const box=tooltip.getBoundingClientRect();return{cursorX,left:box.left,right:box.right,center:(box.left+box.right)/2,plotLeft:plotBox.left,plotRight:plotBox.right,text:tooltip.textContent}};return{center:move(.5),right:move(.998),viewportWidth:innerWidth,errors:window.__testErrors}})()""")
            assert abs(curve_tooltip["center"]["center"] - curve_tooltip["center"]["cursorX"]) <= 1.5, curve_tooltip
            assert abs(curve_tooltip["right"]["center"] - curve_tooltip["right"]["cursorX"]) <= 1.5, curve_tooltip
            assert curve_tooltip["right"]["right"] <= curve_tooltip["viewportWidth"] and curve_tooltip["right"]["text"].startswith("(") and not curve_tooltip["errors"], curve_tooltip
            characters["curveTooltip"] = curve_tooltip
            arrow_setup = cdp.eval("""(()=>{const card=document.querySelector('.ff8-character-curve[data-curve-title="STR"]'),input=card.querySelector('input:not(:disabled)'),beforeValue=Number(input.value.replaceAll(',','')),maximum=Number(input.dataset.max),key=beforeValue>=maximum?'ArrowDown':'ArrowUp';window.__curveArrowTest={beforePath:card.querySelector('.lex-curve-line').getAttribute('d'),beforeValue,key,input};input.focus();input.dispatchEvent(new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true}));return{beforeValue,key}})()""")
            wait_eval(cdp, "(()=>{const test=window.__curveArrowTest,card=document.querySelector('.ff8-character-curve[data-curve-title=STR]');return Number(test.input.value.replaceAll(',',''))!==test.beforeValue&&card.querySelector('.lex-curve-line').getAttribute('d')!==test.beforePath})()", 5)
            arrow_result = cdp.eval("""(()=>{const test=window.__curveArrowTest,card=document.querySelector('.ff8-character-curve[data-curve-title="STR"]');return{beforeValue:test.beforeValue,afterValue:Number(test.input.value.replaceAll(',','')),key:test.key,pathChanged:card.querySelector('.lex-curve-line').getAttribute('d')!==test.beforePath,focused:document.activeElement===test.input,connected:test.input.isConnected,errors:window.__testErrors}})()""")
            assert arrow_result["afterValue"] != arrow_result["beforeValue"] and arrow_result["pathChanged"], arrow_result
            assert arrow_result["focused"] and arrow_result["connected"] and not arrow_result["errors"], arrow_result
            characters["curveArrowKey"] = arrow_result
            slider_drag = cdp.eval("""(async()=>{const field=document.querySelector('.character-limit-break-field.lex-has-value-fill'),handle=field.querySelector('.lex-value-handle'),input=field.querySelector('input:not(:disabled)'),before=Number(input.value.replaceAll(',','')),beforeInput=input,native=shell.refresh;let refreshes=0;shell.refresh=()=>{refreshes++};handle.setPointerCapture=()=>{};const r=input.getBoundingClientRect(),h=handle.getBoundingClientRect(),pointerId=41;handle.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,cancelable:true,button:0,buttons:1,pointerId,clientX:h.left+h.width/2,clientY:h.top+h.height/2}));const values=[];for(let index=1;index<=24;index++){handle.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,buttons:1,pointerId,clientX:r.left+r.width*(index/25),clientY:r.top+r.height/2}));if(index%4===0)await new Promise(requestAnimationFrame);values.push(Number(input.value.replaceAll(',','')))}const during={refreshes,connected:beforeInput.isConnected,before,after:Number(input.value.replaceAll(',','')),advances:new Set(values).size};handle.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,button:0,buttons:0,pointerId,clientX:r.right-2,clientY:r.top+r.height/2}));await new Promise(requestAnimationFrame);const after={refreshes,connected:beforeInput.isConnected,dragging:Boolean(input.lexValueSliderDragging),released:Number(input.value.replaceAll(',',''))};shell.refresh=native;return{during,after,errors:window.__testErrors}})()""", await_promise=True)
            assert slider_drag["during"]["refreshes"] == 0 and slider_drag["during"]["connected"], slider_drag
            assert slider_drag["during"]["after"] != slider_drag["during"]["before"] and slider_drag["during"]["advances"] >= 2, slider_drag
            assert slider_drag["after"]["refreshes"] == 1 and slider_drag["after"]["connected"] and not slider_drag["after"]["dragging"], slider_drag
            assert slider_drag["after"]["released"] != slider_drag["during"]["before"], slider_drag
            assert not slider_drag["errors"], slider_drag
            characters["sliderDrag"] = slider_drag
            graph_reference = cdp.eval("""(()=>{const card=document.querySelector('.ff8-character-curve[data-curve-title="STR"]'),source=card.querySelector('.lex-curve-variable .lex-source-control-internal'),input=source.querySelector('input'),reference=source.querySelector('.lex-reference-value'),box=node=>{const value=node.getBoundingClientRect();return{left:value.left,right:value.right,top:value.top,bottom:value.bottom}};return{input:box(input),reference:box(reference),text:reference.textContent.trim(),errors:window.__testErrors}})()""")
            assert graph_reference["text"].startswith("V"), graph_reference
            assert 3 <= graph_reference["input"]["right"] - graph_reference["reference"]["right"] <= 5, graph_reference
            assert graph_reference["reference"]["top"] >= graph_reference["input"]["top"] - 1 and graph_reference["reference"]["bottom"] <= graph_reference["input"]["bottom"] + 1, graph_reference
            assert not graph_reference["errors"], graph_reference
            characters["curveReferenceAlignment"] = graph_reference
            capture(cdp, "ff8-current-graph-reference.png")
            variable_link = cdp.eval("""(()=>{const card=document.querySelector('.ff8-character-curve[data-curve-title="STR"]'),drawer=card.querySelector('.lex-curve-variable-overlay'),label=card.querySelector('.lex-curve-variable[data-curve-variable="a"]'),name=label.querySelector('.lex-curve-variable-name'),input=label.querySelector('input'),token=card.querySelector('.lex-curve-path-formula [data-curve-variable="a"]'),tokens=[...card.querySelectorAll('.lex-curve-path-formula [data-curve-variable]')],hover=node=>{drawer.dispatchEvent(new PointerEvent('pointerover',{bubbles:true}));node.dispatchEvent(new PointerEvent('pointerover',{bubbles:true}));return{label:label.classList.contains('lex-curve-variable-highlight'),token:token.classList.contains('lex-curve-variable-highlight'),count:card.querySelectorAll('.lex-curve-variable-highlight').length}};drawer.dispatchEvent(new PointerEvent('pointerover',{bubbles:true}));const drawerCount=card.querySelectorAll('.lex-curve-variable-highlight').length,nameHover=hover(name),inputHover=hover(input),fills=tokens.map(node=>getComputedStyle(node).fill);return{drawerIdentity:drawer.hasAttribute('data-curve-variable'),nameIdentity:name.hasAttribute('data-curve-variable'),drawerCount,nameHover,inputHover,tokenCount:tokens.length,fillCount:new Set(fills).size,fills,errors:window.__testErrors}})()""")
            assert not variable_link["drawerIdentity"] and not variable_link["nameIdentity"], variable_link
            assert variable_link["drawerCount"] == 0, variable_link
            assert variable_link["nameHover"]["label"] and variable_link["nameHover"]["token"], variable_link
            assert variable_link["inputHover"]["label"] and variable_link["inputHover"]["token"], variable_link
            assert variable_link["tokenCount"] >= 4 and variable_link["fillCount"] >= 4 and not variable_link["errors"], variable_link
            characters["curveVariableLink"] = variable_link
            # Check the restored curve-following text; redesign is deferred in #299.
            characters["curveLayout"] = check_math(cdp)
            type_target = cdp.eval("""(()=>{document.activeElement?.blur();const field=document.querySelector('.character-limit-break-field'),r=field.getBoundingClientRect(),rail=field.querySelector('.lex-field-type-rail');return{x:r.left+r.width*.5,y:r.top+r.height*.5,initialTransform:getComputedStyle(rail).transform,initialOpacity:getComputedStyle(rail).opacity}})()""")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": type_target["x"], "y": type_target["y"], "button": "none", "buttons": 0})
            wait_eval(cdp, "parseFloat(getComputedStyle(document.querySelector('.character-limit-break-field .lex-field-type-rail')).opacity)>=.99", 5)
            type_hover = cdp.eval("""(()=>{const field=document.querySelector('.character-limit-break-field'),rail=field.querySelector('.lex-field-type-rail'),name=rail.querySelector('.lex-field-type-name'),range=rail.querySelector('.lex-field-type-range'),owner=field.closest('.character-limit-break-row'),box=node=>{const r=node.getBoundingClientRect();return{left:r.left,top:r.top,right:r.right,bottom:r.bottom}};return{type:field.dataset.lexType,name:name.textContent,hover:field.matches(':hover'),transform:getComputedStyle(rail).transform,nameTransform:getComputedStyle(name).transform,nameWritingMode:getComputedStyle(name).writingMode,rangeOpacity:getComputedStyle(range).opacity,rangeDisplay:getComputedStyle(range).display,rail:box(rail),field:box(field),owner:box(owner),errors:window.__testErrors}})()""")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": (type_hover["rail"]["left"] + type_hover["rail"]["right"]) / 2, "y": (type_hover["rail"]["top"] + type_hover["rail"]["bottom"]) / 2, "button": "none", "buttons": 0})
            wait_eval(cdp, "parseFloat(getComputedStyle(document.querySelector('.character-limit-break-field .lex-field-type-rail>.lex-info-help')).opacity)>=.99", 5)
            type_help = cdp.eval("""(()=>{const rail=document.querySelector('.character-limit-break-field .lex-field-type-rail'),name=rail.querySelector('.lex-field-type-name'),range=rail.querySelector('.lex-field-type-range'),help=rail.querySelector('.lex-info-help');return{railHover:rail.matches(':hover'),nameOpacity:getComputedStyle(name).opacity,rangeOpacity:getComputedStyle(range).opacity,helpOpacity:getComputedStyle(help).opacity,helpText:help.textContent.trim(),errors:window.__testErrors}})()""")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": type_hover["field"]["right"] - 8, "y": (type_hover["field"]["top"] + type_hover["field"]["bottom"]) / 2, "button": "none", "buttons": 0})
            cdp.eval("document.querySelector('.character-limit-break-field input').focus()")
            wait_eval(cdp, "parseFloat(getComputedStyle(document.querySelector('.character-limit-break-field .lex-field-type-range')).opacity)>=.99", 5)
            type_focus = cdp.eval("""(()=>{const field=document.querySelector('.character-limit-break-field'),input=field.querySelector('input'),rail=field.querySelector('.lex-field-type-rail');return{transform:getComputedStyle(rail).transform,rangeOpacity:getComputedStyle(rail.querySelector('.lex-field-type-range')).opacity,typeAndRangeVisible:[rail.querySelector('.lex-field-type-name'),rail.querySelector('.lex-field-type-range')].filter(n=>n&&getComputedStyle(n).display!=='none'&&parseFloat(getComputedStyle(n).opacity)>.9).length===2,focused:document.activeElement===input}})()""")
            assert type_hover["type"] == type_hover["name"] == "INT", type_hover
            assert float(type_target["initialOpacity"]) <= .01, type_target
            assert type_hover["rangeDisplay"] == "block" and float(type_hover["rangeOpacity"]) <= .01, type_hover
            assert type_hover["nameWritingMode"] == "horizontal-tb" and type_hover["nameTransform"].startswith("matrix(0, -1, 1, 0"), type_hover
            assert type_help["railHover"] and type_help["helpText"] == "?", type_help
            assert float(type_help["nameOpacity"]) <= .01 and float(type_help["rangeOpacity"]) <= .01 and float(type_help["helpOpacity"]) >= .99, type_help
            assert float(type_focus["rangeOpacity"]) >= .99 and not type_focus["typeAndRangeVisible"] and type_focus["focused"], type_focus
            assert type_hover["rail"]["left"] >= type_hover["owner"]["left"] - 1 and type_hover["rail"]["top"] >= type_hover["field"]["top"] - 1 and type_hover["rail"]["bottom"] <= type_hover["field"]["bottom"] + 1, type_hover
            assert not type_hover["errors"], type_hover
            characters["typeRail"] = {"hover": type_hover, "help": type_help, "focus": type_focus}
            character_surface = cdp.eval("""(()=>{document.activeElement?.blur();const toolbar=document.querySelector('#toolbar.portrait-toolbar'),selector=toolbar.querySelector('.ff8-portrait-selector'),tabs=selector.querySelector('.ff8-portrait-tabs'),active=tabs.querySelector('.ff8-portrait-tab.active'),pointer=getComputedStyle(active,'::after'),row=document.querySelector('.character-limit-break-row'),fields=[...row.querySelectorAll('.character-limit-break-field')],rect=node=>{const value=node.getBoundingClientRect();return{left:value.left,right:value.right,top:value.top,bottom:value.bottom}},surface=node=>{const style=getComputedStyle(node);return{image:style.backgroundImage,color:style.backgroundColor}},fieldData=fields.map(field=>{const style=getComputedStyle(field),box=rect(field),rail=rect(field.querySelector('.lex-field-type-rail'));return{box,rail,borderRight:style.borderRightWidth,borderBottom:style.borderBottomWidth}});return{toolbar:surface(toolbar),selector:surface(selector),tabs:surface(tabs),pointer:{width:parseFloat(pointer.width),height:parseFloat(pointer.height),left:parseFloat(pointer.left)},row:rect(row),fields:fieldData,errors:window.__testErrors}})()""")
            assert character_surface["toolbar"]["image"] != "none", character_surface
            assert character_surface["selector"] == {"image": "none", "color": "rgba(0, 0, 0, 0)"} and character_surface["tabs"] == {"image": "none", "color": "rgba(0, 0, 0, 0)"}, character_surface
            assert character_surface["pointer"] == {"width": 48, "height": 32, "left": -44}, character_surface
            assert all(field["borderRight"] == "0px" and field["borderBottom"] == "0px" for field in character_surface["fields"]), character_surface
            assert abs(character_surface["fields"][0]["box"]["left"] - character_surface["row"]["left"]) <= 1 and abs(character_surface["fields"][-1]["box"]["right"] - character_surface["row"]["right"]) <= 1, character_surface
            assert all(field["rail"]["left"] >= field["box"]["left"] - 1 and field["rail"]["right"] <= field["box"]["right"] + 1 for field in character_surface["fields"]) and not character_surface["errors"], character_surface
            characters["surfaceContract"] = character_surface
            capture(cdp, "ff8-current-characters.png")
            cdp.eval("""(()=>{const native=window.fetch.bind(window);window.fetch=(...args)=>String(args[0]||'').includes('/api/kernel/save')?new Promise(resolve=>setTimeout(resolve,700)).then(()=>native(...args)):native(...args);document.querySelector('#global-save').click()})()""")
            wait_eval(cdp, "document.body.classList.contains('lex-save-busy')", 5)
            save_busy = cdp.eval("""(()=>({busy:document.body.classList.contains('lex-save-busy'),inert:document.body.inert,spinner:!!document.querySelector('#global-save .lex-save-throbber'),disabled:document.querySelector('#global-save').disabled,opacity:getComputedStyle(document.querySelector('#global-save')).opacity,errors:window.__testErrors}))()""")
            assert save_busy["busy"] and save_busy["inert"] and save_busy["spinner"] and save_busy["disabled"], save_busy
            assert float(save_busy["opacity"]) >= .9 and not save_busy["errors"], save_busy
            wait_eval(cdp, "!document.body.classList.contains('lex-save-busy')", 30)
            characters["saveBusy"] = save_busy

            cdp.eval("navigate('gfs')")
            wait_eval(cdp, "!!document.querySelector('.gf-ability-table select,.gf-ability-table input')", 30)
            check_math(cdp)
            gf_curve_contract = cdp.eval("""(()=>{const curves=[...document.querySelectorAll('.gf-level-curve')],panels=[...document.querySelectorAll('.gf-panel')],first=curves[0],plot=first?.querySelector('.lex-curve-plot')?.getBoundingClientRect(),overlay=first?.querySelector('.lex-curve-variable-overlay')?.getBoundingClientRect();return{count:curves.length,current:curves.every(node=>node.classList.contains('ff8-character-curve')),formulae:curves.every(node=>getComputedStyle(node.querySelector('.lex-curve-path-formula')).display!=='none'&&node.querySelector('textPath')!==null),drawerTop:Boolean(plot&&overlay&&overlay.top<=plot.top+1),panels:panels.map(node=>({border:getComputedStyle(node).borderTopWidth,background:getComputedStyle(node).backgroundColor})),errors:window.__testErrors}})()""")
            assert gf_curve_contract["count"] == 2 and gf_curve_contract["current"] and gf_curve_contract["formulae"], gf_curve_contract
            assert gf_curve_contract["drawerTop"] and all(panel["border"] == "0px" and panel["background"] == "rgba(0, 0, 0, 0)" for panel in gf_curve_contract["panels"]), gf_curve_contract
            assert not gf_curve_contract["errors"], gf_curve_contract
            gf_live_reference = cdp.eval("""(()=>{const control=document.querySelector('.gf-ability-table select,.gf-ability-table input'),source=control.closest('.lex-source-control');if(control.tagName==='SELECT'){const next=[...control.options].find(option=>option.value!==control.value);control.value=next.value;control.dispatchEvent(new Event('change',{bubbles:true}))}else{control.value=String((Number(control.value)||0)+1);control.dispatchEvent(new Event('input',{bubbles:true}))}return{reference:source.querySelector('.lex-reference-values')?.textContent.trim()||'',connected:source.isConnected,errors:window.__testErrors}})()""")
            assert gf_live_reference["connected"] and gf_live_reference["reference"].startswith("V"), gf_live_reference
            assert not gf_live_reference["errors"], gf_live_reference
            capture(cdp, "ff8-current-gfs.png")

            cdp.eval("navigate('magic')")
            wait_eval(cdp, "document.querySelector('.ff8-concept-icon[title=\"Berserk game icon\"]')?.naturalWidth>0&&document.querySelector('.ff8-concept-icon[title=\"Zombie game icon\"]')?.naturalWidth>0", 30)
            cdp.eval("""(()=>{const sleep=state.data.magic.rows.find(row=>row.name==='Sleep');state.selected.magic=sleep.id;render()})()""")
            wait_eval(cdp, "document.querySelector('.lex-detail-panel-title')?.textContent==='Sleep'", 30)
            magic = cdp.eval("""(()=>{const pick=title=>{const image=document.querySelector(`.ff8-concept-icon[title="${title} game icon"]`);return{src:image?.getAttribute('src'),width:image?.naturalWidth,height:image?.naturalHeight}},sleepRow=[...document.querySelectorAll('.lex-detail-field')].find(row=>row.querySelector('.lex-detail-field-label')?.textContent.trim().toLowerCase()==='j-status (attack)'),sleep=sleepRow?.querySelector('label[title="Sleep"]'),record=state.data.magic.rows.find(row=>row.name==='Sleep'),field=record.fields.find(value=>value.lookup?.type==='flags'&&value.lookup?.name==='j_status'&&value.label.toLowerCase()==='j-status attack'),entry=field.lookup.entries.find(value=>value.name==='Sleep'),mask=Number(entry.mask??entry.value),sections=[...document.querySelectorAll('.magic-detail>.lex-detail-panel-body>.lex-detail-section')].map(node=>node.querySelector('.lex-detail-section-title')?.textContent.trim()),rects=[...document.querySelectorAll('.magic-detail>.lex-detail-panel-body>.lex-detail-section')].map(node=>{const box=node.getBoundingClientRect();return{left:box.left,top:box.top,right:box.right}});return{berserk:pick('Berserk'),zombie:pick('Zombie'),sleep:{stored:field.value,mask,checked:Boolean(sleep?.querySelector('input')?.checked)},sections,rects,errors:window.__testErrors}})()""")
            assert magic["berserk"]["src"].endswith("/277.png") and magic["berserk"]["width"] > 0, magic
            assert magic["zombie"]["src"].endswith("/278.png") and magic["zombie"]["width"] > 0, magic
            assert magic["sleep"]["stored"] & magic["sleep"]["mask"] and magic["sleep"]["checked"], magic
            assert magic["sections"] == ["GENERAL", "JUNCTIONING"], magic
            assert len({round(rect["left"]) for rect in magic["rects"]}) == 1, magic
            magic_layout = cdp.eval("""(()=>{const toggle=document.querySelector('.flag-list-icon-toggles .ff8-icon-toggle');if(!toggle)return{missing:'toggle'};const ts=getComputedStyle(toggle),image=toggle.querySelector('.ff8-concept-icon').getBoundingClientRect(),tr=toggle.getBoundingClientRect(),controlNode=toggle.closest('.lex-source-control'),control=(controlNode||toggle).getBoundingClientRect(),compatRows=[...document.querySelectorAll('.magic-compat-column .lex-column-list-row')],inline=document.querySelector('.ff8-inline-field-label-text'),split=document.querySelector('.lex-leading-list-detail'),panes=[...split.children].filter(node=>node.classList.contains('lex-panel-layout-pane')),box=node=>{const r=node.getBoundingClientRect();return{left:r.left,right:r.right}};return{toggle:{background:ts.backgroundColor,border:ts.borderTopWidth,verticalDelta:Math.abs((image.top+image.height/2)-(tr.top+tr.height/2)),square:Math.abs(control.width-control.height)},compat:{rows:compatRows.length,panel:!!split,headers:[...document.querySelectorAll('.magic-compat-column .lex-column-list-head-cell')].map(node=>node.textContent.replace(/[^A-Za-z ]/g,'').trim()),children:panes.map(node=>node.className),left:box(split.querySelector(':scope>.magic-compat-column')),right:box(split.querySelector(':scope>.magic-detail'))},inlineCenterAlign:inline?getComputedStyle(inline).textAlign:'center',inlineInside:!!document.querySelector('.ff8-inline-field .ff8-inline-field-label-text')||!!document.querySelector('.lex-multi-number-label'),projectFont:getComputedStyle(document.body).fontFamily}})()""")
            assert magic_layout["toggle"]["background"] == "rgba(0, 0, 0, 0)" and magic_layout["toggle"]["border"] == "0px" and magic_layout["toggle"]["verticalDelta"] <= 1, magic_layout
            # The panel is the GFs tab's table now: one row per GF, same headers.
            assert magic_layout["compat"]["panel"] and magic_layout["compat"]["rows"] >= 16, magic_layout
            assert magic_layout["compat"]["headers"] == ["GF", "Change"], magic_layout
            assert "magic-compat-column" in magic_layout["compat"]["children"][0], magic_layout
            assert "lex-barrelled-master" in magic_layout["compat"]["children"][1] and "magic-detail" in magic_layout["compat"]["children"][2], magic_layout
            assert magic_layout["compat"]["left"]["right"] <= magic_layout["compat"]["right"]["left"], magic_layout
            # A checkless toggle is square, so its tick sits a fixed distance
            # from its own icon however many fit on the row.
            assert magic_layout["toggle"]["square"] <= 1, magic_layout
            assert magic_layout["inlineCenterAlign"] == "center", magic_layout
            assert magic_layout["inlineInside"], magic_layout
            assert "FF8 Menu" in magic_layout["projectFont"], magic_layout
            magic["layout"] = magic_layout
            magic_provenance = cdp.eval("""(()=>{const row=[...document.querySelectorAll('.lex-detail-field')].find(node=>node.querySelector('.lex-detail-field-label')?.textContent.trim()==='ELEMENT'),sources=[...row.querySelectorAll('.flag-list-icon-toggles>.lex-source-control')],input=sources[0].querySelector('input'),before=input.checked;input.checked=!before;input.dispatchEvent(new Event('change',{bubbles:true}));const changed=sources[0].querySelector('.lex-reference-values')?.textContent.trim()||'',siblings=sources.slice(1).filter(source=>source.querySelector('.lex-reference-values')).length,junction=[...document.querySelectorAll('.lex-detail-field')].find(node=>node.querySelector('.lex-detail-field-label')?.textContent.trim()==='JUNCTION (STATS)'),controls=[...junction.querySelectorAll('.lex-multi-number-item .lex-source-control,.ff8-inline-field>.lex-source-control')],number=controls[0].querySelector('input');number.value=String((Number(number.value.replaceAll(',',''))||0)+1);number.dispatchEvent(new Event('input',{bubbles:true}));const general=[...document.querySelectorAll('.magic-detail>.lex-detail-panel-body>.lex-detail-section')][0];return{changed,siblings,junctionChanged:controls[0].querySelector('.lex-reference-values')?.textContent.trim()||'',junctionSiblingRefs:controls.slice(1).filter(source=>source.querySelector('.lex-reference-values')).length,labelStarts:[...general.querySelectorAll('.lex-detail-field-control')].slice(0,5).map(node=>Math.round(node.getBoundingClientRect().left)),errors:window.__testErrors}})()""")
            assert magic_provenance["changed"].startswith("V") and not any(token in magic_provenance["changed"].lower() for token in ("true", "false", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9")) and magic_provenance["siblings"] == 0, magic_provenance
            assert magic_provenance["junctionChanged"].startswith("V") and magic_provenance["junctionSiblingRefs"] == 0, magic_provenance
            assert len(set(magic_provenance["labelStarts"])) == 1 and not magic_provenance["errors"], magic_provenance
            magic["provenance"] = magic_provenance
            magic_sort = cdp.eval("""(()=>{const head=document.querySelector('.lex-column-list-head-cell[data-column-key="id"]'),button=head.querySelector('.lex-column-sort'),label=head.querySelector('.header-label'),beforeLabel=label.getBoundingClientRect(),before=[...state.sorts.magic];button.click();const nextHead=document.querySelector('.lex-column-list-head-cell[data-column-key="id"]'),nextLabelNode=nextHead.querySelector('.header-label'),nextLabel=nextLabelNode.getBoundingClientRect(),pointerNode=nextHead.querySelector('.lex-sort-indicator'),pointer=getComputedStyle(pointerNode),icon=document.querySelector('.ff8-record-list .lex-column-list-row .ff8-concept-icon');return{before,after:[...state.sorts.magic],aria:nextHead.getAttribute('aria-sort'),labelShift:Math.abs(beforeLabel.left-nextLabel.left),pointerImage:pointer.backgroundImage,pointerTransform:pointer.transform,overflow:getComputedStyle(nextHead).overflow,iconTransform:getComputedStyle(icon).transform,iconParentAlign:getComputedStyle(icon.parentElement).alignItems,errors:window.__testErrors}})()""")
            assert magic_sort["after"] != magic_sort["before"] and magic_sort["aria"] != "none", magic_sort
            assert magic_sort["labelShift"] <= 1 and "0.png" in magic_sort["pointerImage"], magic_sort
            assert magic_sort["pointerTransform"] != "none" and magic_sort["overflow"] == "visible", magic_sort
            assert magic_sort["iconTransform"].endswith(", 2)") and magic_sort["iconParentAlign"] == "center", magic_sort
            magic["sort"] = magic_sort
            assert not magic["errors"], magic
            cdp.eval("document.querySelector('.magic-compat-column,.gf-panel.compatibility')?.scrollIntoView({block:'center'})")
            capture(cdp, "ff8-current-magic.png")

            cdp.eval("navigate('shops')")
            wait_eval(cdp, "document.querySelectorAll('.ff8-shop-table .lex-column-list-row').length===16", 30)
            shops = cdp.eval("""(()=>{const first=document.querySelector('.ff8-shop-table .lex-column-list-row'),slot=first.querySelector('.shop-slot-clear'),finder=first.querySelector('.ff8-item-search'),source=finder.closest('.lex-source-control'),itemIcon=finder.querySelector('.ff8-item-icon-slot'),before=state.data.shops.rows.find(row=>row.id===state.selected.shops).slots.find(entry=>entry.slot===Number(first.dataset.key)).itemId,detail=document.querySelector('.shop-detail'),detailBox=detail.getBoundingClientRect(),rightmost=[...detail.querySelectorAll('*')].map(node=>({node:node.className||node.tagName,right:node.getBoundingClientRect().right-detailBox.right})).sort((a,b)=>b.right-a.right)[0];return{rows:document.querySelectorAll('.ff8-shop-table .lex-column-list-row').length,columns:document.querySelectorAll('.ff8-shop-table .lex-column-list-head-cell').length,finders:document.querySelectorAll('.ff8-shop-table .ff8-item-search').length,selects:document.querySelectorAll('.ff8-shop-table select').length,add:document.querySelectorAll('.shop-detail .lex-new-button,.shop-capacity').length,slotButton:!!slot,iconInside:finder.contains(itemIcon),stableTracks:getComputedStyle(source).gridTemplateColumns,before,overflow:detail.scrollWidth-detail.clientWidth,rightmost,errors:window.__testErrors}})()""")
            assert shops["rows"] == 16 and shops["finders"] == 16 and shops["selects"] == 0 and shops["add"] == 0
            assert shops["columns"] == 3 and shops["slotButton"] and shops["iconInside"], shops
            assert shops["overflow"] <= 1 and shops["rightmost"]["right"] <= 0 and not shops["errors"], shops
            rare_reference = cdp.eval("""(()=>{const source=document.querySelector('.ff8-shop-table .lex-column-list-row .rare .lex-source-control')||document.querySelector('.ff8-shop-table .lex-column-list-row .lex-column-list-cell:last-child .lex-source-control'),input=source.querySelector('input[type=checkbox]'),box=source.getBoundingClientRect(),track=parseFloat(getComputedStyle(source).gridTemplateColumns),before=input.checked;input.checked=!before;input.dispatchEvent(new Event('change',{bubbles:true}));const ir=input.getBoundingClientRect();return{text:source.querySelector('.lex-reference-values')?.textContent.trim()||'',centerDelta:Math.abs((ir.left+ir.width/2)-(box.left+track/2)),errors:window.__testErrors}})()""")
            assert rare_reference["text"] in {"V✓", "V×"} and rare_reference["centerDelta"] <= 2 and not rare_reference["errors"], rare_reference
            shops["rareReference"] = rare_reference
            shop_clear = cdp.eval("""(()=>{const shop=state.data.shops.rows.find(row=>row.id===state.selected.shops),slot=shop.slots[0],button=document.querySelector('.ff8-shop-table .lex-column-list-row .shop-slot-clear'),source=button.closest('.lex-column-list-row').querySelector('.lex-source-control'),finder=source.querySelector('.ff8-item-search'),before=finder.getBoundingClientRect(),beforeGrid=getComputedStyle(source).gridTemplateColumns,beforeChildren=[...source.children].map(node=>node.className);button.click();const current=state.data.shops.rows.find(row=>row.id===state.selected.shops).slots[0],nextSource=document.querySelector('.ff8-shop-table .lex-column-list-row .lex-source-control'),nextFinder=nextSource.querySelector('.ff8-item-search'),after=nextFinder.getBoundingClientRect(),reference=document.querySelector('.ff8-shop-table .lex-reference-values');return{itemId:current.itemId,before:{left:before.left,width:before.width,grid:beforeGrid,children:beforeChildren},after:{left:after.left,width:after.width,grid:getComputedStyle(nextSource).gridTemplateColumns,children:[...nextSource.children].map(node=>node.className)},referenceIcon:!!reference?.querySelector('.ff8-item-display .ff8-item-icon-slot'),referenceText:reference?.textContent.trim()||'',errors:window.__testErrors}})()""")
            assert shop_clear["itemId"] == 0, shop_clear
            assert abs(shop_clear["before"]["left"] - shop_clear["after"]["left"]) <= 1, shop_clear
            assert abs(shop_clear["before"]["width"] - shop_clear["after"]["width"]) <= 1, shop_clear
            assert shop_clear["referenceIcon"] and shop_clear["referenceText"].startswith("V"), shop_clear
            shops["clear"] = shop_clear
            capture(cdp, "ff8-current-shops.png")

            cdp.eval("navigate('weapons')")
            wait_eval(cdp, "!!document.querySelector('.weapon-detail')", 30)
            cdp.eval("""(()=>{const row=state.data.weapons.rows.find(value=>value.ingredients.some(item=>item.itemId===0));state.selected.weapons=row.id;render()})()""")
            wait_eval(cdp, "[...document.querySelectorAll('.ff8-item-search')].some(button=>button.textContent.trim()==='Nothing')", 30)
            weapons = cdp.eval("""(()=>{const nothing=[...document.querySelectorAll('.weapon-ingredient-row')].find(row=>row.querySelector('.ff8-item-search')?.textContent.trim()==='Nothing');return{cost:document.querySelector('.weapon-cost .lex-detail-section-title')?.textContent,headers:document.querySelectorAll('.weapon-cost thead').length,pins:document.querySelectorAll('.weapon-detail .lex-column-pin').length,nothingQuantity:nothing?.querySelectorAll('input,select').length,searchers:document.querySelectorAll('.ff8-item-search').length,overflow:document.querySelector('.weapon-detail').scrollHeight-document.querySelector('.weapon-detail').clientHeight,errors:window.__testErrors}})()""")
            assert weapons["cost"] == "COST" and weapons["headers"] == 0 and weapons["pins"] >= 5
            assert weapons["nothingQuantity"] == 0, weapons
            assert weapons["searchers"] == 4, weapons
            assert weapons["overflow"] <= 0 and not weapons["errors"], weapons
            weapon_geometry = cdp.eval("""(()=>{const detail=document.querySelector('.weapon-detail'),data=[...detail.querySelectorAll('.weapon-data-field>.lex-detail-field-control')].map(node=>node.getBoundingClientRect().right),ingredients=[...detail.querySelectorAll('.weapon-ingredient-control')].map(row=>{const children=[...row.children],item=children[0]?.getBoundingClientRect(),amount=children[1]?.getBoundingClientRect();return{join:amount?Math.abs(item.right-amount.left):0,right:amount?.right||item.right}}),section=detail.querySelector('.weapon-cost'),title=section.querySelector('.lex-detail-section-title'),sr=section.getBoundingClientRect(),tr=title.getBoundingClientRect();return{xOverflow:detail.scrollWidth-detail.clientWidth,dataRightSpread:Math.max(...data)-Math.min(...data),ingredientJoin:Math.max(...ingredients.map(value=>value.join)),ingredientRightSpread:Math.max(...ingredients.map(value=>value.right))-Math.min(...ingredients.map(value=>value.right)),titleVisible:tr.top>=sr.top-12&&tr.bottom<=sr.bottom}})()""")
            assert weapon_geometry["xOverflow"] <= 1 and weapon_geometry["dataRightSpread"] <= 1, weapon_geometry
            assert weapon_geometry["ingredientJoin"] <= 1 and weapon_geometry["ingredientRightSpread"] <= 1 and weapon_geometry["titleVisible"], weapon_geometry
            weapon_sort = cdp.eval("""(()=>{const before=state.sorts.weapons.slice(),button=document.querySelector('[data-column-key="upgradePrice"] .lex-column-sort');button.click();const after=state.sorts.weapons.slice(),aria=document.querySelector('[data-column-key="upgradePrice"]')?.getAttribute('aria-sort'),melee=[...document.querySelectorAll('.weapon-detail input[type="checkbox"]')].find(node=>node.closest('.lex-detail-field')?.textContent.toLowerCase().includes('melee'));return{before,after,aria,meleeType:melee?.type,errors:window.__testErrors}})()""")
            assert weapon_sort["after"][0] == "upgradePrice" and weapon_sort["aria"] in {"ascending", "descending"}, weapon_sort
            assert weapon_sort["meleeType"] == "checkbox" and not weapon_sort["errors"], weapon_sort
            weapons["sort"] = weapon_sort
            wait_eval(cdp, "parseFloat(getComputedStyle(document.querySelector('.ff8-record-list')).getPropertyValue('--lex-fitted-row-height'))>40", 10)
            cdp.eval("""(()=>{const input=document.querySelector('.lex-pager-search input');window.__weaponRowHeight=input.closest('.lex-paged-list-detail').querySelector('.ff8-record-list .lex-column-list-row:not(.lex-filler-row)').getBoundingClientRect().height;input.value='Revolver';input.dispatchEvent(new Event('input',{bubbles:true}))})()""")
            wait_eval(cdp, "document.querySelectorAll('.ff8-record-list .lex-column-list-row:not(.lex-filler-row)').length===1", 10)
            search_fit = cdp.eval("""(()=>{const input=document.querySelector('.lex-pager-search input'),rows=[...document.querySelectorAll('.ff8-record-list .lex-column-list-row:not(.lex-filler-row)')],after=rows[0].getBoundingClientRect().height;input.value='';input.dispatchEvent(new Event('input',{bubbles:true}));return{before:window.__weaponRowHeight,after,count:rows.length,errors:window.__testErrors}})()""")
            assert search_fit["count"] == 1 and abs(search_fit["before"] - search_fit["after"]) <= 1, search_fit
            weapons["searchFit"] = search_fit
            # Hit rate is a percentage stat, not a fraction of 255, so there is
            # no companion raw field any more. What must hold is that the single
            # field round-trips the typed value into the record.
            hit_rate = cdp.eval("""(()=>{const field=document.querySelector('[aria-label="Hit rate"]');field.value='50';field.dispatchEvent(new Event('input',{bubbles:true}));const row=state.data.weapons.rows.find(value=>value.id===state.selected.weapons);return{value:field.value,stored:row.fields.find(entry=>entry.field==='hit_rate')?.value,errors:window.__testErrors}})()""")
            assert hit_rate["value"] == "50" and hit_rate["stored"] == 50, hit_rate
            searcher = cdp.eval("""(()=>{const row=state.data.weapons.rows.find(value=>value.ingredients.some(item=>item.itemId===0)),slot=row.ingredients.findIndex(item=>item.itemId===0),control=[...document.querySelectorAll('.ff8-item-search')].find(value=>value.textContent.trim()==='Nothing'),button=control.querySelector('.ff8-item-finder');window.__searcherProof={weapon:row.id,slot};button.click();return{weapon:row.id,slot}})()""")
            wait_eval(cdp, "state.tab==='items'&&document.querySelector('.lex-searcher-bar')&&document.querySelectorAll('.lex-search-candidate').length>0", 30)
            searcher_start = cdp.eval("""(()=>{const candidate=[...document.querySelectorAll('.lex-search-candidate')].find(node=>Number(node.dataset.key)!==0),expected=Number(candidate.dataset.key);window.__searcherProof.expected=expected;candidate.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,pointerId:1}));return{prompt:document.querySelector('.lex-searcher-prompt').textContent,locked:document.querySelector('.lex-shell-header').classList.contains('lex-searcher-active'),expected}})()""")
            wait_eval(cdp, "state.tab==='weapons'&&!document.querySelector('.lex-searcher-bar')", 5)
            searcher_end = cdp.eval("""(()=>{const proof=window.__searcherProof,row=state.data.weapons.rows.find(value=>value.id===proof.weapon);return{selected:state.selected.weapons,value:row.ingredients[proof.slot].itemId,expected:proof.expected}})()""")
            assert searcher_start["prompt"].startswith("Select the Item for ") and searcher_start["locked"], searcher_start
            assert searcher_end["selected"] == searcher["weapon"] and searcher_end["value"] == searcher_end["expected"], searcher_end
            weapons["searcher"] = {"start": searcher_start, "end": searcher_end}
            capture(cdp, "ff8-current-weapons.png")

            # Developer mode can override the shared row count for one page.
            # With all 33 weapons on one page, the center pager disappears and
            # the search control expands into the released space.
            cdp.eval("window.dispatchEvent(new CustomEvent('lexeditor-settings-changed',{detail:{developerMode:true,selectionHoldMs:650,tableRowsPerPage:15,viewPreferences:{}}}));renderWeapons()")
            wait_eval(cdp, "!!document.querySelector('.lex-page-row-override input')", 10)
            row_focus = cdp.eval("""(()=>{const input=document.querySelector('.lex-page-row-override input');input.focus();input.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,key:'ArrowUp'}));const retained=document.activeElement===input&&input.isConnected;input.value='33';input.dispatchEvent(new FocusEvent('blur'));return{retained,inherited:input.closest('.lex-page-row-override').classList.contains('inherited')}})()""")
            assert row_focus == {"retained": True, "inherited": True}, row_focus
            wait_eval(cdp, "document.querySelector('.lex-paged-list-detail')?.dataset.lexPageSize==='33'", 10)
            page_override = cdp.eval("""(()=>{const root=document.querySelector('.lex-paged-list-detail'),pager=root.querySelector('.lex-pager'),search=pager.querySelector('.lex-pager-search'),pr=pager.getBoundingClientRect(),sr=search.getBoundingClientRect(),content=root.querySelector('.lex-column-cell-content'),style=getComputedStyle(content);return{value:root.dataset.lexPageSize,stored:localStorage.getItem('lexeditor:rows:ff8-weapons'),single:pager.classList.contains('single-page'),controls:pager.querySelectorAll('.lex-pager-controls').length,searchRatio:sr.width/pr.width,whiteSpace:style.whiteSpace,overflow:style.overflow,textOverflow:style.textOverflow,errors:window.__testErrors}})()""")
            assert page_override["value"] == "33" and page_override["stored"] == "33", page_override
            assert page_override["single"] and page_override["controls"] == 0 and page_override["searchRatio"] > .5, page_override
            assert page_override["whiteSpace"] == "nowrap" and page_override["overflow"] == "hidden" and page_override["textOverflow"] == "ellipsis", page_override
            weapons["pageOverride"] = page_override
            cdp.eval("document.querySelector('.lex-page-row-override').dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,button:2}))")
            wait_eval(cdp, "document.querySelector('.lex-paged-list-detail')?.dataset.lexPageSize==='15'&&document.querySelector('.lex-page-row-override')?.classList.contains('inherited')", 10)
            assert cdp.eval("localStorage.getItem('lexeditor:rows:ff8-weapons')") is None

            # Local sorting is the shared fallback for nested Table panels.
            cdp.eval("navigate('encounters')")
            wait_eval(cdp, "!!document.querySelector('.encounter-slot-table .lex-column-sort')", 30)
            cdp.eval("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))", True)
            encounter_sort = cdp.eval("""(()=>{const table=document.querySelector('.encounter-slot-table'),before=[...table.querySelectorAll('.lex-column-list-row')].map(row=>row.dataset.key),button=table.querySelector('[data-column-key="enemy"] .lex-column-sort');button.click();const once=document.querySelector('.encounter-slot-table'),first=[...once.querySelectorAll('.lex-column-list-row')].map(row=>row.dataset.key);once.querySelector('[data-column-key="enemy"] .lex-column-sort').click();const twice=document.querySelector('.encounter-slot-table'),second=[...twice.querySelectorAll('.lex-column-list-row')].map(row=>row.dataset.key),finders=[...twice.querySelectorAll('.ff8-entity-search')],widths=finders.map(node=>node.getBoundingClientRect().width),finder=finders[0],headers=[...twice.querySelectorAll('.lex-column-list-head-cell')].map(cell=>{const label=cell.querySelector('.header-label')?.getBoundingClientRect(),help=cell.querySelector('.lex-info-help')?.getBoundingClientRect();return{key:cell.dataset.columnKey,labelRight:label?.right,helpLeft:help?.left,overlap:!!(label&&help&&label.right>help.left+.5)}}),firstRow=twice.querySelector('.lex-column-list-row'),numeric=['x','y','z'].map(key=>firstRow.querySelector(`[data-column-key="${key}"] input`)).map(input=>{const source=input.closest('.lex-source-control'),reference=source.querySelector(':scope>.lex-source-strip'),r=input.getBoundingClientRect(),sr=source.getBoundingClientRect(),rr=reference.getBoundingClientRect();return{width:r.width,available:rr.left-sr.left-2,clientWidth:input.clientWidth,scrollWidth:input.scrollWidth,className:source.className,display:getComputedStyle(source).display,sourceWidth:sr.width}}),stage=document.querySelector('.encounter-header-section .lex-detail-field:first-child'),stageInput=stage.querySelector('input'),stagePin=stage.querySelector('.lex-column-pin'),ir=stageInput.getBoundingClientRect(),pr=stagePin.getBoundingClientRect(),tip={x:pr.left+pr.width*3.71/24,y:pr.top+pr.height*21.71/24},wanted={x:ir.right-ir.height*.1,y:ir.top+ir.height*.1};return{before,first,second,slotColumn:twice.querySelectorAll('[data-column-key="slot"]').length,help:twice.querySelectorAll('.lex-column-list-head-cell .lex-info-help').length,headers,numeric,stagePin:{dx:tip.x-wanted.x,dy:tip.y-wanted.y,inControl:stage.querySelector('.lex-source-control')===stagePin.parentElement},finderWidthSpread:Math.max(...widths)-Math.min(...widths),finderBackground:getComputedStyle(finder).backgroundColor,finderBorder:getComputedStyle(finder).borderTopWidth,errors:window.__testErrors}})()""")
            enabled_state = cdp.eval("""(()=>{const table=document.querySelector('.encounter-slot-table'),headers=[...table.querySelectorAll('.lex-column-list-head-cell')],disabled=table.querySelector('.encounter-slot-disabled');return{first:headers[0]?.dataset.columnKey,label:headers[0]?.querySelector('.header-label')?.textContent.trim(),disabled:!!disabled,locked:disabled?[...disabled.querySelectorAll('.lex-column-list-cell:not(.encounter-slot-enabled) :is(input,select,textarea,button)')].every(control=>control.disabled):false}})()""")
            assert enabled_state == {"first": "enabled", "label": "", "disabled": True, "locked": True}, enabled_state
            assert encounter_sort["first"] != encounter_sort["second"] and encounter_sort["second"] == encounter_sort["before"], encounter_sort
            assert encounter_sort["slotColumn"] == 0 and encounter_sort["help"] == 9, encounter_sort
            assert encounter_sort["finderWidthSpread"] <= 1 and encounter_sort["finderBackground"] == "rgba(0, 0, 0, 0)" and encounter_sort["finderBorder"] == "0px", encounter_sort
            assert all(not row["overlap"] for row in encounter_sort["headers"]), encounter_sort
            assert all("lex-source-control-internal" in row["className"] and abs(row["width"] - row["sourceWidth"]) <= 2 and row["scrollWidth"] <= row["clientWidth"] + 1 for row in encounter_sort["numeric"]), encounter_sort
            assert encounter_sort["stagePin"]["inControl"] and abs(encounter_sort["stagePin"]["dx"]) <= 1 and abs(encounter_sort["stagePin"]["dy"]) <= 1, encounter_sort
            capture(cdp, "ff8-current-encounters.png")

            cdp.eval("navigate('enemies')")
            wait_eval(cdp, "[...document.querySelectorAll('.enemy-tabbed-column [role=tab]')].some(node=>node.textContent.trim().startsWith('AI'))", 30)
            enemy_surface = cdp.eval("""(()=>{const split=document.querySelector('.lex-leading-list-detail'),left=split.querySelector(':scope>.enemy-tabbed-column'),right=split.querySelector(':scope>.enemy-detail'),box=node=>{const r=node.getBoundingClientRect();return{left:r.left,right:r.right}},surface=node=>{const style=getComputedStyle(node);return{color:style.backgroundColor,image:style.backgroundImage}};return{children:[...split.children].filter(node=>node.classList.contains('lex-panel-layout-pane')).map(node=>node.className),left:box(left),right:box(right),surfaces:[surface(left),surface(right)],errors:window.__testErrors}})()""")
            assert "enemy-tabbed-column" in enemy_surface["children"][0] and "lex-barrelled-master" in enemy_surface["children"][1] and "enemy-detail" in enemy_surface["children"][2], enemy_surface
            assert enemy_surface["left"]["right"] <= enemy_surface["right"]["left"], enemy_surface
            assert enemy_surface["surfaces"][0] == enemy_surface["surfaces"][1] and "linear-gradient" in enemy_surface["surfaces"][0]["image"], enemy_surface
            assert not enemy_surface["errors"], enemy_surface
            cdp.eval("[...document.querySelectorAll('.enemy-tabbed-column [role=tab]')].find(node=>node.textContent.trim().startsWith('AI')).click()")
            wait_eval(cdp, "!!document.querySelector('.enemy-ability-table .lex-column-sort')", 30)
            enemy_sort = cdp.eval("""(()=>{const table=document.querySelector('.enemy-ability-table'),before=[...table.querySelectorAll('.lex-column-list-row')].map(row=>row.dataset.key),button=table.querySelector('[data-column-key="slot"] .lex-column-sort');button.click();const once=document.querySelector('.enemy-ability-table'),first=[...once.querySelectorAll('.lex-column-list-row')].map(row=>row.dataset.key);once.querySelector('[data-column-key="slot"] .lex-column-sort').click();const second=[...document.querySelector('.enemy-ability-table').querySelectorAll('.lex-column-list-row')].map(row=>row.dataset.key);return{before,first,second,errors:window.__testErrors}})()""")
            first_slots = [int(value.rsplit("-", 1)[1]) for value in enemy_sort["first"]]
            second_slots = [int(value.rsplit("-", 1)[1]) for value in enemy_sort["second"]]
            assert enemy_sort["first"] != enemy_sort["second"], enemy_sort
            assert first_slots == sorted(first_slots) and second_slots == sorted(second_slots, reverse=True), enemy_sort
            capture(cdp, "ff8-current-enemies.png")

            cdp.eval("state.filters.text='Description';state.pages.text=0;navigate('text')")
            wait_eval(cdp, "!![...document.querySelectorAll('.ff8-record-list .lex-column-list-row:not(.lex-filler-row)')].find(node=>node.textContent.includes('Description'))", 30)
            text_view = cdp.eval("""(()=>{const row=[...document.querySelectorAll('.ff8-record-list .lex-column-list-row:not(.lex-filler-row)')].find(node=>node.textContent.includes('Description')),field=row.querySelector('[data-column-key="role"]'),content=field.querySelector('.lex-column-cell-content')||field,fr=field.getBoundingClientRect(),cr=content.getBoundingClientRect(),title=document.querySelector('.lex-detail-panel-title')?.textContent.trim(),subtitle=document.querySelector('.lex-detail-panel-meta')?.textContent.trim();return{value:field.textContent.trim(),cell:{left:fr.left,right:fr.right},content:{left:cr.left,right:cr.right,client:content.clientWidth,scroll:content.scrollWidth},title,subtitle,titleContainsField:title?.includes('Description'),errors:window.__testErrors}})()""")
            assert text_view["value"] == "Description", text_view
            assert text_view["content"]["left"] >= text_view["cell"]["left"] and text_view["content"]["right"] <= text_view["cell"]["right"], text_view
            assert text_view["content"]["scroll"] <= text_view["content"]["client"] + 1, text_view
            assert text_view["subtitle"] == "Description" and not text_view["titleContainsField"], text_view
            assert not text_view["errors"], text_view
            capture(cdp, "ff8-current-text.png")

            cdp.eval("navigate('settings')")
            wait_eval(cdp, "!!document.querySelector('input[aria-label=\"Monogamy\"]')", 20)
            dependency = cdp.eval("""(()=>{const monogamy=document.querySelector('input[aria-label="Monogamy"]'),item=document.querySelector('input[aria-label="Universal Item"]'),unsafe=['Command Menu Rework','Shared Party Magic Inventory','XP Bars','HP Bars','Better Targeting'].map(label=>!!document.querySelector(`input[aria-label="${label}"]`));monogamy.checked=!monogamy.checked;monogamy.dispatchEvent(new Event('change',{bubbles:true}));return{rows:document.querySelectorAll('#main .setting-row').length,item:!!item,unsafe,accent:getComputedStyle(monogamy).accentColor,toolbarHidden:document.querySelector('#toolbar').hidden,toolbarTabs:document.querySelectorAll('#toolbar .lex-subtab-button').length,localSaveButtons:document.querySelectorAll('#main .lex-settings-save,#toolbar .lex-settings-save').length,globalSaveDisabled:document.querySelector('#global-save').disabled,errors:window.__testErrors}})()""")
            assert dependency["rows"] == 23 and dependency["item"] and all(dependency["unsafe"]), dependency
            assert dependency["accent"] == "rgb(170, 36, 50)" and not dependency["toolbarHidden"] and dependency["toolbarTabs"] == 2, dependency
            assert dependency["localSaveButtons"] == 0 and not dependency["globalSaveDisabled"], dependency
            capture(cdp, "ff8-current-setting-dependency.png")

            cdp.eval("navigate('items');navigate('weapons')")
            wait_eval(cdp, "document.querySelector('nav button[data-tab=\"weapons\"]')?.classList.contains('active')", 10)
            before_back_url = cdp.eval("location.href")
            cdp.eval("history.back()")
            wait_eval(cdp, "document.querySelector('nav button[data-tab=\"items\"]')?.classList.contains('active')", 10)
            browser_back = cdp.eval("""({url:location.href,active:document.querySelector('nav button.active[data-tab]')?.dataset.tab,home:location.protocol==='file:',errors:window.__testErrors})""")
            assert browser_back["url"] == before_back_url and browser_back["active"] == "items" and not browser_back["home"], browser_back

            # The two global number settings must use the game skin rather
            # than Chromium's white input and text shadow.
            settings_style = cdp.eval("""(()=>{const fixture=document.createElement('section');fixture.className='lex-global-setting';fixture.style.position='fixed';fixture.style.left='-1000px';const ids=['lex-selection-hold','lex-table-rows'];for(const id of ids){const input=document.createElement('input');input.id=id;input.type='number';fixture.append(input)}document.body.append(fixture);const values=ids.map(id=>{const style=getComputedStyle(document.getElementById(id));return{id,background:style.backgroundColor,shadow:style.boxShadow,textShadow:style.textShadow,color:style.color}});fixture.remove();return{values,errors:window.__testErrors}})()""")
            assert all(value["background"] != "rgb(255, 255, 255)" and value["shadow"] == "none" and value["textShadow"] == "none" for value in settings_style["values"]), settings_style

            # Global Settings must retain the same two-track geometry when the
            # FF8 theme and its wider extracted font are active.
            cdp.eval("""(()=>{window.pywebview={api:{lexeditor_settings:async()=>({developerMode:false,lexerMode:true,lexerAuthorized:true,lexerLogin:'Lexer-Lux',hoverableAltClick:false,selectionHoldMs:650,tableRowsPerPage:15,panelGapPercent:1,residentHandleWidthPercent:5,mainMenuHeightPercent:9,soundEnabled:true,soundVolumePercent:50,absentGameDesaturationPercent:75,globalMessageRarity:3,loadingTransitionMinimumSeconds:1.5,updateCheckFrequency:'daily',updateCheckChoices:[{value:'daily',label:'Daily'},{value:'weekly',label:'Weekly'}],defaultValues:{developerMode:false,hoverableAltClick:false,selectionHoldMs:650,tableRowsPerPage:15,panelGapPercent:1,residentHandleWidthPercent:5,mainMenuHeightPercent:9,soundEnabled:true,soundVolumePercent:50,absentGameDesaturationPercent:75,globalMessageRarity:3,loadingTransitionMinimumSeconds:1.5,updateCheckFrequency:'daily'},helpers:[]})}};LexeditorUI.openSettings()})()""")
            wait_eval(cdp, "!!document.querySelector('#lex-mainMenuHeightPercent')", 10)
            themed_settings = cdp.eval("""(()=>{const pairs=[...document.querySelectorAll('.lex-setting-control-pair')].map(pair=>{const controls=[...pair.querySelectorAll('input[type="number"],select')].filter(node=>!node.disabled),boxes=controls.map(node=>{const r=node.getBoundingClientRect(),owner=node.closest('.lex-setting-default-control,.lex-unit-field')||node,or=owner.getBoundingClientRect();return{id:node.id,left:r.left,right:r.right,width:r.width,ownerLeft:or.left,ownerRight:or.right,clientWidth:node.clientWidth,scrollWidth:node.scrollWidth}});return{boxes,overlap:boxes.length>1&&boxes[0].right>boxes[1].left+.5,contained:boxes.every(box=>box.left>=box.ownerLeft-.5&&box.right<=box.ownerRight+.5),readable:boxes.every(box=>box.width>=80&&box.scrollWidth<=box.clientWidth+1)}}),dialog=document.querySelector('.lex-global-settings'),main=document.querySelector('#lex-mainMenuHeightPercent'),unit=main.closest('.lex-unit-field').querySelector('.lex-unit');return{pairs,mainValue:main.value,unit:unit.textContent,overflow:dialog.scrollWidth-dialog.clientWidth,errors:window.__testErrors}})()""")
            assert themed_settings["mainValue"] == "9" and themed_settings["unit"] == "%", themed_settings
            assert all(not row["overlap"] and row["contained"] and row["readable"] for row in themed_settings["pairs"]), themed_settings
            assert themed_settings["overflow"] <= 1 and not themed_settings["errors"], themed_settings
            capture(cdp, "ff8-current-global-settings.png")
            cdp.eval("document.querySelector('.lex-global-settings .lex-close-button').click()")
            wait_eval(cdp, "!document.querySelector('.lex-global-settings')", 5)

            # The loading transition is exercised on a fresh target. By this
            # point the page has been driven through searchers, dialogs and
            # settings, and the accumulated session stops answering evals;
            # a new tab reproduces the transition faithfully and cheaply.
            request = Request(f"http://127.0.0.1:{port}/json/new?about:blank",
                              method="PUT")
            fresh = json.loads(urlopen(request, timeout=10).read().decode("utf-8"))
            cdp = Cdp(fresh["webSocketDebuggerUrl"])
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride", {
                "width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False,
            })
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__testErrors=[];
              addEventListener('error',event=>{if(String(event.message).indexOf('ResizeObserver loop')>=0)return;window.__testErrors.push(String(event.message));});
              addEventListener('unhandledrejection',event=>window.__testErrors.push(String(event.reason)));
              window.pywebview={api:{transition_snapshot:async()=>({html:'<!doctype html><html><body style="margin:0;background:#18202b;color:white;font:40px sans-serif;display:grid;height:100vh;place-items:center">LEXEDITOR MENU PROOF</body></html>'})}};
              const nativeFetch=window.fetch.bind(window);let delayed=false;
              window.fetch=(...args)=>{const address=String(args[0]||'');if(!delayed&&address.includes('/api/dashboard')){delayed=true;return new Promise(resolve=>setTimeout(resolve,800)).then(()=>nativeFetch(...args))}return nativeFetch(...args)};
            """})
            cdp.call("Page.navigate", {"url": session.url + "?lexTransition=load&lexQuote=Transition%20proof"})
            wait_eval(cdp, "document.readyState==='complete'", 30)
            transition_debug = cdp.eval("""(()=>({url:location.href,api:Object.keys(window.pywebview?.api||{}),backdrop:document.querySelector('.lex-plugin-transition-backdrop')?.getAttribute('srcdoc')?.includes('LEXEDITOR MENU PROOF')||false,loading:!!document.querySelector('.lex-plugin-loading-screen'),surface:!!document.querySelector('.lex-plugin-transition-surface'),errors:window.__testErrors}))()""")
            assert transition_debug["backdrop"] and transition_debug["loading"], transition_debug
            transition_loading = cdp.eval("""(()=>{const surface=document.querySelector('.lex-plugin-transition-surface').getBoundingClientRect(),backdrop=document.querySelector('.lex-plugin-transition-backdrop').getBoundingClientRect();return{quote:document.querySelector('.lex-plugin-loading-quote').textContent,surfaceLeft:surface.left,backdropLeft:backdrop.left,dim:getComputedStyle(document.querySelector('.lex-plugin-loading-screen')).backgroundColor,errors:window.__testErrors}})()""")
            assert transition_loading["quote"] == "Transition proof", transition_loading
            assert transition_loading["surfaceLeft"] >= 1500 and abs(transition_loading["backdropLeft"]) <= 1, transition_loading
            assert not transition_loading["errors"], transition_loading
            capture(cdp, "ff8-current-loading-transition.png")
            transition_done = None
            for _ in range(80):
                transition_done = cdp.eval("""(()=>({ready:typeof state!=='undefined'&&!state.booting&&!document.querySelector('.lex-plugin-transition-backdrop')&&!document.querySelector('.lex-plugin-loading-screen')&&document.querySelector('.lex-plugin-transition-surface.settled')!==null,booting:typeof state==='undefined'?null:state.booting,backdrop:!!document.querySelector('.lex-plugin-transition-backdrop'),surface:document.querySelector('.lex-plugin-transition-surface')?.className||'',left:document.querySelector('.lex-plugin-transition-surface')?.getBoundingClientRect().left??null,loading:!!document.querySelector('.lex-plugin-loading-screen'),errors:window.__testErrors}))()""")
                if transition_done["ready"]:
                    break
                time.sleep(.25)
            assert transition_done and transition_done["ready"], transition_done
            assert abs(transition_done["left"]) <= 1 and not transition_done["loading"] and not transition_done["errors"], transition_done
            print(json.dumps({"topBar": top_bar, "formulae": formulae, "items": items, "characters": characters, "magic": magic, "shops": shops, "weapons": weapons, "encounterSort": encounter_sort, "enemySort": enemy_sort, "text": text_view, "settingDependency": dependency, "browserBack": browser_back, "settings": settings_style, "themedSettings": themed_settings, "transition": {"loading": transition_loading, "done": transition_done}}, ensure_ascii=True))
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
