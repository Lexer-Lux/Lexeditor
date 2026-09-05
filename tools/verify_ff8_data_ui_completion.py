"""Hidden rendered contract for the FF8 structured data editors."""

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
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    profile = tempfile.TemporaryDirectory(
        prefix="lexeditor-ff8-data-ui-edge-", ignore_cleanup_errors=True)
    project = tempfile.TemporaryDirectory(prefix="lexeditor-ff8-data-ui-project-", ignore_cleanup_errors=True)
    port = free_port()
    browser = None
    cdp = None
    try:
        with FF8Session({"LEXEDITOR_FF8_PROJECT": project.name}) as session:
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

            item = cdp.eval("""(()=>{state.selected.items=159;navigate('items');return{
              section:!!document.querySelector('.item-menu-section'),
              controls:document.querySelectorAll('.item-menu-section input,.item-menu-section select').length,
              flags:document.querySelectorAll('.item-menu-section input[type=checkbox]').length,
              flagRows:new Set([...document.querySelectorAll('.item-menu-section .lex-toggle-row label')]
                .map(label=>Math.round(label.getBoundingClientRect().top))).size,
              pinOffsets:[...document.querySelectorAll('.item-price-section .ff8-equation-term')].map(term=>{
                const input=term.querySelector('input'),pin=term.querySelector('.lex-column-pin');
                if(!input||!pin)return null;const ir=input.getBoundingClientRect(),pr=pin.getBoundingClientRect();
                return {label:term.closest('.lex-detail-field')?.querySelector('.lex-detail-field-label')?.textContent.trim(),
                  right:Math.abs(ir.right-pr.right),top:Math.abs(ir.top-pr.top)};
              }).filter(Boolean),
              types:state.data.menuItems.types.length,
            }})()""")
            assert item["section"] and item["controls"] >= 10 and item["flags"] == 8, item
            # The flags wrap in the shared toggle row; every label in a wrapped
            # row must share one top, so the count equals the number of rows.
            assert 1 <= item["flagRows"] <= 4, item
            assert len(item["pinOffsets"]) == 3, item
            assert all(offset["right"] <= 14 and offset["top"] <= 14 for offset in item["pinOffsets"]), item
            assert item["types"] >= 20, item

            fit = cdp.eval("""(async()=>{const control=document.querySelector('.item-parameter-field select');if(!control)return null;
              const normal=parseFloat(getComputedStyle(control).fontSize);control.style.width='120px';await new Promise(resolve=>setTimeout(resolve,100));
              const narrow=parseFloat(getComputedStyle(control).fontSize),value=control.selectedOptions[0]?.textContent;
              const clientWidth=control.clientWidth,scrollWidth=control.scrollWidth,style=getComputedStyle(control);
              const canvas=document.createElement('canvas'),context=canvas.getContext('2d');
              context.font=`${style.fontStyle} ${style.fontWeight} ${normal}px ${style.fontFamily}`;
              const measured=context.measureText(value).width;
              control.style.width='';return{normal,narrow,value,clientWidth,scrollWidth,measured,font:context.font}})()""", await_promise=True)
            assert fit and fit["value"] == "Tonberry King" and \
                11 <= fit["narrow"] <= fit["normal"] and \
                fit["scrollWidth"] <= fit["clientWidth"] + 1, fit
            item["parameterFit"] = fit
            item_shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            item_rendered = ROOT / "worklog" / "issues" / "rendered" / "github-63-ff8-item-parameters.png"
            item_rendered.parent.mkdir(parents=True, exist_ok=True)
            item_rendered.write_bytes(base64.b64decode(item_shot["data"]))

            enemy_id = cdp.eval("state.data.enemyTables.rows[0].id")
            enemy = cdp.eval(f"""(()=>{{state.selected.enemies={enemy_id};navigate('enemies');return{{
              tabs:[...document.querySelectorAll('.enemy-tabbed-column [role=tab]')].map(node=>node.textContent.trim().replace(/\\d+$/,'')),
              active:document.querySelector('.enemy-tabbed-column [role=tab][aria-selected=true]')?.textContent.trim().replace(/\\d+$/,''),
              curves:document.querySelectorAll('.enemy-tabbed-column .lex-curve-editor').length,
              pairTables:document.querySelectorAll('.enemy-pair-table').length,
              finders:document.querySelectorAll('.enemy-table-section .ff8-item-search,.enemy-table-section .ff8-entity-search').length,
            }}}})()""")
            assert enemy["tabs"] == ["Stats", "AI", "Battle Text"] and enemy["active"] == "Stats", enemy
            assert enemy["curves"] == 7, enemy
            assert enemy["pairTables"] == 3 and enemy["finders"] > 0, enemy
            cdp.eval("[...document.querySelectorAll('.enemy-tabbed-column [role=tab]')].find(node=>node.textContent.includes('AI')).click()")
            wait_eval(cdp, "document.querySelectorAll('.enemy-ability-table .lex-column-list-row').length===48&&document.querySelectorAll('.enemy-ai-script').length===5", 10)
            enemy["abilityRows"] = cdp.eval("document.querySelectorAll('.enemy-ability-table .lex-column-list-row').length")
            enemy["conditionalRows"] = cdp.eval("document.querySelectorAll('.enemy-ai-instruction').length")
            enemy["boundary"] = cdp.eval("document.querySelector('.enemy-ai-boundary')?.textContent||''")
            assert enemy["abilityRows"] == 48 and enemy["conditionalRows"] > 0, enemy
            assert "decoded and rebuilt" in enemy["boundary"] and \
                "replace, insert, delete, and reorder" in enemy["boundary"] and \
                "not decoded" not in enemy["boundary"], enemy
            ai_shot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            ai_rendered = ROOT / "worklog" / "issues" / "rendered" / "github-64-ff8-enemy-ai.png"
            ai_rendered.parent.mkdir(parents=True, exist_ok=True)
            ai_rendered.write_bytes(base64.b64decode(ai_shot["data"]))

            encounter = cdp.eval("""(()=>{state.selected.encounters=0;navigate('encounters');return{
              tab:[...document.querySelectorAll('nav button[data-tab]')].some(node=>node.dataset.tab==='encounters'),
              slots:document.querySelectorAll('.encounter-slot-table .lex-column-list-row').length,
              enemyFinders:document.querySelectorAll('.encounter-slot-table .ff8-entity-search').length,
              headerControls:document.querySelectorAll('.encounter-header-section input').length,
              fieldPins:[...document.querySelectorAll('.encounter-header-section .lex-detail-field')].map(field=>({
                label:field.querySelector('.lex-detail-field-label')?.childNodes[0]?.textContent.trim(),
                help:field.querySelector('.lex-info-help')?.getAttribute('title')||'',
                pressed:field.querySelector('.lex-column-pin')?.getAttribute('aria-pressed')})),
              slotControls:[...(document.querySelector('.encounter-slot-table .lex-column-list-row')?.querySelectorAll('input')||[])].map(input=>({
                type:input.type,value:input.type==='checkbox'?input.checked:input.value,
                width:input.getBoundingClientRect().width,height:input.getBoundingClientRect().height,
                fits:input.type==='checkbox'||input.scrollWidth<=input.clientWidth+1})),
              slotSelects:[...(document.querySelector('.encounter-slot-table .lex-column-list-row')?.querySelectorAll('select')||[])].map(select=>({
                value:select.value,text:select.selectedOptions[0]?.textContent,disabled:select.disabled})),
            }})()""")
            assert encounter["tab"] and encounter["slots"] == 8 and encounter["enemyFinders"] == 8, encounter
            assert encounter["headerControls"] == 4, encounter
            assert encounter["fieldPins"] == [
                {"label": "STAGE ID", "help": "", "pressed": "true"},
                {"label": "FLAGS", "help": "", "pressed": "false"},
                {"label": "MAIN CAMERA", "help": "", "pressed": "false"},
                {"label": "SECONDARY CAMERA", "help": "", "pressed": "false"},
            ], encounter
            assert len(encounter["slotControls"]) == 9, encounter
            assert all(control["width"] >= 18 and control["height"] >= 18
                       for control in encounter["slotControls"]), encounter
            assert [control["value"] for control in encounter["slotControls"] if control["type"] == "text"] == ["1,100", "0", "-3,300", "1"], encounter
            assert encounter["slotSelects"] == [{"value": "special", "text": "Special (255)", "disabled": False}], encounter
            assert all(control["fits"] for control in encounter["slotControls"]), encounter
            cdp.eval("document.querySelector('.encounter-header-section .lex-column-pin[aria-pressed=true]').click()")
            wait_eval(cdp, "!document.querySelector('.encounter-slot-table')?.closest('.lex-paged-list-detail')?.querySelector('.lex-barrel-grid [data-column-key=stageId]')", 10)
            encounter["stageUnpinned"] = cdp.eval("document.querySelector('.encounter-header-section .lex-column-pin')?.getAttribute('aria-pressed')==='false'")
            assert encounter["stageUnpinned"], encounter
            screenshot = cdp.call("Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False, "fromSurface": True,
            })
            rendered = ROOT / "worklog" / "issues" / "rendered" / "github-39-ff8-encounters.png"
            rendered.parent.mkdir(parents=True, exist_ok=True)
            rendered.write_bytes(base64.b64decode(screenshot["data"]))
            data_map = cdp.eval("""(()=>Object.fromEntries(state.datamap.rows
              .filter(row=>['menu/mitem.bin','battle/c0m*.dat','battle/scene.out'].includes(row.filename))
              .map(row=>[row.filename,row.status])))()""")
            assert data_map == {"menu/mitem.bin": "integrated", "battle/c0m*.dat": "partial",
                                "battle/scene.out": "integrated"}, data_map

            saved = cdp.eval("""(async()=>{
              state.data.menuItems.rows[0].flags^=1;
              state.data.encounters.rows[0].stageId=(state.data.encounters.rows[0].stageId+1)&255;
              const table=state.data.enemyTables.rows[0];
              table.tables.abilities.low[0].animation=(table.tables.abilities.low[0].animation+1)&255;
              const before=dirtyCount();await saveAll();
              return {before,after:dirtyCount(),menu:state.data.menuItems.rows[0].flags,
                encounter:state.data.encounters.rows[0].stageId,
                animation:state.data.enemyTables.rows[0].tables.abilities.low[0].animation,
                errors:window.__testErrors};
            })()""", await_promise=True)
            assert saved["before"] == 3 and saved["after"] == 0, saved
            assert not saved["errors"], saved
            assert (Path(project.name) / "direct" / "menu" / "mitem.bin").is_file(), saved
            assert (Path(project.name) / "direct" / "battle" / "scene.out").is_file(), saved
            assert list((Path(project.name) / "direct" / "battle").glob("c0m*.dat")), saved
            print({"items": item, "itemScreenshot": str(item_rendered), "enemy": enemy, "enemyAiScreenshot": str(ai_rendered), "encounter": encounter,
                   "dataMap": data_map, "save": saved})
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
